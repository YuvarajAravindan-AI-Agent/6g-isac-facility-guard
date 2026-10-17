"""Phase 2: ISAC sensing pipeline on GPU.

clutter removal -> range-Doppler -> 2D CA-CFAR -> cluster/peak interpolation ->
angle estimation (16x8 panel, modelled at the detected cell with per-element noise) ->
EKF tracker (M-of-N confirmation) -> Monte Carlo metrics + plots + tracks.json.
"""
import json
import time
import numpy as np
import torch
import torch.nn.functional as F
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import isac_sim as I

dev = "cuda"
C, LAM, N, M, TS = I.C, I.LAM, I.N, I.M, I.TSYM
RES_R = C / (2 * I.B)
DV = LAM / (2 * M * TS)
GNB = I.GNB
KA, KE = 16, 8
K = KA * KE
PFA = 1e-6
FRAME_DT = I.FRAME_DT
D = I.P_END - I.P_START
L = float(np.linalg.norm(D))
DIR = D / L
VEL = I.SPEED * DIR
T_END = L / I.SPEED
N_FRAMES = int((T_END - M * TS) / FRAME_DT)

# CFAR geometry: guard (doppler, range), training (doppler, range)
GV, GR, TV, TR = 2, 3, 8, 12
NT = (2 * (GV + TV) + 1) * (2 * (GR + TR) + 1) - (2 * GV + 1) * (2 * GR + 1)

