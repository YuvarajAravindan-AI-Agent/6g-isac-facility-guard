# Judge submission text (draft)

**Title:** 6G ISAC Facility Guard: network sensing, governed by a human

**One line:** A simulated 6G base station senses a drone using its own communication signal, and a Meta Llama agent proposes responses that a human approves and a tamper-evident log records.

**Demo video:** 6g-isac-judge.mp4 (about 4:13, captions burned in; SRT included). Live demo: https://ai-agentic-enterprises.com/6g-isac/ (play the operator yourself; no login).

**Problem.** Small low-flying drones are a blind spot for critical sites, and real 6G hardware tests are costly or impossible today. 3GPP is still studying ISAC, so simulation is the only way to explore it now.

**What we built.**
1. Radio simulation: ray-traced substation (Sionna RT), 13 GHz, 400 MHz OFDM, moving point target (100 cm²), 20 Monte Carlo flights.
2. Sensing pipeline on GPU: clutter removal, range-Doppler, CA-CFAR, angle estimate (16x8 panel), Kalman tracker with 3-hit confirmation.
3. Governed agent: deterministic evidence tools, **Meta Llama 3.1 8B (Ollama, local)** proposes actions from a 7-action catalog, a policy engine enforces floors/minimums/blocks, a human approves physical actions, a SHA-256 hash-chained audit log records everything and verifies in the browser.
4. Dashboard: static page that replays the recorded run (no GPU, no live model calls), with an interactive "be the operator" mode.

**Results (simulation, 20 flights).** Track confirmed at 321 m (about 27 s before the fence) in 20/20 runs; 3D position error 0.64 m RMS; speed error 0.81 m/s RMS; smallest target detected 90% of the time at 300 m: about 10 cm² at a 1e-6 false-alarm design. Measured false-alarm rate 1.4e-6 vs 1.0e-6 design, reported as measured.

**Use of Meta AI tooling.** Llama 3.1 8B is the agent's reasoning engine, run locally so no incident data leaves the site. Its answers are structured JSON; its mistakes are caught (a grounding check flagged a wrong zone claim; a policy floor overrode an under-reaction).

**Technical depth / honesty.** Limits are stated in the video: closest-approach Doppler blind zone, hovering drones invisible to clutter removal, angle estimate modelled at the detected cell, drone is a point target, scripted human decisions in the recording, ISAC not yet standardized.

**Impact.** Substations, ports and airports are regulated (aviation rules such as Remote ID, privacy law because sensing data can be personal data). Propose, approve, prove is how AI earns a place there.
