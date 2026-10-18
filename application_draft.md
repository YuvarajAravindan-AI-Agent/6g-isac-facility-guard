# Meta Global AI Developer Hackathon: application draft (startup track)

Status: DRAFT. The real question wording is behind the Cerebral Valley login; reshape these to fit. Scored on two equal criteria: project idea, and technical skill shown.

Track: Startup
Theme: Push the Frontier (secondary fit: Build for Your World)

## Project idea (short)
6G networks will sense as well as communicate. A base station can detect an unauthorized drone near a critical facility using only its communication signal, with no separate radar. The hard part is not detection but what happens next: an AI agent that proposes a response must not act on its own in a regulated, safety-critical setting.

I built and ran this as a simulation: a 13 GHz, 400 MHz OFDM base station senses a drone approaching a power substation, and a governed agent proposes responses (cue camera, dispatch patrol, alert airspace authority, escalate to police). A deterministic policy engine bounds what the agent may propose, a human approves or rejects every action, and every step lands in a hash-chained audit log. For the hackathon I will extend it with Meta models: Llama for the agent today, SAM 3.1 for camera-cued visual confirmation of the sensed track, and Muse Spark for planning, benchmarked against the Llama baseline.

Honest scope: simulation only. ISAC is not yet standardized by 3GPP (Rel-20 study item).

## Why it fits the theme
It gives a machine a new capability (sensing with the comms signal) and addresses a physical-system control problem (facility protection) with a governed human-in-the-loop design that regulators can audit (FAA Remote ID, EU U-space, India Drone Rules; GDPR and DPDP for sensing data).

## What I built (technical skill)
Everything below is working and linkable.
- Radio and sensing simulation on an NVIDIA L4: Sionna ray tracing of a substation scene (15 clutter paths), a point-target drone echo, OFDM channel. 0.375 m range resolution, 384 m max range.
- Detection pipeline: Hann-windowed range-Doppler, 2D CA-CFAR (Pfa 1e-6), parabolic peak interpolation, EKF tracker with 3-hit confirmation.
- Measured results (20 Monte Carlo runs): track confirmed at about 321 m in 20/20 runs, roughly 27 s before the drone reaches the facility. 3D position RMSE 0.64 m, velocity RMSE 0.81 m/s. Minimum target size for Pd of at least 0.9 at 300 m reported. Measured Pfa checked on 2e8 noise-only cells against the design value.
- Governed agent: Meta Llama 3.1 8B Instruct (Ollama on the GPU) calls evidence tools and proposes actions; a deterministic policy engine blocks anything outside an action catalog; scripted human approval; hash-chained audit log with tamper detection (self-test passes: hostile output blocked, tamper detected).
- Limits I report openly: a hovering drone is invisible to static-clutter removal, the closest tangential pass falls in the zero-Doppler notch (Pd 0.71 in that bin), the agent's rationale sometimes misstates the zone (the grounding check flags it), human approval latency eats most of the late-flight lead time.
- Earlier shipped work on the same governed-agent pattern: approval-gated Odoo agent, OPA-gated cloud agent (Terraform on AWS and GCP), governed SAP HANA/CAP stock agent with audit trail, K-1 tax bridge.

## Links
- Live demo (static replay, runs without a GPU): https://ai-agentic-enterprises.com/6g-isac/
- Judge walkthrough video: https://ai-agentic-enterprises.com/6g-isac/watch/
- LinkedIn teaser: https://www.linkedin.com/feed/update/urn:li:activity:7517255221149003776/
- Code (governed cloud agent): https://github.com/YuvarajAravindan-AI-Agent/governed-cloud-agent
- Code (SAP governed sandbox): https://github.com/YuvarajAravindan-AI-Agent/sap-gov-sandbox
- SAP walkthrough: https://ai-agentic-enterprises.com/sap-demo/
- K-1 tax bridge: https://ai-agentic-enterprises.com/k1-bridge/
- Company: https://ai-agentic-enterprises.com
- The 6G repo (YuvarajAravindan-AI-Agent/6g-isac-facility-guard) is private; make it public first if you want to list it.

## Not claimed
No acceptance, no prizes, no claim that Muse Spark or SAM 3.1 is already integrated (the agent runs on Llama 3.1 8B today).
