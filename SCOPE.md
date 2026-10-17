# 6G ISAC digital twin: drone intrusion at a critical facility

Scoped 2026-10-17. Simulation only; ISAC is not yet standardized by 3GPP (Rel-20 study), so label the demo as such.

## What it demonstrates
A simulated 6G base station senses an unauthorized drone near a critical facility using only its communication signal (no separate radar). A governed AI agent proposes a response; a human approves before anything happens.

## Design
1. **Scene and radio**
   - Power substation scene from OpenStreetMap -> Mitsuba/Sionna RT (buildings, fences, metal structures = clutter).
   - Band: FR3 ~13 GHz, 400 MHz bandwidth (~0.4 m range resolution). Sub-THz is a stretch goal.
   - Waveform: OFDM.
2. **Sensing simulation**
   - Sionna RT for static multipath/clutter.
   - Drone = moving point scatterer with set RCS and velocity added to the channel (ray tracing a 30 cm object is unreliable; hybrid is the honest approach).
   - Output: channel response per OFDM symbol.
3. **Sensing pipeline (GPU)**
   - Static clutter removal, 2D FFT range-Doppler, CFAR detection, Kalman tracking.
   - Metrics: Pd vs Pfa, range/velocity error, tracking error.
4. **Governed agent** (reuse existing approval-gate pattern)
   - Input: track (position, speed, heading, confidence).
   - Tools: check no-fly-zone/policy file, check registered flights, draft response (alert security, cue camera, prioritize slice).
   - Human approval gate; full audit log. LLM = Gemini via vertex-gateway.
5. **Dashboard**: map + track, range-Doppler heatmap, approval queue, audit trail. Runs on precomputed outputs so the public demo needs no GPU.

## Phases
| Phase | Work | Output |
|---|---|---|
| 0 | Check AWS balance + GPU quota, launch one g6.xlarge, install Sionna | Working environment |
| 1 | Scene + channel simulation with moving target | Raw channel data |
| 2 | Range-Doppler, clutter removal, CFAR, tracking | Detection plots + metrics |
| 3 | Governed agent with approval gate + audit log | Working workflow |
| 4 | Dashboard, deploy to Contabo (/6g-isac/) | Live demo |
| 5 | Demo video, LinkedIn post | Published |

## Cost
~60-100 GPU hours on one L4 (g6.xlarge, ~$0.80/hr) = ~$50-100 of the $9k AWS credit. Box stopped when idle. GCP only for Gemini calls. Nothing depends on the Dec 16 2026 GCP expiry.

## Regulatory angle
- Drones: US FAA Remote ID, EU U-space/EASA, India Drone Rules / Digital Sky.
- Sensing data can be personal data: GDPR, India DPDP Act, US privacy law; data minimization + retention policy.

## Success criteria
- Pd > 90% at a stated false-alarm rate, plotted vs SNR and range.
- Range error < 1 m; tracking error reported.
- Every agent action traceable in the audit log; no action without approval.

## Risks
- Sionna RT / Mitsuba / OptiX need a working NVIDIA driver on the instance.
- If the drone RCS is too small for long-range detection, report it honestly.

## Defaults
Facility: power substation. Band: 13 GHz / 400 MHz. Code: private repo on AI-Agent GitHub account.

## Phase 0 status (2026-10-17): DONE
- Account 632393508307 (profile `enterprises`), us-east-1, G/VT quota 8 vCPU.
- Instance `isac-sim` (g6.xlarge, NVIDIA L4, DLAMI Ubuntu 22.04, 150 GB), ids in aws.env. SSH key = id_ed25519_aws_devbox, SG open to the launch IP only (update if IP changes). Left STOPPED.
- Venv `~/isac`: Sionna 1.2.2, sionna-rt, torch (CUDA true), Mitsuba cuda_ad_mono_polarized variant loads, sample scene loads. "jitc_llvm_init failed" warning is harmless (CUDA backend works).
- Not verified: remaining credit balance (no API for it; check the Billing console credits page).

