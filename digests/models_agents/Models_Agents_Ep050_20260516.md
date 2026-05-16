# Models & Agents
> **An agent that manages another agent just moved from research demo to production reality at Fin.**

**What You Need to Know:** Fin (formerly Intercom) launched Fin Operator, an AI system whose sole job is configuring, debugging, and monitoring the customer-facing Fin agent. The release highlights a practical two-layer agent architecture with human approval gates and usage-based pricing. Builders should watch how support-ops workflows shift when one agent owns the operational loop for another.
---
### Top Story
Fin announced Fin Operator, an AI agent purpose-built to manage the company's customer-facing Fin agent. Operator acts as data analyst, knowledge manager, and debugger: it generates charts from conversation metrics, ingests product PDFs to update help articles, traces failed conversations to root causes in guidance rules, and proposes fixes as reviewable diffs. It runs on Claude rather than Fin's own Apex models because the tasks resemble software-engineering work more than customer-service resolution. Every change requires explicit human approval before going live, and early beta users report it feels like adding five people to the ops team. General availability is planned for summer 2026 inside the Pro tier with usage-based billing. The launch shows enterprises are now willing to productionize meta-agents when strict human oversight remains in place. Source: [venturebeat.com](https://venturebeat.com/technology/intercom-now-called-fin-launches-an-ai-agent-whose-only-job-is-managing-another-ai-agent)
---
### Model Updates
**Qwen3.6-35B-A3B and 9B on Terminal-Bench 2.0: r/LocalLLaMA**
The 35B-A3B variant with little-coder scaffold reached 24.6% on the public Terminal-Bench 2.0 leaderboard, surpassing Gemini 2.5 Pro on Gemini CLI. The 9B model scored 9.2%, proving sub-10B models can now register measurable results on hard agentic benchmarks. The result underscores that scaffold choice still matters more than raw parameter count on this evaluation. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1temio0/qwen3635ba3b_and_9b_are_officially_on_the_public/)

**Zyphra ZAYA1-8B-Diffusion-Preview: MarkTechPost**
Zyphra converted an autoregressive MoE model into a discrete diffusion model, delivering up to 7.7x inference speedup by moving decoding from memory-bandwidth bound to compute-bound. The preview shows no systematic loss on standard evaluations. This is the first public demonstration of turning an existing MoE LLM into a diffusion model at this scale. Source: [marktechpost.com](https://www.marktechpost.com/2026/05/15/zyphra-releases-zaya1-8b-diffusion-preview-the-first-moe-diffusion-model-converted-from-an-autoregressive-llm-with-up-to-7-7x-speedup/)

**Gemma4 26B MoE in MLX with turboquant: r/LocalLLaMA**
A custom MLX backend with turboquant and rotating KV cache now runs Gemma4 26B on M5 MacBook Air at 128k context with 4 concurrent batches. At 8k context it outperforms llama.cpp on both prompt processing and generation speed while using less runtime memory. The implementation includes a custom kernel for SWA layers to preserve 2-bit memory savings at higher batch sizes. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1te6os6/gemma4_26b_moe_running_in_mlx_with_turboquant_and/)

