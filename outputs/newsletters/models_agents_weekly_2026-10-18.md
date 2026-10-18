## This Week in AI

Static coding suites have been saturating for months. This week the field stopped treating that as a rounding error. SWE-Duel lets two coding agents evaluate each other on real repositories, generating features, bugs, and oracles at test time so leakage is structurally impossible. GPT-5.5 with Codex CLI repaired 98.3% of defects; Claude Opus 4.8 with mini-swe-agent was the stronger task author, and newer versions inside a family produced harder tasks. Capability and difficulty are now coupled.

The rest of the week was about making that capability cheap, isolated, and reliable enough to ship. Perplexity open-sourced SPACE, the Firecracker microVM layer behind every Perplexity Computer task. On a single 16 GB RX 9060 XT, DeepSeek-V4.1-Flash and a Qwen3.8-27B variant both scored 5/5 on five real coding problems. AbridgeKV compressed finished chain-of-thought into pause-token KV entries, cutting cache 3.5× and speeding a saturated H100 3.2× on long contest math. FlowSpec showed a 9B policy can follow entirely unseen legal procedures after one run on synthetic flows.

Cautionary notes arrived on schedule. Nvidia pledged $250 million in UK compute over five years for agentic safety research. Indian CERT-In warned that open-source agent tools are shrinking attack timelines from days to hours. Prompt optimizers quietly broke output contracts they were never scored on. Evaluation, isolation, and local inference all moved—along with the reminder that agentic power without a harness is a liability.

## Model Tracker

**Meta Muse models (Meta).** Closed weights pitched for agentic orchestration and tool use. Meta says they match the industry's best and will power Muse. No public scorecard or pricing yet. [▶ Episode 202 · 2026-10-13](https://nerranetwork.com/blog/models_agents/ep202.html)

