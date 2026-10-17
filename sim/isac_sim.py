"""Phase 1: 6G ISAC channel simulation (FR3, 13 GHz, 400 MHz OFDM).

Static clutter comes from Sionna RT ray tracing of the substation. The drone is a
moving point scatterer (radar equation, RCS sigma) added to the channel, because
ray tracing a ~30 cm object at this resolution is unreliable. The base station is
quasi-monostatic: TX and RX panels on the same mast, self-interference assumed
cancelled (direct TX->RX path masked out).
"""
import numpy as np
import torch
import sionna.rt as rt
import scene as S

C = 299_792_458.0
FC = 13e9
LAM = C / FC
B = 400e6
N = 1024                     # subcarriers
DF = B / N                   # 390.625 kHz
TSYM = 1.25 / DF             # OFDM symbol incl. 25% CP = 3.2 us
M = 2048                     # symbols per sensing frame (CPI ~ 6.55 ms)
PT_DBM = 30.0
GAIN_DB = 20.0               # TX and RX panel gain each
NF_DB = 7.0
RCS = 0.01                   # m^2, small quadcopter at 13 GHz
FRAME_DT = 0.5               # s between sensing frames
DEV = "cuda"

GNB = np.array([(a + b) / 2 for a, b in zip(S.GNB_TX, S.GNB_RX)])  # quasi-monostatic point

# drone: straight approach toward the fence, 12 m/s
P_START = np.array([300.0, -200.0, 60.0])
P_END = np.array([0.0, 0.0, 30.0])
SPEED = 12.0


def drone_pos(t):
    d = P_END - P_START
    L = np.linalg.norm(d)
    s = np.minimum(SPEED * np.asarray(t) / L, 1.0)
    return P_START + np.outer(s, d) if np.ndim(t) else P_START + s * d


def static_clutter():
    """Complex channel H0[k] of the empty scene from ray tracing."""
    sc = rt.load_scene(S.write_scene("scene/substation.xml"))
    sc.frequency = FC
    sc.tx_array = rt.PlanarArray(num_rows=1, num_cols=1, pattern="iso", polarization="V")
    sc.rx_array = rt.PlanarArray(num_rows=1, num_cols=1, pattern="iso", polarization="V")
    sc.add(rt.Transmitter("tx", position=list(S.GNB_TX)))
    sc.add(rt.Receiver("rx", position=list(S.GNB_RX)))
    solver = rt.PathSolver()
    paths = solver(sc, max_depth=3, los=True, specular_reflection=True,
                   diffuse_reflection=False, refraction=False, diffraction=False,
                   samples_per_src=1_000_000)
    a, tau = paths.cir(normalize_delays=False, out_type="numpy")
    a = np.asarray(a).reshape(-1).astype(np.complex128)
    tau = np.asarray(tau).reshape(-1).astype(np.float64)
    keep = (tau > 0) & (tau * C > 5.0)           # drop direct TX->RX leakage
    a, tau = a[keep], tau[keep]
    f = np.arange(N) * DF
    H0 = (a[None, :] * np.exp(-2j * np.pi * f[:, None] * tau[None, :])).sum(1)
    H0 *= 10 ** (GAIN_DB / 20)                   # combined sqrt(Gt*Gr) (2 x 20 dB -> 40 dB power)
    return H0, len(a), tau


def noise_sigma():
    p_sub_dbm = PT_DBM - 10 * np.log10(N)
    n_sub_dbm = -174 + 10 * np.log10(DF) + NF_DB
    return 10 ** ((n_sub_dbm - p_sub_dbm) / 20)   # std of complex noise (total)


def gen_frame(t0, H0, rng):
    """Channel matrix Y[m, k] (symbols x subcarriers) for the frame starting at t0."""
    m = np.arange(M)
    t = t0 + m * TSYM
    pos = drone_pos(t)
    R = np.linalg.norm(pos - GNB, axis=1)
    tau = 2 * R / C
    amp = np.sqrt((10 ** (2 * GAIN_DB / 10)) * LAM**2 * RCS / ((4 * np.pi) ** 3 * R**4))
    f = np.arange(N) * DF
    ph = np.exp(-2j * np.pi * (FC + f[None, :]) * tau[:, None])
    echo = amp[:, None] * ph
    sig = noise_sigma()
    noise = (rng.standard_normal((M, N)) + 1j * rng.standard_normal((M, N))) * sig / np.sqrt(2)
    Y = H0[None, :] + echo + noise
    return Y.astype(np.complex64), float(R[M // 2])


def range_doppler(Y):
    """Clutter removal (mean over slow time), IFFT over subcarriers, FFT over symbols."""
    y = torch.from_numpy(Y).to(DEV)
    y = y - y.mean(0, keepdim=True)
    rng_ = torch.fft.ifft(y, dim=1)
    rd = torch.fft.fftshift(torch.fft.fft(rng_, dim=0), dim=0)
    return rd.abs().cpu().numpy()


def rd_axes():
    ranges = np.arange(N) * C / (2 * B)
    vel = -np.fft.fftshift(np.fft.fftfreq(M, TSYM)) * LAM / 2   # negative = approaching
    return ranges, vel


if __name__ == "__main__":
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rng = np.random.default_rng(7)
    H0, npaths, taus = static_clutter()
    print(f"ray-traced clutter paths: {npaths}; |H0| rms {np.sqrt((abs(H0)**2).mean()):.3e}")
    print(f"noise sigma {noise_sigma():.3e}; range res {C/(2*B):.3f} m; max range {C/(2*DF):.0f} m; "
          f"vel res {LAM/(2*M*TSYM):.2f} m/s")
    ranges, vel = rd_axes()
    # truth radial velocity from the trajectory
    rows = []
    for t0 in [0, 5, 10, 15, 20, 24]:
        Y, R_true = gen_frame(t0, H0, rng)
        rd = range_doppler(Y)
        vi, ri = np.unravel_index(rd.argmax(), rd.shape)
        dt = 0.01
        R1 = np.linalg.norm(drone_pos(t0 + M * TSYM / 2 + dt) - GNB)
        R0 = np.linalg.norm(drone_pos(t0 + M * TSYM / 2) - GNB)
        v_true = (R1 - R0) / dt
        med = np.median(rd)
        rows.append((t0, R_true, ranges[ri], v_true, vel[vi], 20 * np.log10(rd.max() / med)))
        print(f"t={t0:>4}s  R true {R_true:7.1f} est {ranges[ri]:7.1f} m | v true {v_true:6.2f} est {vel[vi]:6.2f} m/s | peak/median {rows[-1][-1]:5.1f} dB")
        if t0 == 10:
            sel = np.abs(vel) <= 40
            order = np.argsort(vel[sel])
            img = 20 * np.log10(rd[sel][order] / rd.max() + 1e-12)
            plt.figure(figsize=(7, 4))
            plt.imshow(img, aspect="auto", origin="lower",
                       extent=[ranges[0], ranges[-1], -40, 40], vmin=-60)
            plt.xlabel("range (m)"); plt.ylabel("radial velocity (m/s), negative = approaching")
            plt.title("6G ISAC range-Doppler, t=10 s"); plt.colorbar(label="dB")
            plt.savefig("rd_t10.png", dpi=120, bbox_inches="tight")
    np.savez("phase1_static.npz", H0=H0, taus=taus)
