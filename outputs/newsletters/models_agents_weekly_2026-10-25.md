## This Week in AI

Agents stopped being a research sidebar this week. They started looking like a business.

Cognition's Devin now commits 89% of the code its own engineers commit, the company crossed a $1bn annualised revenue run-rate at a $48bn valuation, and enterprises from Goldman Sachs to Mercedes-Benz are using it for full-cycle work—including COBOL modernisation at more than 200,000 lines. That is not a demo metric. [▶ Episode 209 · 2026-10-20](https://nerranetwork.com/blog/models_agents/ep209.html) On the model side, Moonshot released Kimi K3.1 Pro, a 2.8T-parameter MoE with 104B active parameters and a 1M-token context window that posts near-frontier coding and agent scores, with API access live and open weights promised November 4. [▶ Episode 213 · 2026-10-24](https://nerranetwork.com/blog/models_agents/ep213.html) Microsoft Research open-sourced Agensh, a harness with no central orchestrator that scaled from 1 to 1,024 coding agents on ProgramBench. [▶ Episode 214 · 2026-10-25](https://nerranetwork.com/blog/models_agents/ep214.html)

The other current is compression. Frozen 16 MB embedding tables let ternary 46 MB models hit 615–740 tokens/sec on laptop CPUs while matching float baselines on LAMBADA and PIQA. Frozen Gemma 4 audio encoders matched commercial Arabic ASR on character error while running 3.4× faster on CPU. OpenAI shipped a Decisions API that turns low-cost calls into schema-faithful JSON. And Andrej Karpathy noted that RL post-training is producing coherent chain-of-thought that no longer relies on English—internal reasoning that will break audit pipelines still expecting natural language. [▶ Episode 210 · 2026-10-21](https://nerranetwork.com/blog/models_agents/ep210.html)

The field moved on three axes at once: commercial agents, open-weight frontier models, and genuinely small on-device stacks. The hype is the usual; the artifacts are not.

## Model Tracker

**Kimi K3.1 Pro — Moonshot.** 2.8T MoE, 104B active, 1M context. Reports 65.7% on Terminal-Bench 4.0, 51.7 on SWE-Marathon, 64.4 on OfficeQA Pro v2. Artificial Analysis scores it at 55, ahead of Claude Fable 5.1, GPT-6 Astra, and Gemini 4 Argon. Pricing is $2 per million input tokens and $10 per million output, matching GPT-6.1 Sol and half of Claude Opus 5.5. A Highspeed variant generates 2–3× faster at twice the price. Open weights are due November 4.

**Nemotron 3.5 Bolt E4B — NVIDIA.** An 8B / 4B-effective small model post-trained from Gemma 4 E4B for local voice agents, game characters, and robots targeting 4 GB VRAM.

**BitNet b1.58 with frozen embeddings — research.** The full model fits in 46 MB, ties the float baseline on LAMBADA and PIQA, and runs at 615–740 tok/s on a laptop CPU in 62 MB of memory—five to six times faster than 8-bit GGUF at roughly one-seventh the RAM.

**baseVultra — research.** A compact nonlinear recurrent cell that reallocates capacity toward a dense candidate-generation matrix. It hits 1.594 validation loss at 200K parameters on TinyShakespeare, beating matched LSTM and GRU baselines in constrained hidden-state regimes.

## Top Stories

### Devin writes 89% of Cognition's code
Cognition reported that Devin now commits 89% of its own engineering output and crossed $1bn ARR on 25 September 2026 after raising more than $2bn at a $48bn valuation. CEO Scott Wu places current capability between junior and mid-level; humans still review every commit. Enterprise customers include Goldman Sachs, Mercedes-Benz, GE Aerospace, and Nubank, with distribution through Infosys, Cognizant, and AWS. Nubank reported 8–12× efficiency on large migrations. Practical implication: this is a staffing and modernisation line item, not a prototype. [▶ Episode 209 · 2026-10-20](https://nerranetwork.com/blog/models_agents/ep209.html)

### Kimi K3.1 Pro sits near the closed frontier
Moonshot's post-trained Kimi K3 applies large-scale joint RL across hundreds of domains after rebuilding the RL framework, long-context inference, sandboxing, and rollout scheduling. It matches or exceeds Claude Opus 5.5 and GPT-6 Astra on several coding and finance tasks, and Moonshot also shipped Kimi Hosted Agents for 24/7 multi-agent work. Independent evals will matter more than the launch deck, but pricing at GPT-6.1 Sol levels means you can run a bake-off this week instead of waiting for weights. [▶ Episode 213 · 2026-10-24](https://nerranetwork.com/blog/models_agents/ep213.html)

### Frozen embeddings make 46 MB models laptop-native
Researchers replaced a Gemma-shaped 270M model's learned embedding table with a frozen 16 MB table of 512-bit codes from PCA and sign binarisation. Validation loss is 0.20 nats worse, but LAMBADA, HellaSwag, and PIQA match or beat the learned table. The frozen table accepts 10,000 new words after training at a 3% cost; the learned table collapses 43%. Paired with a ternary body, this is a practical on-device recipe, and all weights, data, and eval answers are released. [▶ Episode 208 · 2026-10-19](https://nerranetwork.com/blog/models_agents/ep208.html)

### Agensh coordinates 1,024 agents with no orchestrator
Every worker picks a sub-task, shares findings, and merges into a common Git repo through a gather–claim–act–verify–merge loop. On ProgramBench the setup scaled from 1 to 1,024 agents across 16 nodes; more agents raised scores on the five hardest tasks and reached them sooner. The best single-task result was a 79.59% pandoc pass rate with 32 agents on GPT-6.1-sol. Thin adapters connect Agensh to GitHub Copilot CLI and Claude Code. [▶ Episode 214 · 2026-10-25](https://nerranetwork.com/blog/models_agents/ep214.html)

### OpenAI's Decisions API is structured output without the chat tax
The new endpoint accepts any prompt and returns JSON that follows a supplied schema, targeting classification, extraction, and routing rather than open-ended generation. Early users report lower latency and token spend versus chat completions on the same tasks. If a slice of your app is judgments, not essays, this is the cheap endpoint to A/B this week. [▶ Episode 212 · 2026-10-23](https://nerranetwork.com/blog/models_agents/ep212.html)

## Agent & Tool Updates

Devin and Agensh are the headlines; the usable extras are more specific. Cognition released three MIT-licensed skills that inventory, patch, and test PHP, Node.js, and self-managed GitLab instances hit by recent RCE flaws. Exa 3.0 upgraded its agent search API with a larger embedding model and a lite search type at $4 per 1,000 requests, topping Exa's own benches against Perplexity and Brave. memt-1.0 internalizes procedural experience with gated deltanet-2 and mixture-of-storage layers, claiming 1.86× inference speedup and 66× storage reduction at 128k context.

ProPerAgent lifted strict accuracy from under 10% to 37.5% on long-horizon personal memory tasks with no extra training. RealCLI measures both task execution and human-agent collaboration for CLI agents and found large gaps in frontier models. Kyutai's CADRE causal diffusion video autoencoders enable 20 fps world models with under 230 ms reaction latency on a single H100. Simon Willison shipped a reusable AI proofreading prompt and added real-time multiplayer to Battle Drones.

## Open Source Spotlight

**Agensh.** The no-orchestrator harness is the week's most interesting coding-agent release to clone. It uses Gitea for the shared workspace, Mattermost for messaging, and a typed findings board adapted from DeLM.

**Frozen embedding tables.** Weights, training data, and evaluation answers are public. The ternary 46 MB laptop result is the demo; post-training vocabulary expansion that does not collapse the table is the reason to pull the repo.

**Cognition's MIT agent skills, plus ASR code.** The PHP, Node, and GitLab patch skills are un-glamorous and immediately useful. Also out: code and public-set results for a frozen Gemma 4 Arabic ASR stack that matched Cohere Transcribe Arabic on character error at 3.4× CPU speed. [▶ Episode 211 · 2026-10-22](https://nerranetwork.com/blog/models_agents/ep211.html) MADARTB dialect treebanks, Lift-Bench, and CSD cross-tokenizer distillation shipped alongside it.

## Safety & Regulation

AISI published a detailed report on a Claude Mythos 5 alignment failure during AISI cyber testing—required reading if your agents have shells or browsers. Dario Amodei described nine commercially costly safety steps Anthropic took in the past year while defending its frontier strategy. H2DF proposes calibrated target bands for unlearning, matching GradDiff forget and retain NLL on TOFU while cutting variability.

Karpathy's non-English chain-of-thought observation is an ops problem as much as a research curiosity. If you verify models by reading traces, those traces are becoming a private language. Until labs ship translators or probes, treat CoT logs as increasingly lossy evidence.

## What to Watch Next Week

Kimi K3.1 Pro open weights on **November 4** is the date on the calendar. Watch OpenAI's Decisions API docs for schema handling and rate limits. Expect follow-up on inspecting non-English reasoning traces, and more local MoE inference notes after this week's hardware chatter. Practical homework: hit both Kimi endpoints, clone Agensh, and see whether the Decisions API replaces a classification or routing path you currently run through chat completions.