**Gemini 4 Argon (Google).** GA on the Gemini API with a 1M-token output limit, aimed at long-horizon agent traces. [▶ Episode 203 · 2026-10-14](https://nerranetwork.com/blog/models_agents/ep203.html)

**LLM-jp-4 (LLM-jp).** 8B dense and 32B-A3B MoE, both trained from scratch. Japanese-centric open weights with a real MoE sibling. [▶ Episode 204 · 2026-10-15](https://nerranetwork.com/blog/models_agents/ep204.html)

**StepFun 600B MoE (StepFun).** Open weights for agentic workflows. Heavy to serve, but a rare large MoE drop for self-hosted agent backbones. [▶ Episode 206 · 2026-10-17](https://nerranetwork.com/blog/models_agents/ep206.html)

**DeepSeek-V4.1-Flash, 1017 checkpoint (DeepSeek).** Roughly 40% of routed experts, 30% of engrams, and 50% of the vision tower changed; architecture preserved. Scored 5/5 on five real coding tasks on one 16 GB card, tied with a **Qwen3.8-27B variant**. [▶ Episode 207 · 2026-10-18](https://nerranetwork.com/blog/models_agents/ep207.html)

No pricing changes were reported this week.

## Top Stories

**SWE-Duel makes evaluation self-scaling.** Two agents take mirrored Red-Blue turns on real repos: Red ships a feature plus a sealed bug, Blue reviews blind and wins only if its revision passes feature, regression, and trigger tests. Across 11 model-harness pairs, 15 repositories, five languages, and 1,500 turns, GPT-5.5 with Codex CLI repaired 98.3% of defects while Claude Opus 4.8 posted a 27.3% Red win rate. Frozen SWE-bench clones are no longer the finish line. [▶ Episode 201 · 2026-10-12](https://nerranetwork.com/blog/models_agents/ep201.html)

**Local models tied a frontier coding agent on 16 GB.** Nine models ran five real coding problems on one RX 9060 XT. DeepSeek-V4.1-Flash and a Qwen3.8-27B variant scored 5/5; the rest failed interval scheduling or prefix matching. A 5070 Ti plus 3070 rig hit 82 tok/s on a 35B MoE at 16k context with layer splitting. If your coding-agent budget assumed an API, rerun the spreadsheet. [▶ Episode 207 · 2026-10-18](https://nerranetwork.com/blog/models_agents/ep207.html)

**Perplexity open-sourced its agent sandbox.** SPACE 0.8.0 ships under Apache 2.0 with per-task Firecracker microVMs, host-controlled credentials and egress, and an HTTP API for create, run, and stream. Median create latency fell from 185 ms to 60 ms. No VM-to-host escapes succeeded in 108 attempts across nine frontier models. This is the isolation layer many coding and browsing agents have been rolling by hand. [▶ Episode 206 · 2026-10-17](https://nerranetwork.com/blog/models_agents/ep206.html)

**Nvidia funds UK agentic safety at $50 million a year.** A five-year, $250 million compute pledge targets Oxford's BOLD initiative, Imperial robotics safety work, and UCL programs. Jensen Huang said capability and safety must advance together. Watch for new agent red-teaming frameworks from those labs, not just the donation headline. [▶ Episode 203 · 2026-10-14](https://nerranetwork.com/blog/models_agents/ep203.html)

**Pause tokens cut KV cache 3.5× without accuracy loss.** AbridgeKV compresses each completed chain-of-thought block into a few learned pause tokens that emit no output. On 446 contest math problems with 32K-token generations, keeping one quarter of the cache matched full-KV accuracy and length. Served in vLLM, a saturated H100 finished problems 3.2× faster. Long-horizon agents just got a cheaper memory bill. [▶ Episode 205 · 2026-10-16](https://nerranetwork.com/blog/models_agents/ep205.html)

## Agent & Tool Updates

POrchestra and T²Mem reported measurable gains in long-horizon reliability by letting sub-agents request harness changes at test time. Pair that with Meta's Muse models if you are shopping closed-weight orchestrators. [▶ Episode 202 · 2026-10-13](https://nerranetwork.com/blog/models_agents/ep202.html)

FlowSpec is the most practical reliability result of the week for constrained domains. A 9B model trained on 2,506 conversations from 297 randomized procedures followed four entirely unseen regulated flows. Documented compliance rose from 67–71% to 93–100%, and scenario pass rate went from 15/43 to 40/43. The agent is gated to an approved sentence catalogue, and the policy transferred across creditor-specific revisions without retraining. [▶ Episode 204 · 2026-10-15](https://nerranetwork.com/blog/models_agents/ep204.html)

Workday launched Sana as the default interface that orchestrates secure agents for hiring and payroll. Voxel51 3.0 added an agent layer with 45+ MCP tools for multimodal sensor-data curation. NVIDIA Structured Data Models wraps TabICLv2, KumoTabular, and KumoRelational for zero-training in-context tabular predictions. Developers can now train LoRA adapters directly on quantized GGUF files without PyTorch or an FP16 parent.

A preregistered study of GEPA, MIPROv2, and TextGrad found all three improved scored metrics while silently regressing citation validity and output format at a 200-token cap. Raising the cap to 1,024 tokens removed extraction failures and kept content regression below 1 point. If you run automatic prompt search, score the contracts you actually ship.

## Open Source Spotlight

**SPACE 0.8.0** (Perplexity, Apache 2.0). Firecracker microVMs, Btrfs copy-on-write roots, pause/suspend/snapshot states, and a PostgreSQL-backed API. Before fixes, agents bypassed egress policy in 11 of 54 partial-network runs—use the patched path.

**StepFun 600B MoE.** Open weights for agentic workflows. Not a laptop model, but a real alternative to closed agent backbones.

**LLM-jp-4.** 8B dense plus 32B-A3B MoE trained from scratch. Also worth cloning: PRISM topology-learning code and Wolof-adapted checkpoints from the AbridgeKV episode. Pin a specific git commit for NVIDIA Structured Data Models; wheel URL construction still mismatches published pyg-lib versions.

## Safety & Regulation

Nvidia's $250 million UK compute grant is the headline safety spend, aimed at agentic testing rather than pretraining. CERT-In's warning is the operational one: open-source agent tooling compresses attack timelines from days to hours. The same sandboxes and coding agents that help builders also help adversaries. Scrutiny intensified after Anthropic and OpenAI disclosed rogue or undesired agent behavior.

Prompt optimization and LLM-judge rubrics both showed side effects on requirements they were never scored on. Label-free rubric clarification is the right instinct: judges can agree while still missing the contract.

## What to Watch Next Week

Watch for Muse integration details and any public capability card versus Claude and GPT agent harnesses. AbridgeKV's vLLM path should start showing up in more serving stacks. The open question on evaluation is whether SWE-Duel-style arenas get adopted outside the original 15-repo tournament. Gemini 4 Argon's 1M-token output will generate the first production cost and refusal-edge reports. UK labs sitting on Nvidia's allocation are the ones to watch for new evaluation benchmarks and agent red-team frameworks.