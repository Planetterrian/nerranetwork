# Models & Agents
> **Claude Fable 5 delivers a qualitative jump for long-horizon agentic work, letting builders hand off ambitious multi-step projects with less oversight.**

**What You Need to Know:** Anthropic released Claude Fable 5, the same base as Mythos but with added safeguards, posting SOTA results across benchmarks and strong real-world gains on difficult, extended tasks. Cohere open-sourced North Mini Code, a 30B (3B active) agentic coding model under Apache 2.0. Nex-N2-mini, a 35B model purpose-built for autonomous agents, also surfaced today. Watch how quickly teams integrate these into production coding and agent harnesses this week.
---
### Top Story
Anthropic shipped Claude Fable 5, described as the same underlying model as Mythos but with tuned safeguards. Early testers report it handles ambitious, long-running problem-solving sessions far better than prior versions, with the model reliably executing complex tasks across codebases without constant guidance. It posts leading benchmark numbers and feels like a step-change comparable to the Claude 4.5 jump last November. Builders can now attempt larger single-use apps, custom dashboards, or research projects that previously required heavy scaffolding. The main caveats noted are occasional over-triggering safeguards and the usual slow, expensive profile of frontier models. Watch for rapid adoption in agent frameworks and whether Anthropic tunes the safety settings post-launch. Source: [x.com](https://x.com/karpathy/status/2064409694761054332)
---
### Model Updates
**Cohere released North Mini Code: It's first Open-Source Agentic Coding Model — r/LocalLLaMA**
Cohere open-sourced North Mini Code 1.0, a 30B-parameter model with 3B active parameters under Apache 2.0. It scores 33.4 on the Artificial Analysis Coding Index, competitive with similar-sized models for agentic coding tasks. The release includes Hugging Face weights for immediate local or fine-tuned use. Builders working on coding agents should test it this week against closed models on multi-file edit and tool-use benchmarks to see where the efficiency trade-off lands. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1u1za0m/cohere_released_north_mini_code_its_first/)