## Phase 1 status (2026-10-17): DONE (plot regeneration pending)
- Code in sim/: scene.py (procedural substation, cuboids; ITU ground materials are undefined at 13 GHz so ground = concrete), isac_sim.py (ray-traced clutter + point-target drone echo, range-Doppler).
- Params: 13 GHz, 400 MHz, 1024 subcarriers, 2048 symbols/frame -> 0.375 m range res, 384 m max range, 1.76 m/s velocity res.
- Ray tracing gave 15 clutter paths (specular, depth 3). Drone approach 300 m -> ~13 m at 12 m/s.
- Single-frame peak vs truth: range error <= 0.2 m at all test times; velocity within one bin (-12.32 est vs -12.0 true); peak/median 28 dB at 299 m up to 85 dB at 13 m.
- Simplifications: point-target drone (RCS 0.01 m^2), 40 dB combined antenna gain applied to all paths, no drone-ground multipath, no beam steering.
- TODO: rd_t10.png in sim/ is the old unzoomed plot; the script now crops to +-40 m/s, rerun to refresh. Instance isac-sim is STOPPED (aws.env IP changes on each start).

## Phase 2 status (2026-10-17): DONE (one cosmetic rerun pending)
- Geometry changed: drone now approaches from (300,-200,60) to (0,0,30) at 12 m/s (30 s, range 333 m -> 22 m min); old line passed ~6 m over the mast. Phase 1 numbers were from the old line and are superseded.
- sim/pipeline.py: Hann-windowed range-Doppler, 2D CA-CFAR (616 training cells, Pfa 1e-6), parabolic peak interpolation, 16x8 panel angle estimate (modelled at the detected cell, per-element noise), EKF tracker with 3-hit confirmation. Outputs: metrics.json, tracks.json (nominal run, input for Phase 3/dashboard), fig_*.png.
- Results (20 Monte Carlo runs, RCS 0.01 m^2): first detection at 333 m, track confirmed at ~321 m (3 frames, ~1.5 s) in 20/20 runs, i.e. ~27 s before the drone reaches the facility. 3D position RMSE 0.64 m (p90 1.07 m), velocity RMSE 0.81 m/s. Error grows with range (median ~1.3 m at 340 m).
- RCS 0.001 m^2 (small drone): still 20/20 confirmed at ~321 m; position RMSE 1.7 m, median ~3 m at 300+ m.
- Minimum RCS for Pd >= 0.9 at ~300 m: 6e-4 m^2 at Pfa 1e-4, 1e-3 m^2 at Pfa 1e-6/1e-8.
- Pfa check on 2e8 noise-only cells: measured 1.05e-2 / 1.1e-3 / 1.0e-4 vs design 1e-2 / 1e-3 / 1e-4 (1e-5 and 1e-6 lost to JSON rounding; earlier unwindowed run gave 8.8e-7 at design 1e-6).
- False detections ~2.9/frame (design load: 1e-6 x 2e6 cells); tracker rejected them in all runs, but false-track rate is not yet measured. Use Pfa 1e-8 for a quieter operating point.
- Honest limits: closest approach (~22 m, tangential) puts the drone inside the zero-Doppler notch -> 2 of 7 frames missed there (Pd 0.71 in the 0-30 m bin); a hovering drone would be invisible to static-clutter removal (rotor micro-Doppler not modelled); angle estimation is modelled at the detected cell, not a full array simulation.
- TODO next GPU session: rerun `python pipeline.py` to refresh fig_rd_cfar.png (axis fix) and metrics.json (rounding fix). Instance STOPPED.

## Hackathon requirements (relayed 2026-10-17 from the Meta hackathon session; applications close Oct 25, judging Nov 4-8)
Scoring: Impact 30%, Demo 25% (incl. video quality), Use of Meta AI tooling 25%, Technical depth 20%.
- Two videos, each with a NEW look recorded in the contabo style registry (/opt/ai-digest/style_registry), self-intro only at the end:
  1. LinkedIn cut: short, movie-style with entity captions (ground station, drone, human in the loop...), Blender-rendered from tracks.json.
  2. Judge cut: problem + workflow first, then architecture/setup, then live screens: range-Doppler, Pd vs Pfa, range/tracking error, approval-gated agent + audit log. Length limit unknown -> build as modular segments that cut to ~3 min and ~5-6 min. No padding.