VALID = torch.ones(M, N, dtype=torch.bool, device=dev)
VALID[M // 2 - 1:M // 2 + 2, :] = False        # zero-Doppler notch (|v| <= 1 bin = 1.76 m/s)
VALID[:, :int(8 / RES_R)] = False              # near-in leakage region

WIN_N = torch.hann_window(N, periodic=True, device=dev)
WIN_M = torch.hann_window(M, periodic=True, device=dev)
FREQ = torch.arange(N, device=dev, dtype=torch.float64) * I.DF
P_START_T = torch.tensor(I.P_START, device=dev)
VEL_T = torch.tensor(VEL, device=dev)
GNB_T = torch.tensor(GNB, device=dev)


def alpha(pfa):
    return NT * (pfa ** (-1.0 / NT) - 1.0)


def truth(t):
    pos = I.P_START + VEL * t
    rel = pos - GNB
    R = float(np.linalg.norm(rel))
    return dict(pos=pos, R=R, rv=float(VEL @ rel / R), u=rel[1] / R, v=rel[2] / R)


def gen_rd(t0, H0t, g, rcs, drone=True):
    if drone:
        t = t0 + torch.arange(M, device=dev, dtype=torch.float64) * TS
        pos = P_START_T[None, :] + VEL_T[None, :] * t[:, None]
        R = torch.linalg.norm(pos - GNB_T[None, :], dim=1)
        tau = 2 * R / C
        amp = torch.sqrt(10 ** (2 * I.GAIN_DB / 10) * LAM**2 * rcs / ((4 * np.pi) ** 3 * R**4))
        ph = -2 * np.pi * (I.FC + FREQ[None, :]) * tau[:, None]
        Y = H0t[None, :] + amp[:, None] * torch.exp(1j * ph)
    else:
        Y = H0t[None, :].expand(M, N).clone()
    s = I.noise_sigma() / np.sqrt(2)
    Y = Y + s * (torch.randn(M, N, generator=g, device=dev, dtype=torch.float64)
                 + 1j * torch.randn(M, N, generator=g, device=dev, dtype=torch.float64))
    Y = Y - Y.mean(0, keepdim=True)              # static clutter removal
    y = Y.to(torch.complex64) * WIN_N[None, :]    # Hann windows suppress sidelobe skirts of strong targets
    rd = torch.fft.fftshift(torch.fft.fft(torch.fft.ifft(y, dim=1) * WIN_M[:, None], dim=0), dim=0)
    return rd, rd.real**2 + rd.imag**2


def _box(x, hv, hr):
    k = (2 * hv + 1, 2 * hr + 1)
    xp = F.pad(x, (hr, hr, 0, 0), mode="replicate")
    xp = F.pad(xp, (0, 0, hv, hv), mode="circular")
    return F.avg_pool2d(xp, k, stride=1) * (k[0] * k[1])


def cfar_ratio(P):
    x = P.double()[None, None]
    noise = (_box(x, GV + TV, GR + TR) - _box(x, GV, GR)) / NT
    return (x / noise)[0, 0], noise[0, 0]


def parab(a, b, c):
    d = a - 2 * b + c
    return 0.0 if d == 0 else float(np.clip(0.5 * (a - c) / d, -0.5, 0.5))


def angle_est(p, noise_pow, u, v, rng):
    """Single-snapshot 2D beamscan on a KA x KE panel (half-wavelength spacing)."""
    mm = np.arange(KA)[None, :]
    nn = np.arange(KE)[:, None]
    a = np.exp(1j * np.pi * (mm * u + nn * v))
    x = (p / np.sqrt(K)) * a + np.sqrt(noise_pow / 2) * (
        rng.standard_normal((KE, KA)) + 1j * rng.standard_normal((KE, KA)))
    X = np.abs(np.fft.fftshift(np.fft.fft2(x, s=(64, 128))))
    kv, ku = np.unravel_index(X.argmax(), X.shape)
    du = parab(X[kv, (ku - 1) % 128], X[kv, ku], X[kv, (ku + 1) % 128])
    dv = parab(X[(kv - 1) % 64, ku], X[kv, ku], X[(kv + 1) % 64, ku])
    return 2 * (ku + du - 64) / 128, 2 * (kv + dv - 32) / 64


def extract(rd, P, ratio, noise, pfa, tr, rng):
    det = (ratio > alpha(pfa)) & VALID
    pk = F.max_pool2d(P[None, None], 3, 1, 1)[0, 0]
    det &= (P >= pk)
    idx = det.nonzero().cpu().numpy()
    if len(idx) == 0:
        return []
    Pc = P.cpu().numpy()
    out = []
    for i, j in idx[:50]:
        lp = lambda a, b: np.log(Pc[a, b] + 1e-30)
        i0, i1 = max(i - 1, 0), min(i + 1, M - 1)
        j0, j1 = max(j - 1, 0), min(j + 1, N - 1)
        di = parab(lp(i0, j), lp(i, j), lp(i1, j))
        dj = parab(lp(i, j0), lp(i, j), lp(i, j1))
        R = (j + dj) * RES_R
        vr = -(i + di - M / 2) * DV
        snr = float(ratio[i, j])
        is_truth = abs(R - tr["R"]) < 1.5 and abs(vr - tr["rv"]) < 3.5
        if is_truth:
            ut, vt = tr["u"], tr["v"]
        else:                                            # false alarm: random direction
            ang = rng.uniform(0, 2 * np.pi); rad = 0.7 * np.sqrt(rng.uniform())
            ut, vt = rad * np.cos(ang), rad * np.sin(ang)
        p = complex(rd[i, j])
        ue, ve = angle_est(p, float(noise[i, j]), ut, vt, rng)
        snr_el = max((snr - 1) / K, 0.05)
        su = 1.5 * np.sqrt(6 / (snr_el * KE * KA * (KA**2 - 1))) / np.pi
        sv = 1.5 * np.sqrt(6 / (snr_el * KA * KE * (KE**2 - 1))) / np.pi
        out.append(dict(R=float(R), vr=float(vr), u=float(ue), v=float(ve),
                        su=float(max(su, 0.003)), sv=float(max(sv, 0.003)),
                        snr_db=float(10 * np.log10(snr)), is_truth=bool(is_truth)))
    return out


# ------------------------- tracker (EKF, constant velocity) -------------------------
SIG_R, SIG_RD, Q_ACC, GATE = 0.25, 0.6, 2.0, 23.5   # chi2(4) ~ 99.99%


def hfun(x):
    rel = x[:3] - GNB
    R = np.linalg.norm(rel)
    return np.array([R, rel[1] / R, rel[2] / R, rel @ x[3:] / R])


def hjac(x):
    J = np.zeros((4, 6))
    for k in range(6):
        e = np.zeros(6); e[k] = 1e-4
        J[:, k] = (hfun(x + e) - hfun(x - e)) / 2e-4
    return J


def pos_from_meas(d):
    w = np.sqrt(max(1 - d["u"]**2 - d["v"]**2, 1e-6))   # boresight = +x
    dirv = np.array([w, d["u"], d["v"]])
    return GNB + d["R"] * dirv, dirv


class Tracker:
    def __init__(self):
        self.x = None
        self.hits = 0
        self.miss = 0
        self.confirmed = False
        self.confirm_t = None
        self.confirm_range = None

    def step(self, dets, dt, t):
        if self.x is None:
            if not dets:
                return None
            d = max(dets, key=lambda q: q["snr_db"])
            pos, dirv = pos_from_meas(d)
            self.x = np.concatenate([pos, d["vr"] * dirv])
            self.P = np.diag([25.0**2] * 3 + [10.0**2] * 3)
            self.hits, self.miss, self.confirmed = 1, 0, False
            return self.snapshot()
        F_ = np.eye(6); F_[:3, 3:] = np.eye(3) * dt
        G = np.zeros((6, 3)); G[:3] = np.eye(3) * dt**2 / 2; G[3:] = np.eye(3) * dt
        self.x = F_ @ self.x
        self.P = F_ @ self.P @ F_.T + Q_ACC**2 * G @ G.T
        Hm = hjac(self.x)
        hx = hfun(self.x)
        best = None
        for d in dets:
            z = np.array([d["R"], d["u"], d["v"], d["vr"]])
            Rm = np.diag([SIG_R**2, d["su"]**2, d["sv"]**2, SIG_RD**2])
            S = Hm @ self.P @ Hm.T + Rm
            inn = z - hx
            m = float(inn @ np.linalg.solve(S, inn))
            if m < GATE and (best is None or m < best[0]):
                best = (m, inn, S)
        if best:
            _, inn, S = best
            Kg = self.P @ Hm.T @ np.linalg.inv(S)
            self.x = self.x + Kg @ inn
            self.P = (np.eye(6) - Kg @ Hm) @ self.P
            self.hits += 1
            self.miss = 0
        else:
            self.miss += 1
        if not self.confirmed and self.hits >= 3:
            self.confirmed = True
            self.confirm_t = t
            self.confirm_range = float(np.linalg.norm(self.x[:3] - GNB))
        if (not self.confirmed and self.miss >= 2) or (self.confirmed and self.miss >= 3):
            self.x = None
            return None
        return self.snapshot()

    def snapshot(self):
        return dict(pos=self.x[:3].tolist(), vel=self.x[3:].tolist(),
                    sigma_pos=float(np.sqrt(np.trace(self.P[:3, :3]) / 3)),
                    confirmed=bool(self.confirmed))


# ------------------------------- runs and metrics -------------------------------
def run_once(seed, H0t, rcs, keep_frame=None, export=None):
    g = torch.Generator(device=dev); g.manual_seed(seed)
    rng = np.random.default_rng(seed)
    trk = Tracker()
    frames, kept = [], None
    first_det = None
    for k in range(N_FRAMES):
        t0 = k * FRAME_DT
        tm = t0 + M * TS / 2
        rd, P = gen_rd(t0, H0t, g, rcs)
        if export is not None:       # +-30 m/s crop, dB above median noise, uint8 (0..50 dB), velocity ascending
            med = P.flatten()[::97].median()
            crop = P[M // 2 - 17:M // 2 + 18].flip(0)
            db = 10 * torch.log10(crop / med + 1e-9)
            export.append((db.clamp(0, 50) * (255 / 50)).round().to(torch.uint8).cpu().numpy())
        ratio, noise = cfar_ratio(P)
        tr = truth(tm)
        dets = extract(rd, P, ratio, noise, PFA, tr, rng)
        has_truth = any(d["is_truth"] for d in dets)
        if has_truth and first_det is None:
            first_det = (tm, tr["R"])
        snap = trk.step(dets, FRAME_DT, tm)
        err_p = err_v = None
        if snap and snap["confirmed"]:
            err_p = float(np.linalg.norm(np.array(snap["pos"]) - tr["pos"]))
            err_v = float(np.linalg.norm(np.array(snap["vel"]) - VEL))
        frames.append(dict(t=tm, truth=dict(pos=tr["pos"].tolist(), vel=VEL.tolist(), R=tr["R"], rv=tr["rv"]),
                           detections=dets, track=snap, has_truth_det=has_truth, err_pos=err_p, err_vel=err_v,
                           n_false=sum(1 for d in dets if not d["is_truth"])))
        if keep_frame == k:
            sel = torch.abs(torch.arange(M, device=dev) - M // 2) * DV <= 40
            kept = (P[sel].cpu().numpy(), dets, tr)
    return dict(frames=frames, first_det=first_det, confirm_t=trk.confirm_t, confirm_range=trk.confirm_range,
                kept=kept)


def truth_ratio(ratio, t0):
    tr = truth(t0 + M * TS / 2)
    j = int(round(tr["R"] / RES_R)); i = int(round(M / 2 - tr["rv"] / DV))
    return float(ratio[i - 1:i + 2, j - 1:j + 2].max())


def t_at_range(Rt):
    ts = np.linspace(0, T_END - M * TS - 0.01, 4000)
    r = np.array([truth(t + M * TS / 2)["R"] for t in ts])
    return float(ts[np.argmin(abs(r - Rt))])


def main():
    t_start = time.time()
    H0, _, _ = I.static_clutter()
    H0t = torch.tensor(H0, device=dev)
    out = {}
    print(f"frames/run {N_FRAMES}, CFAR cells {NT}, alpha(1e-6)={10*np.log10(alpha(1e-6)):.1f} dB")

    # 1) nominal and small-target Monte Carlo with full tracker
    mc = {}
    exp = []
    for label, rcs, runs in [("drone_0.01", 0.01, 20), ("small_0.001", 0.001, 20)]:
        res = [run_once(s, H0t, rcs, keep_frame=20 if s == 0 else None,
                        export=exp if (s == 0 and label == "drone_0.01") else None) for s in range(runs)]
        mc[label] = res
        print(label, "done", f"{time.time()-t_start:.0f}s")
    nominal = mc["drone_0.01"][0]

    summ = {}
    for label, res in mc.items():
        fd = [r["first_det"][1] for r in res if r["first_det"]]
        cf = [r["confirm_range"] for r in res if r["confirm_t"] is not None]
        ep = [f["err_pos"] for r in res for f in r["frames"] if f["err_pos"] is not None]
        ev = [f["err_vel"] for r in res for f in r["frames"] if f["err_vel"] is not None]
        nfa = sum(f["n_false"] for r in res for f in r["frames"])
        nfr = sum(len(r["frames"]) for r in res)
        summ[label] = dict(
            runs=len(res), first_detection_range_median_m=float(np.median(fd)) if fd else None,
            confirmed_runs=len(cf), confirm_range_median_m=float(np.median(cf)) if cf else None,
            confirm_range_worst_m=float(np.min(cf)) if cf else None,
            pos_err_rmse_m=float(np.sqrt(np.mean(np.square(ep)))) if ep else None,
            pos_err_p90_m=float(np.percentile(ep, 90)) if ep else None,
            vel_err_rmse_mps=float(np.sqrt(np.mean(np.square(ev)))) if ev else None,
            false_detections_per_frame=nfa / nfr)
    out["monte_carlo"] = summ
    tbr = {}
    bb = np.arange(0, 361, 40)
    for label, res in mc.items():
        rr = np.array([f["truth"]["R"] for r in res for f in r["frames"] if f["err_pos"] is not None])
        ee = np.array([f["err_pos"] for r in res for f in r["frames"] if f["err_pos"] is not None])
        cen, med, p90 = [], [], []
        for k in range(len(bb) - 1):
            sel = (rr >= bb[k]) & (rr < bb[k + 1])
            if sel.any():
                cen.append(float((bb[k] + bb[k + 1]) / 2)); med.append(float(np.median(ee[sel]))); p90.append(float(np.percentile(ee[sel], 90)))
        tbr[label] = dict(range_m=cen, median_m=med, p90_m=p90)
    out["tracking_error_by_range"] = tbr

    # 2) Pd vs range per target size
    bins = np.arange(0, 361, 30)
    pdr = {}
    for label, res in mc.items():
        hit = np.zeros(len(bins) - 1); tot = np.zeros(len(bins) - 1)
        for r in res:
            for f in r["frames"]:
                b = np.searchsorted(bins, f["truth"]["R"]) - 1
                if 0 <= b < len(hit):
                    tot[b] += 1; hit[b] += f["has_truth_det"]
        pdr[label] = (hit / np.maximum(tot, 1)).tolist()
    out["pd_vs_range"] = dict(bins_m=bins.tolist(), pd=pdr)

    # 3) Pd vs RCS at ~300 m, several Pfa; 4) measured vs design Pfa on noise-only frames
    t300 = t_at_range(300.0)
    rcs_list = np.logspace(-4.5, -1.5, 13)
    pfas = [1e-3, 1e-4, 1e-5, 1e-6, 1e-7, 1e-8]
    TR_N = 100
    pd = np.zeros((len(rcs_list), len(pfas)))
    g = torch.Generator(device=dev); g.manual_seed(1234)
    for a, rcs in enumerate(rcs_list):
        for _ in range(TR_N):
            rd, P = gen_rd(t300, H0t, g, rcs)
            ratio, _ = cfar_ratio(P)
            tr_ = truth_ratio(ratio, t300)
            pd[a] += [tr_ > alpha(p) for p in pfas]
    pd /= TR_N
    out["pd_vs_rcs_300m"] = dict(rcs=rcs_list.tolist(), pfa=pfas, pd=pd.tolist(), range_m=truth(t300 + M * TS / 2)["R"])

    des = [1e-2, 1e-3, 1e-4, 1e-5, 1e-6]
    cnt = np.zeros(len(des)); ncell = 0
    for _ in range(100):
        rd, P = gen_rd(0.0, H0t, g, 0.0, drone=False)
        ratio, _ = cfar_ratio(P)
        for q, p in enumerate(des):
            cnt[q] += int(((ratio > alpha(p)) & VALID).sum())
        ncell += int(VALID.sum())
    out["pfa_check"] = dict(design=des, measured=(cnt / ncell).tolist(), cells=ncell)
    print("pfa check", out["pfa_check"])

    # ---- plots ----
    plt.rcParams.update({"font.size": 10})
    Pz, dets, tr = nominal["kept"]
    vz = np.linspace(40, -40, Pz.shape[0]) if False else None
    rax = np.arange(N) * RES_R
    ii = np.where(np.abs(np.arange(M) - M // 2) * DV <= 40)[0]
    vax = -(ii - M / 2) * DV
    order = np.argsort(vax)
    img = 10 * np.log10(Pz[order] / np.median(Pz) + 1e-9)
    plt.figure(figsize=(8, 4))
    plt.imshow(img, aspect="auto", origin="lower", extent=[rax[0], rax[-1], vax[order][0], vax[order][-1]],
               vmin=0, vmax=np.percentile(img, 99.999))
    plt.colorbar(label="dB above median noise")
    plt.plot(tr["R"], tr["rv"], "o", mfc="none", mec="w", ms=14, label="truth")
    for d in dets:
        if abs(d["vr"]) <= 40:
            plt.plot(d["R"], d["vr"], "x", c="r", ms=8)
    plt.ylim(-40, 40); plt.xlim(0, rax[-1])
    plt.xlabel("range (m)"); plt.ylabel("radial velocity (m/s)\nnegative = approaching")
    plt.title(f"Range-Doppler after clutter removal, t={nominal['frames'][20]['t']:.1f} s (x = CFAR detection)")
    plt.legend(loc="upper right"); plt.savefig("fig_rd_cfar.png", dpi=130, bbox_inches="tight"); plt.close()

    plt.figure(figsize=(6, 3.6))
    cen = (bins[:-1] + bins[1:]) / 2
    for label, v in pdr.items():
        plt.plot(cen, v, "o-", label=f"RCS {label.split('_')[1]} m$^2$")
    plt.ylim(-0.02, 1.05); plt.xlabel("range (m)"); plt.ylabel("detection probability")
    plt.title(f"Pd vs range (Pfa {PFA:g}, 20 runs each)"); plt.grid(alpha=.3); plt.legend()
    plt.savefig("fig_pd_range.png", dpi=130, bbox_inches="tight"); plt.close()

    plt.figure(figsize=(6, 3.6))
    for q in [3, 1, 5]:
        plt.semilogx(rcs_list, pd[:, q], "o-", label=f"Pfa {pfas[q]:g}")
    plt.axhline(0.9, c="gray", ls="--"); plt.xlabel("target RCS (m$^2$)"); plt.ylabel("detection probability")
    plt.title(f"Pd vs target size at {out['pd_vs_rcs_300m']['range_m']:.0f} m"); plt.grid(alpha=.3, which="both"); plt.legend()
    plt.savefig("fig_pd_rcs.png", dpi=130, bbox_inches="tight"); plt.close()

    plt.figure(figsize=(6, 3.6))
    for a in [2, 4, 6]:
        plt.semilogx(pfas, pd[a], "o-", label=f"RCS {rcs_list[a]:.1e} m$^2$")
    plt.xlabel("false-alarm probability per cell"); plt.ylabel("detection probability")
    plt.title("ROC at ~300 m"); plt.grid(alpha=.3, which="both"); plt.legend()
    plt.savefig("fig_roc.png", dpi=130, bbox_inches="tight"); plt.close()

    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    for label, res in mc.items():
        rr = np.array([f["truth"]["R"] for r in res for f in r["frames"] if f["err_pos"] is not None])
        ee = np.array([f["err_pos"] for r in res for f in r["frames"] if f["err_pos"] is not None])
        if len(rr):
            bb = np.arange(0, 361, 40)
            med = [np.median(ee[(rr >= bb[k]) & (rr < bb[k + 1])]) if ((rr >= bb[k]) & (rr < bb[k + 1])).any() else np.nan for k in range(len(bb) - 1)]
            ax[0].plot((bb[:-1] + bb[1:]) / 2, med, "o-", label=label)
    ax[0].set_xlabel("range (m)"); ax[0].set_ylabel("median 3D position error (m)")
    ax[0].set_title("Tracking error vs range"); ax[0].grid(alpha=.3); ax[0].legend()
    tt = [f["truth"]["pos"] for f in nominal["frames"]]
    ee = [f["track"]["pos"] if f["track"] and f["track"]["confirmed"] else [np.nan] * 3 for f in nominal["frames"]]
    tt, ee = np.array(tt), np.array(ee)
    ax[1].plot(tt[:, 0], tt[:, 1], "k-", label="truth")
    ax[1].plot(ee[:, 0], ee[:, 1], "r.", label="confirmed track")
    ax[1].plot(*GNB[:2], "b^", label="6G base station"); ax[1].plot(0, 0, "gs", label="facility")
    ax[1].set_xlabel("x (m)"); ax[1].set_ylabel("y (m)"); ax[1].set_title("Plan view, nominal run"); ax[1].legend(); ax[1].grid(alpha=.3)
    plt.savefig("fig_tracking.png", dpi=130, bbox_inches="tight"); plt.close()

    # nominal run for Phase 3 / dashboard
    def rnd(o):
        if isinstance(o, float): return float(f"{o:.6g}")
        if isinstance(o, dict): return {k: rnd(v) for k, v in o.items()}
        if isinstance(o, list): return [rnd(v) for v in o]
        return o
    meta = dict(gnb=GNB.tolist(), facility_box=[[-30, -25], [30, 25]], fc_hz=I.FC, bw_hz=I.B,
                rcs=0.01, frame_dt=FRAME_DT, pfa=PFA, speed=I.SPEED)
    json.dump(rnd(dict(meta=meta, frames=nominal["frames"])), open("tracks.json", "w"))
    arr = np.stack(exp)
    arr.tofile("rd_frames.bin")
    vs = [-(i - M / 2) * DV for i in range(M // 2 + 17, M // 2 - 18, -1)]
    json.dump(dict(frames=int(arr.shape[0]), rows=int(arr.shape[1]), cols=int(arr.shape[2]), vel=vs,
                   range_max=N * RES_R, db_max=50, t=[f["t"] for f in nominal["frames"]]), open("rd_meta.json", "w"))
    json.dump(rnd(out), open("metrics.json", "w"), indent=1)
    print(json.dumps(rnd(out["monte_carlo"]), indent=1))
    print(f"total {time.time()-t_start:.0f}s")


if __name__ == "__main__":
    main()
