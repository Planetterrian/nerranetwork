# Models & Agents
> **Windows users can now steer Codex agents directly on their machines while stepping away.**

**What You Need to Know:** OpenAI extended computer-use capabilities to Windows for Codex, letting the agent act on local desktops and continue tasks from the mobile app. StepFun released a 198B MoE vision-language model optimized for coding agents, while Hermes Agent added tool search to reduce MCP context bloat. Builders should test the new Windows support this week and evaluate the MeMo memory architecture for long-term knowledge updates without retraining.
---
### Top Story
OpenAI added Windows support for Codex computer use, allowing the agent to perform actions directly on Windows machines and continue tasks started from the ChatGPT mobile app. The feature enables users to start, review, and steer work remotely while the agent keeps running locally. This expands Codex beyond macOS and browser environments, giving developers a path to run autonomous coding sessions on standard Windows hardware. Early access means reliability is still limited and users should expect iteration on edge cases like window management and file permissions. Watch for expanded mobile-to-desktop handoff features and tighter integration with local development tools in the coming weeks. Source: [x.com](https://x.com/OpenAI/status/2060428604727771421)
---
### Model Updates
**Step 3.7 Flash: StepFun**
StepFun released Step 3.7 Flash, a 198B MoE vision-language model with native vision support and 256k context. It includes an Advisor Mode aimed at coding agents and search workflows. The model targets agentic use cases where vision and long context matter. Builders working on multimodal coding agents should test it against current Qwen and Gemini vision setups to see where the MoE routing helps.

**Pantheon-Reasoning-27B: Gryphe**
Gryphe released Pantheon-Reasoning-27B, a dense Qwen 3.6 27B fine-tune that keeps thinking tags active across multi-turn conversations. Training data combined Pantheon roleplay with full reasoning traces from Opus 4.6, WorldSim, and text adventure sources. The model is positioned as a successor to both the Pantheon series and earlier Codex releases. Roleplay and agent developers can try the GGUF quants to see whether the added reasoning traces improve character consistency over non-reasoning baselines.

**X-Token: NVIDIA**
NVIDIA introduced X-Token, a projection-guided cross-tokenizer knowledge distillation method that improves on GOLD. On Llama-3.2-1B it raised average performance by 3.82 points and lifted GSM8k accuracy from 2.56 to 15.54. The technique addresses structural failures in prior distillation approaches when tokenizers differ. Teams doing model compression or student-teacher setups should examine the method for small-model reasoning gains.

**Qwen3.6-27B Quantization Results: Community Benchmark**
A detailed llama.cpp perplexity benchmark compared multiple Qwen3.6-27B quants from Unsloth, mradermacher, and others using mean KLD and top-token match. Q6_K and Q5_K_M variants stayed close to BF16 while Q4_K_XL offered the best quality-to-size trade-off for 16 GB cards. Lower quants below Q4 showed sharp KLD increases. Anyone running Qwen3.6-27B locally should review the tables before choosing between Unsloth Q4_K_XL and mradermacher IQ4_XS.

**Gemma 4 31B to MoE Conversion: Community Experiment**
A developer created a training script to convert Gemma 4 31B dense into a native MoE model by adding a router and experts while preserving the enable_moe_block config. The experiment targets knowledge updates and capability gains through the MoE structure. Early results are pending full runs on B300 hardware. Researchers interested in post-training dense Gemma 4 models should watch for public checkpoints and training code.
---
### Agent & Tool Developments
**Hermes Agent Tool Search: Nous Research**
Hermes Agent added Tool Search to the MCP layer using BM25 progressive schema disclosure. Anthropic evals showed accuracy gains from 49% to 74% on Opus 4 by reducing context bloat. The update targets long-horizon agents that previously hit token limits when exposing many tools. Teams building MCP-compatible agents should test the new search mechanism to see how it affects tool selection reliability.

**Genesis World 1.0: Genesis AI**
Genesis AI released Genesis World 1.0, a four-component simulation platform covering physics, rendering, compilation, and tooling for robotics foundation model evaluation. It achieved a 0.8996 Pearson correlation between simulation and real-world robot rollouts while cutting policy evaluation time from over 200 hours to under 0.5 hours. Nyx and Quadrants components support scalable testing. Robotics researchers and simulation teams should evaluate the platform for faster iteration on foundation models.

**AgentTrove Dataset: MarkTechPost**
AgentTrove provides 1.7M agentic interaction traces in ShareGPT format, the largest open collection currently available. A Python tutorial shows how to stream the data, normalize turns, extract commands, and export successful trajectories into clean SFT datasets. The resource targets researchers building or fine-tuning agent models. Developers working on agent training pipelines should pull the dataset to augment existing SFT collections.
---
### Practical & Community
**Fulloch V2: Local Voice Assistant**
Fulloch V2 runs a fully local voice assistant on 16 GB VRAM using Qwen3.5-9B for generation, Qwen3-1.7B for ASR and TTS, plus bge embeddings for semantic search over Obsidian vaults. It supports Home Assistant control, agentic long-term memory, acoustic barge-in, and custom wakewords without special models. The project includes a Chat UI and scripts for creating new voices. Linux and Windows users looking for private voice agents should clone the repo and test the Obsidian integration.

**Shadow AI: Local Voice Companion**
Shadow AI is a Windows-only voice-first companion that runs locally, supports any language mid-conversation, includes web search via a local SearXNG instance, and builds persistent memory across sessions. It offers optional Google integration and skill learning while keeping all data on-device. The project is open source under AGPL-3.0 and uses a bring-your-own-key model with Gemini. Windows developers wanting a always-listening local assistant should review the GitHub for setup and planned local model additions.

**Flash Attention 2 on V100: Community Port**
A community port of Flash Attention 2 for V100 GPUs delivered 3–24× speedups on forward and backward passes depending on sequence length and batch size, with memory reductions up to 93%. Benchmarks covered causal and non-causal attention across multiple head and dimension configurations. V100 owners running older inference stacks should test the ai-bond implementation to reclaim memory and reduce latency.
---
### Under the Hood: Memory Models vs RAG for Continual Updates
Everyone talks about giving LLMs new knowledge as if retrieval or fine-tuning are the only two levers. In practice, MeMo-style memory models insert a small dedicated network that stores facts parametrically while the main model stays frozen. The memory model is trained on synthetic QA pairs distilled from new documents, then updated via task-vector merging when fresh data arrives. This avoids the catastrophic forgetting that occurs when you fine-tune the full LLM and sidesteps the context-window and noise problems of raw RAG. The tradeoff is upfront compute—roughly 180 H200 GPU-hours to train a 14B memory model plus another 240 hours to generate reflections—plus an 11–19% accuracy drop versus full retraining. The approach shines when your corpus changes slowly and you need synthesis across many documents rather than exact lookup. Use it when you already have a strong frozen reasoning model and want to swap in updated knowledge without touching the base weights; stick with RAG when you need source citations or face rapidly changing data.
---
### Things to Try This Week
- Test OpenAI Codex computer use on a Windows machine for local file and IDE tasks to see how the mobile handoff performs in practice.
- Run the Pantheon-Reasoning-27B GGUF quant on a roleplay or agent workflow and compare thinking-trace consistency against a standard Qwen 3.6 27B.
- Evaluate Hermes Agent Tool Search on an MCP setup with many tools to measure the reported accuracy lift on Opus 4.
- Benchmark Unsloth Q4_K_XL versus mradermacher IQ4_XS on Qwen3.6-27B using your own prompts to decide the right quant for 16 GB cards.
- Clone Fulloch V2 and connect it to your Obsidian vault to test semantic voice search over personal notes.
---
### On the Horizon
- More Windows and mobile extensions for Codex-style computer use expected as OpenAI iterates on the early release.
- Additional MoE conversion experiments on Gemma 4 31B likely to appear on Hugging Face following the initial proof-of-concept.
- Expanded robotics simulation benchmarks using Genesis World 1.0 as more teams adopt the platform for policy evaluation.
- Further memory-model merging results and smaller-scale MeMo variants as researchers optimize the reflection-generation pipeline.