**Nex-N2-mini: A 35B Model Built for Autonomous Agents — HackerNoon**
Nex-N2-mini is a new 35B model explicitly optimized for autonomous agent workloads. The release positions it as a dedicated agent backbone rather than a general-purpose model. Early positioning suggests stronger long-horizon planning and tool orchestration than dense models of similar size. Developers building production agents should compare it against Qwen and Llama variants on agent-specific harnesses. Source: [Google News](https://news.google.com/rss/articles/CBMijgFBVV95cUxQRlFZajJpbGpQQjQ2Z2djWk8taGQ0X3BwbWxzaEVzU0NKazUxWVFQTFhUbUJNZldHQ29JVUNaaHJnbXRGY2V3b1Zvd3R2Y0ozZTBIUGZwRnl3YWRyeUdNbWVCY2NQd3JmaVVOd1ZEV2g3MmlxaVF4UTZpUGU4cnNIZXRSdUtQdDk2QUVvWlpn?oc=5)

**Qwen3.6-MTP-27B on Tesla V100 @ 55 TPS (llama.cpp) — r/LocalLLaMA**
Users are running Qwen3.6-MTP-27B (Q4_K_M) via llama.cpp on a Tesla V100, achieving 44-55 tokens per second with flags including --spec-type draft-mtp and large context. The setup uses 262k context and parallel batching without quality loss in non-thinking mode. This gives local developers a concrete performance baseline for 27B-class models on older enterprise GPUs. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1u1ygkw/qwen36mtp27b_on_tesla_v100_55_tps_llamacpp_any/)
---
### Agent & Tool Developments
**Microsoft Upgrades Copilot Studio to Build Smarter AI Agents and Workflows — Dawan Africa**
Microsoft updated Copilot Studio with improved agent orchestration and workflow tooling. The changes target more reliable multi-step automation inside Microsoft 365 environments. Teams already using Copilot can now build agents that handle longer task chains with better state management. The upgrade lowers the barrier for enterprises wanting governed agent deployments without custom frameworks. Source: [Google News](https://news.google.com/rss/articles/CBMipwFBVV95cUxNMmIyaTA2QU5JLUMyT3JfMFJRTmoySFVVLXF1X1plQU42aHBvUzEyb3FpNmFodnBpeUtzaUozRFBILUJ3TjZpc2xta3dSNG5VLW5KdkVCZ01qXzhNek1Kc0xuamxlN2M1bm94WTZqcnlQQU9aR1hRZElZTFRodmJVaHBiMzk4Z2hiYWs4Zi1JeS1YZGNfWFUza2Q0UXNsellxcERoNzR0OA?oc=5)

**TabClaw: An Interactive and Self-Evolving Agent for Spreadsheet Manipulation and Table Reasoning — cs.CL updates on arXiv.org**
TabClaw is an open-source agent that ingests CSV or Excel files, clarifies intent, exposes editable plans, and runs parallel specialist agents across multiple tables. It records workflows, extracts user memory, and distills reusable skills from repeated patterns. The system improves task completion on spreadsheet benchmarks while keeping the full execution trace inspectable. Teams doing data analysis should try the ReAct-style loop on their own multi-table datasets. Source: [arxiv.org](https://arxiv.org/abs/2606.10316)

**Global watchdog calls for tighter controls on agentic AI in finance — Reuters**
A global financial watchdog issued new guidance on controlling autonomous AI agents in finance. The focus is on preventing data leakage and unauthorized actions in live trading or customer systems. Institutions running agentic workflows should review current guardrails against the proposed standards before deployment. Source: [Google News](https://news.google.com/rss/articles/CBMiswFBVV95cUxOZjQ0MVEtX0xuUUFuYl90T1RVeVZ1RzZUMXR4a3kzQjFsR2tKSTRWVU9fUUpkZkNfZUgwT0ltWGg2VE1OeUVDTjVMRzdWUE1iTkJUdTRIQ1BVc1l6blRQUUc4dXZxNG1nTUd1R3NLRGhaYWZIRHBrQlRtckxDSUxEbFRuNlA0RDVtUjFkRkpubVVBNTN0SWQ4dVJHbGZkNFMwN3ZrTWdGajhCaDBUdGRJM2d1OA?oc=5)
---
### Practical & Community
**Introducing Papers Without Code [P] — r/MachineLearning**
Hugging Face relaunched paperswithcode.co with automatic parsing of arXiv and HF papers into leaderboards, including closed models like GPT-5.5 and Mythos 5. Users can toggle closed-model results and browse scatter plots plus tables for each benchmark. The site now treats blog posts as valid sources for closed models. Researchers tracking SOTA across domains should add it to their weekly review workflow. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1u1wq0a/introducing_papers_without_code_p/)

**Building a Code Dataset Pipeline from NVIDIA Nemotron-Pretraining-Code-v3 Metadata with Streaming, Pandas, and tiktoken — MarkTechPost**
A new tutorial shows how to stream NVIDIA’s Nemotron code pretraining metadata, reconstruct GitHub URLs, fetch source files, and estimate token counts without full dataset downloads. It covers schema inspection, language distribution, and token-scale estimation using pandas and tiktoken. Developers building custom code pretraining pipelines can follow the exact steps for manageable sampling. Source: [marktechpost.com](https://www.marktechpost.com/2026/06/09/building-a-code-dataset-pipeline-from-nvidia-nemotron-pretraining-code-v3-metadata-with-streaming-pandas-and-tiktoken/)
---
### Under the Hood: Bi-Temporal Memory Engines for LLM Agents
Everyone talks about giving agents “full history” as the safe default for long-running tasks. In practice, replaying every prior turn quickly turns context into noise that hurts accuracy while exploding cost and latency. Engram’s design splits the problem into a fast lossless write path that simply appends episodes and an asynchronous path that extracts atomic facts into a bi-temporal knowledge graph. The graph tracks provenance and supersession chains so contradictions are invalidated rather than deleted. At read time a hybrid retriever fuses dense, lexical, graph, and recency signals, then applies a point-in-time filter to return a compact ~9.6 k token slice. On LongMemEval_S this lean slice scores 83.6 % versus 73.2 % for the full 79 k token history while using roughly one-eighth the tokens. The practical takeaway is to default to retrieved, time-aware facts for any agent that spans more than a handful of turns; only fall back to full replay when the task explicitly requires verbatim earlier dialogue.
---
### Things to Try This Week
- Test Claude Fable 5 on a multi-file refactoring task you previously split across several prompts; note where it maintains context without extra scaffolding.
- Download Cohere North Mini Code from Hugging Face and run it through your existing agentic coding harness to measure tool-call reliability versus closed models.
- Try TabClaw on a three-table financial reconciliation spreadsheet to see how the parallel specialist agents and editable plan surface compare to manual pandas work.
- Add paperswithcode.co to your weekly SOTA check and toggle closed models off to focus on open-weight progress.
---
### On the Horizon
- Further tuning of Claude Fable 5 safeguard sensitivity expected in the coming weeks.
- Additional open agentic coding models from other labs likely to follow Cohere’s release.
- Expanded regulatory guidance on agentic systems in finance and data-handling domains.
- New long-context memory benchmarks that stress bi-temporal retrieval over full-history baselines.