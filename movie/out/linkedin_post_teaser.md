What if the 6G base station next to a substation could spot a small drone with no radar at all?

I simulated it. A 13 GHz base station senses the drone with the same signal it uses to talk, confirms the track about 27 seconds before the fence (0.64 m position error, RMS over 20 simulated flights), and a governed AI agent, Meta's Llama 3.1 8B, proposes the response. A human approves anything physical. Every step lands in a hash-chained audit log.

This is the 1:47 teaser. The full 6-minute walkthrough shows the engineering behind it:
• architecture diagram: from radio physics to an approved action
• sequence diagram: echo, detections, track, evidence, Llama, policy engine, human, audit log
• workflow diagram: auto, blocked, needs approval, approved, rejected, expired
• snapshots of the real config files and code, with commit IDs
• detection and tracking metrics, and the honest limits

Full video: https://ai-agentic-enterprises.com/6g-isac/watch/
Interactive demo (play the human approver yourself): https://ai-agentic-enterprises.com/6g-isac/

It is a simulation. ISAC is not yet standardized by 3GPP, the drone is a point target, and the angle estimate is modelled at the detected cell.

#6G #ISAC #AIagents #GovernedAI #Llama #CriticalInfrastructure