**AllenAI MolmoAct2 robotics models: r/LocalLLaMA**
AllenAI released a series of 5B vision-language-action models fine-tuned on robotics datasets including LIBERO, DROID, and bimanual tasks. All weights, training datasets, code, and papers are fully open. The models target absolute joint-pose control and interactive robotics scenarios. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1te9unl/allenai_has_been_iterating_on_their_molmoact2/)
---
### Agent & Tool Developments
**RecursiveMAS multi-agent framework: VentureBeat**
RecursiveMAS lets agents collaborate entirely in latent space instead of exchanging text tokens, yielding 1.2–2.4x faster inference and up to 75% token reduction. Only lightweight RecursiveLink modules (0.31% of parameters) are trained while base models stay frozen. The approach was tested across code, math, and medical reasoning benchmarks with open-weight models. Source: [venturebeat.com](https://venturebeat.com/orchestration/how-recursivemas-speeds-up-multi-agent-inference-by-2-4x-and-reduces-token-usage-by-75)

**MCP-style routed agent tutorial: MarkTechPost**
A new tutorial walks through building a fully functional MCP-style routed agent system with dynamic tool discovery, structured planning, and context injection. It includes a modular tool server exposing web search, local retrieval, dataset loading, and Python execution. The code is designed to be extended for custom agent workflows. Source: [marktechpost.com](https://www.marktechpost.com/2026/05/15/how-to-build-an-mcp-style-routed-ai-agent-system-with-dynamic-tool-exposure-planning-execution-and-context-injection/)

**Nexidion private knowledge vault: r/LocalLLaMA**
Nexidion is an open-source hierarchical Markdown note-taking app with an autonomous background agent that can reorganize notes, summarize subtrees, or extract action items. All work runs locally against OpenAI-compatible endpoints and is protected by built-in version control so every AI edit can be reverted. A Docker Compose setup spins up the full stack including task runner. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1te9381/release_nexidion_a_private_knowledge_vault_with/)
---
### Practical & Community
**RAG on Snapdragon X2 laptop: r/LocalLLaMA**
A developer indexed ~200k documents on an ASUS Zenbook with Snapdragon X2 Elite Extreme using VecML’s on-device AI database. The setup keeps most data on disk with a small active buffer, achieving low-token retrieval while staying within the laptop’s power and thermal limits. The NPU delivers roughly 50% of an RTX 5060’s embedding speed in a far lighter package. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1te93s3/rag_on_snapdragon_x2_laptop_200k_documents/)

**little-coder scaffold for Qwen: r/LocalLLaMA**
The little-coder project that powered the top Terminal-Bench 2.0 Qwen entry is now public on GitHub. It demonstrates that a relatively simple scaffold can lift a 35B MoE model above larger closed models on agentic coding tasks. The repo includes the exact configuration used for the 24.6% leaderboard run. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1temio0/qwen3635ba3b_and_9b_are_officially_on_the_public/)
---
### Under the Hood: Diffusion Decoding for LLMs
Everyone talks about diffusion LLMs as if they simply “generate in parallel.” In practice the technique replaces sequential token-by-token sampling with iterative denoising of a full latent sequence. The model begins with random noise and applies a learned denoiser for a fixed number of steps; each step refines every position simultaneously rather than waiting for the previous token. Because the expensive operations are now matrix multiplies instead of memory-bound KV cache reads, throughput scales with FLOPs instead of bandwidth—exactly why Zyphra saw 7.7x speedups on the 8B MoE. The tradeoff appears at training time: the model must learn to denoise at every diffusion step, which adds a second loss term and requires careful scheduling of noise levels. Quality currently matches autoregressive baselines only when the diffusion schedule is tuned per model size; below ~7B parameters the gap widens quickly. When you need maximum tokens per second on short-to-medium outputs and can afford a small quality regression during early training, diffusion decoding is worth trying; for long coherent generation or when you must stay within existing autoregressive fine-tunes, the classic next-token approach remains simpler. The gotcha most teams hit is assuming any diffusion schedule works—without per-model calibration the output often collapses into repetitive patterns after step 4.
---
### Things to Try This Week
- Spin up the little-coder scaffold against Qwen3.6-35B-A3B on Terminal-Bench 2.0 to see whether the 24.6% result holds on your own agentic tasks.
- Test RecursiveMAS on a small code-generation or medical-reasoning benchmark if you are already running multiple open-weight models in sequence.
- Run the MCP-style routed agent tutorial locally and swap in your own tool server to measure planning overhead versus a simple ReAct loop.
- Index a few thousand documents with the Snapdragon X2 + VecML setup if you need on-device RAG without a discrete GPU.
- Clone Nexidion and point it at a local Qwen or Gemma endpoint to experiment with autonomous note reorganization under version control.
---
### On the Horizon
- Fin Operator moves from early-access beta to general availability this summer inside the Pro tier.
- Zyphra plans to release trained weights and quality benchmarks for the ZAYA1 diffusion model once training completes.
- AllenAI continues releasing new MolmoAct2 fine-tunes on additional robotics datasets with full training code and data.
- Snapdragon X Elite and X2 laptops are expected to see broader on-device RAG and agent tooling support as NPU libraries mature.