- Dashboard (Phase 4) must show those live screens so they can be screen-recorded.
- Keep public demo alive through ~Nov 9: precomputed outputs only, GPU box stopped after the final run, cached agent responses replayed, any live agent call rate-limited, plus a fallback narrated recording. Label: simulation only; ISAC not yet standardized by 3GPP.
- OPEN: "Use of Meta AI tooling" is 25% of the score and the planned agent LLM is Gemini via vertex-gateway. Decision needed from the user: run the agent on a Meta model (Llama) instead. Not yet decided.

## LinkedIn post rule (relayed 2026-10-17)
- Post text may include a light "fingers crossed" line saying the solution has been applied to the Meta Global AI Developer Hackathon, but the application is NOT submitted yet (needs the user's Cerebral Valley login + final click). Keep it as a PLACEHOLDER; publish only after the user confirms submission. Wording: "applied", never "accepted/selected/won".
- Nothing is posted to LinkedIn without the user's explicit go-ahead.

## Phase 3 status (2026-10-17): DONE
- Agent LLM = Meta Llama 3.1 8B Instruct (Ollama 0.40.5 on the isac-sim L4; 5-7 s per call). Chosen by the user for the hackathon "Meta AI tooling" criterion. The laptop has its own Ollama on :11434, so tunnel the box to local port 11435 (OLLAMA_URL=http://127.0.0.1:11435).
- agent/: policy.json (zones, action catalog, never-executable list, minimum actions by threat level and by zone), registry.json, audit.py (hash-chained JSONL, tamper detection), llm.py (Llama client, cache llm_cache.json, modes live | cache-first | replay, rate limit), agent.py (evidence tools -> Llama proposes -> policy engine governs -> scripted human approval -> simulated execution -> audit).
- Outputs: agent/audit.jsonl (48 entries, chain valid), agent/out/incident_timeline.json + agent_metrics.json (dashboard feed), agent/audit_inject.jsonl + out_inject/ (injection variant).
- Verified: selftest passes (hostile output: threat raised to critical, jam_or_spoof_drone blocked, unknown action blocked, tamper detected). Replay mode reproduces the live run with 4/4 cache hits and the same event sequence, no GPU needed.
- Storyline (scripted human decisions): track confirmed t=1.0 s at 349 m; camera cue approved at +3 s (23.5 s before the fence); patrol dispatched (14.0 s lead); airspace authority alerted (2.0 s lead); police escalation first REJECTED, then approved only after the fence line (-2.0 s). Finding: human approval latency eats most of the lead time late in the flight.
- Honest limits: Llama's rationale sometimes misstates the zone (the grounding check flagged it at t=9.5 s, it does not fix it); injection test is one run, Llama ignored the planted note, and the real protection is the deterministic registry match; human decisions are scripted for the recording.
- Phase 2 refresh: with windowing, measured Pfa at design 1e-6 is 1.37e-6 (windowing correlates cells). Figures regenerated, including fig_rd_cfar.png.
- Instance STOPPED. Llama weights stay on its disk.

## Phase 4 status (2026-10-17): DONE, LIVE at https://ai-agentic-enterprises.com/6g-isac/
- site/ (static: index.html + data/), built by build_site.py from sim/new/ + agent/ outputs. Deployed by rsync to contabo-tally:/var/www/6g-isac/ and a Caddy route (/6g-isac -> file_server) added to /etc/caddy/Caddyfile; backup at /etc/caddy/Caddyfile.bak-6g-20261017. To redeploy: `python3 build_site.py && rsync -az --delete -e ssh site/ contabo-tally:/var/www/6g-isac/`.
- Pure static, no backend, no GPU, no live LLM calls: Llama replies are the cached recorded run, so nothing to rate-limit; cost is zero beyond the existing VPS. Keep it up through ~Nov 9.
- Panels: site plan with zones, range-Doppler heatmap (real per-frame maps from the L4 run, CFAR detections + truth ring), track panel, governed-agent timeline (Llama rationale, policy notes, approval cards), hash-chained audit log, metrics tabs (Pd vs range, Pd vs target size, ROC, tracking error, summary).
- Interactive: "Be the operator" mode (viewer approves/rejects in real time, 20 s expiry, own client-side hash chain); "Verify chain" recomputes SHA-256 in the browser (verified: 48 entries intact; "Tamper with entry 20" breaks it at #20).
- Recording views for the videos: ?view=map|rd|agent|audit|metrics (single full-width panel, canvas capped at 1000 px), ?autoplay=1, default speed 2x, scrubber for retakes.
- Verified: no console errors locally and on the live URL; pitfall fixed: Play before the 2 MB data loads (guarded).
- Caveats: the 2 MB rd_frames.bin loads on first visit; ROC and tracking charts are from the Monte Carlo run, the map/RD/track/agent panels replay the nominal run (seed 0); recorded operator is scripted.
- Next: Phase 5 = two videos (LinkedIn movie cut in Blender + judge cut from screen recordings of the dashboard), each with a new look recorded in contabo /opt/ai-digest/style_registry; fallback narrated recording; LinkedIn post stays a placeholder until the user confirms the Meta application is submitted. GPU box is stopped; gpu_export.sh reruns the pipeline if numbers must be regenerated.

## Phase 5 status (2026-10-17): DONE
- Film "dusk-neon-cinemascope-narrated" (registered in contabo style registry). Two cuts in movie/out/: 6g-isac-judge.mp4 (4:13) and 6g-isac-long.mp4 (8:46, under LinkedIn's 10 min limit), each with burned-in captions + .srt, Gacrux TTS narration, synthesized music bed ducked under voice. Drafts: linkedin_post.md (hackathon line is a PLACEHOLDER until the user confirms the Meta application is submitted), judge_submission.md.
- Build: movie/{script,common,cards,dash,build,world,render}.py; 3D from Blender 4.5.14 Cycles on the isac-sim L4 (frames rendered 2026-10-17); GPU box STOPPED at the end; gpu_up.sh / gpu_stage2.sh / gpu_export.sh exist.
- Known flaws: dashboard text on the control-room monitors is mirrored in the s6 shots (texture UV flip; fix = flip movie/screens/*.png and re-render cuts s6c1-s6c3 on the GPU); drone enlarged x7 (stated on the end card); no public rule on hackathon video length was found, judge cut length is my choice.
- Not done: videos not posted anywhere; not hosted on the demo page as a fallback recording.

## Phase 5 update (2026-10-17, v2 of the films)
- Feedback applied: no double captions (SRT renamed so players do not auto-load it next to the burned-in version; dashboard footnotes hidden in cutaways; callouts now collision-aware; opening title kept clear), plus engineering-proof segments: sequence diagram, workflow diagram, config snapshots, code snapshots (policy engine, audit chain, detector), repo/commit card with real git log and selftest result.
- Repo: private GitHub repo YuvarajAravindan-AI-Agent/6g-isac-facility-guard, 7 commits on main (latest b1c0058 at video time), repo-local git identity (not the IITM one). Pushed over HTTPS via gh credentials; SSH key is not linked to that account.
- Cuts: out/6g-isac-judge.mp4 (6:26), out/6g-isac-long.mp4 (8:58, under LinkedIn's 10 min). Long cut dropped l1, l4, l8, l10, l11 to make room. Not posted anywhere.
- GPU box stayed stopped for this round (CPU-only rework).

## Posted (2026-10-17)
- LinkedIn teaser POSTED by the user's request: https://www.linkedin.com/feed/update/urn:li:activity:7517255221149003776/ . Video = movie/out/6g-isac-teaser-9mb.mp4 (1:47, 1280x720, 8.5 MiB; the Chrome upload tool caps files at 10 MB; the 1080p 20.7 MiB version is out/6g-isac-teaser-lite.mp4). Text = movie/out/linkedin_post_teaser.md, no Meta hackathon line (application not submitted).
- Judge cut hosted: https://ai-agentic-enterprises.com/6g-isac/watch/ (page) and /6g-isac/media/6g-isac-judge.mp4 (raw). site/media/ is git-ignored; redeploy with rsync WITHOUT --delete issues because media lives in site/.
- Long cut (8:58) not posted anywhere.
