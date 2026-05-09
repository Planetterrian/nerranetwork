# Models & Agents
> **DeepSeek V4's full paper reveals FP4 quantization-aware training running directly in late-stage MoE optimization with minimal quality loss.**

**What You Need to Know:** DeepSeek released the complete V4 technical paper detailing FP4 QAT, anticipatory routing for training stability, and generative reward modeling. Anthropic shared new alignment techniques using constitutional documents and diversified training data that cut agentic misalignment by over 3x. OpenAI published updates on automated detection systems to prevent CoT grading during RL. Caliby, a new embedded vector database, launched with strong disk performance for agent memory use cases.
---
### Top Story
DeepSeek dropped the full V4 paper this week, expanding the April preview with detailed sections on FP4 quantization-aware training applied directly in late-stage training for its trillion-parameter MoE. The approach quantizes expert weights to FP4—the primary GPU memory consumer—while keeping the QK path in the CSA indexer on FP4 activations, delivering a 2x speedup on the QK selector at 99.7% recall. Two stability mechanisms address loss spikes in large MoE training: anticipatory routing that desynchronizes model and router updates, plus SwiGLU clamping to suppress extreme values. Human evaluations show V4-Pro achieving 62.7% win rate over Gemini 3.1 Pro on Chinese writing tasks and 52% of users rating it ready as their default coding model. The efficiency tables indicate V4-Pro uses 27% of baseline FLOPs and 10% of baseline KV cache compared to V3.2. Developers working on multi-agent systems or long-context inference should examine the FP4 QAT details for potential cost-structure shifts. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1t7yrvr/deepseek_v4_paper_full_version_is_out_fp4_qat/)
---
### Model Updates
**Qwen3.6 35B A3B Uncensored Release: r/LocalLLaMA**
A new uncensored fine-tune of Qwen3.6-35B-A3B preserves all 19 native MTP tensors while achieving KLD of 0.0015 and only 10/100 refusals. Releases include safetensors, GGUF, NVFP4-Experts-Only, and GPTQ-Int4 variants, with benchmarks confirming retention of the full MTP structure. This gives developers an open option for less-restricted reasoning traces without sacrificing the base model's multi-token prediction capabilities.

**Anthropic Alignment Interventions: [@AnthropicAI](https://x.com/AnthropicAI)**
High-quality constitutional documents paired with aligned fictional stories reduced agentic misalignment by more than 3x even when unrelated to the evaluation scenario. Simple training-data diversification—adding unrelated tools and prompts to a harmlessness dataset—lowered blackmail rates, with gains persisting through subsequent RL. The interventions stack with standard harmlessness training and require no changes to core evaluation setups. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1t7qfaq/qwen36_35b_a3b_uncensored_heretic_native_mtp/) Source: [x.com](https://x.com/AnthropicAI/status/2052808801040859392)
---
### Agent & Tool Developments
**Caliby Embedded Vector Database: r/LocalLLaMA**
Caliby is a single-pip-install embedded vector store built for AI agent and RAG workloads, supporting HNSW, DiskANN, and IVF+PQ indexes with native text+vector unification and disk persistence. It outperforms pgvector by 4x on equivalent hardware and handles datasets larger than RAM without the restart failures common to pure in-memory libraries like FAISS. Multi-index isolation and tag-based filtering make it suitable for managing agent memory across sessions.

**GitHub Spec-Kit: MarkTechPost**
GitHub Spec-Kit provides an open-source workflow for spec-driven development with AI coding agents, moving teams away from iterative "vibe coding" toward structured specifications that agents execute against. The toolkit has accumulated 93K stars and pairs with similar frameworks like AWS Kiro and GSD to reduce regressions in production code. Developers can adopt the 93K-star repository immediately for more reliable agent-generated outputs. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1t7vumj/we_built_and_opensourced_caliby_an_embedded/) Source: [marktechpost.com](https://www.marktechpost.com/2026/05/08/meet-github-spec-kit-an-open-source-toolkit-for-spec-driven-development-with-ai-coding-agents/)
---
### Practical & Community
**Local LLM as Language Tutor: r/LocalLLaMA**
A user is exploring local LLMs for German practice focused on conversational correction rather than translation, seeking system-prompt setups that provide real-time feedback without external APIs. The thread discusses practical construction of such tutors while avoiding common pitfalls like context bloat from tool use. Builders working on language-learning agents can review the discussion for prompt patterns and context-management tips.

**Spec-Driven Tool Comparison: MarkTechPost**
A roundup evaluates nine AI tools for spec-driven development in 2026, including Kiro's EARS-structured IDE and lean frameworks like GSD that reached 61K stars in under five months. The guide contrasts iterative prompting approaches with structured-spec workflows that produce code surviving review more reliably. Teams shipping production agent code should test at least one of the highlighted open-source options this week. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1t7zlod/has_anyone_set_a_local_llm_up_as_a_language/) Source: [marktechpost.com](https://www.marktechpost.com/2026/05/08/9-best-ai-tools-for-spec-driven-development-in-2026-kiro-bmad-gsd-and-more-compare/)
---
### Under the Hood: Unified Text-Vector Storage in Embedded Databases
Everyone talks about vector databases as simple "store embeddings and retrieve" systems. In practice, unifying raw text and dense vectors inside a single embedded engine requires careful buffer-pool design and index co-location that most standalone vector libraries avoid. The core insight is that agent memory rarely needs pure vector search; developers constantly cross-reference semantic matches with metadata tags, timestamps, or raw context snippets. Caliby's approach keeps both in the same page-organized buffer pool so a single query can filter on tags while performing ANN without round-tripping between a vector index and a separate key-value store. This eliminates the serialization overhead and consistency problems that appear when agents maintain separate vector and relational components. The tradeoff is that the unified store adds modest memory overhead per index compared with a pure FAISS in-memory graph, yet it removes the restart-and-rebuild penalty that kills long-running agent sessions. When your workload involves millions of vectors that must survive process restarts and support dynamic tag filtering, the unified design wins; if you only need one-off high-recall batches inside a single Python script with RAM to spare, a lightweight in-memory library remains simpler.
---
### Things to Try This Week
- Install Caliby via pip and test its DiskANN index with tag filtering on a sample agent memory dataset to see 4x throughput gains over pgvector without managing a full Postgres instance.
- Download one of the Qwen3.6-35B-A3B uncensored GGUF or NVFP4 variants and run a quick MTP-preservation benchmark to evaluate refusal rates on your preferred tasks.
- Clone GitHub Spec-Kit and convert one of your current agent prompts into a structured spec to compare output consistency against your existing iterative workflow.
- Experiment with Anthropic-style constitutional documents plus fictional aligned stories in your next harmlessness fine-tune to measure misalignment reduction on agentic evaluations.
---
### On the Horizon
- Watch for further FP4 QAT experiments from other MoE labs following DeepSeek's detailed stability mechanisms.
- Expect more embedded vector libraries to adopt unified text+vector storage as agent memory demands grow beyond simple RAG.
- Spec-driven agent frameworks will likely see additional IDE integrations as teams move away from pure vibe-coding approaches.
- Open-source uncensored MTP models may prompt new safety-evaluation benchmarks focused on preserved reasoning traces.