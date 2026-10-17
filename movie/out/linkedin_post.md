# LinkedIn post (DRAFT. Do not publish without explicit go-ahead)

Video: 6g-isac-long.mp4 (about 8:46). Upload 6g-isac-long.srt as the caption file as well (the captions are also burned in).
LinkedIn limits: up to 10 minutes, 5 GB; the picture is cinemascope inside a 16:9 frame so it fits any ratio rule.

---

What if the 6G base station next to a substation could see a small drone, with no radar at all?

I simulated it. A 13 GHz base station senses a drone using the same signal it uses to talk. The track is confirmed at 321 m, about 27 seconds before the fence, with 0.64 m position error (RMS over 20 simulated flights).

Then comes the part I care about most: a governed AI agent. Meta's Llama 3.1 8B proposes actions from a fixed catalog. A policy engine enforces rules. A human approves anything physical. Every step is written to a hash-chained audit log you can verify in your browser.

What the film shows, with spoken narration and captions:
• radio physics: ray-traced substation, 13 GHz, 400 MHz OFDM, range-Doppler, CFAR, Kalman tracker
• the agent: evidence in, structured answer out, policy floors, blocked actions, human approval
• hostile tests: a forged "jam the drone" answer is blocked, an edited log entry breaks the chain
• honest limits: the closest-approach blind zone, hovering drones, and human approval delay

It is a simulation. ISAC is not yet standardized by 3GPP, the drone is a point target, and the angle estimate is modelled at the detected cell. Next step: real radios on an open-source 5G testbed.

Try it yourself (you can play the human approver): https://ai-agentic-enterprises.com/6g-isac/

[PLACEHOLDER, publish ONLY after the user confirms the application is submitted:]
[Also applied this to the Meta Global AI Developer Hackathon. Fingers crossed.]

#6G #ISAC #AIagents #GovernedAI #Llama #CriticalInfrastructure
