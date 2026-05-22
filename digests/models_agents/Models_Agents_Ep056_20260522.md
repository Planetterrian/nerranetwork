# Models & Agents
> **OpenAI just gave Codex the ability to control locked Macs and run multi-day goals, turning it into a true background agent you can launch from your phone.**

**What You Need to Know:** OpenAI shipped several Codex updates today including secure computer use on locked Macs, Goal mode for hours-long autonomous work, and advanced annotation tools. Microsoft released Fara1.5, a family of browser agents that beat OpenAI Operator and Gemini 2.5 on web tasks. Developers should watch how these agent capabilities integrate into existing workflows this week.
---
### Top Story
OpenAI announced new Codex features today including secure Mac computer use, Goal mode, and advanced annotation. Codex can now control apps on a locked Mac from your phone with the screen off, while Goal mode lets users set objectives that run for hours or days across the app, IDE extension, and CLI. Advanced annotation mode allows direct visual edits to web pages during feedback sessions. These changes make Codex significantly more hands-off compared to previous interactive coding tools. Builders working on automation or remote workflows should test Goal mode immediately to see how it handles long-running tasks without constant supervision. Watch for how OpenAI expands the computer-use surface beyond Macs in coming releases. Source: [x.com](https://x.com/OpenAI/status/2057617844800794878)
---
### Model Updates
**Fara1.5 Browser Agents: MarkTechPost**
Microsoft Research released Fara1.5, a family of browser computer-use agents in 4B, 9B, and 27B sizes. The 27B model scores 72% on Online-Mind2Web, outperforming OpenAI Operator, Gemini 2.5 Computer Use, and Yutori Navigator. The release includes FaraGen1.5, a synthetic data pipeline for training agents on gated environments. Teams building web automation should compare Fara1.5-9B against existing browser tools for cost-sensitive deployments. Source: [marktechpost.com](https://www.marktechpost.com/2026/05/22/microsoft-releases-fara1-5-a-family-of-browser-computer-use-agents-4b-9b-27b-that-outperform-openai-operator-and-gemini-2-5-computer-use-on-online-mind2web/)

**Recurrent-Depth Transformers with OpenMythos: MarkTechPost**
A new tutorial shows how to build recurrent-depth transformers using OpenMythos in Google Colab, supporting MLA, GQA, Sparse MoE, and loop-scaled reasoning. Users can create both MLA and GQA variants while checking stability of the recurrent injection matrix via spectral radius. This approach enables deeper reasoning loops without proportional parameter growth. Researchers experimenting with long-horizon tasks should try the Colab notebook to test loop scaling on their own datasets. Source: [marktechpost.com](https://www.marktechpost.com/2026/05/22/build-recurrent-depth-transformers-with-openmythos-for-mla-gqa-sparse-moe-and-loop-scaled-reasoning/)

**Probabilistic Attribution for LLMs: arXiv**
A new framework uses Bayes rule on next-token log-probabilities to attribute model outputs back to prompt tokens without depending on internal architecture. The method computes conditional probabilities of responses given prompts and marginalizes individual tokens to produce attribution scores. It also tracks entropy across token distributions to highlight uncertain generation steps. Developers debugging prompt sensitivity should apply this technique to surface which input tokens most influence unstable outputs. Source: [arxiv.org](https://arxiv.org/abs/2605.21726)

**Sem-Detect for AI Peer Review: arXiv**
Sem-Detect combines textual features with claim-level semantic analysis to detect fully AI-generated peer reviews. It compares target reviews against multiple AI-generated versions of the same paper, exploiting convergence patterns in model outputs. On over 20,000 ICLR and NeurIPS reviews it improves TPR@0.1% FPR by 25.5% over baselines. Conference organizers and journal platforms should evaluate it for catching AI-assisted submissions that still contain human judgment. Source: [arxiv.org](https://arxiv.org/abs/2605.21713)
---
### Agent & Tool Developments
**Agent Skills for Python: Microsoft Agent Framework**
Python developers can now author Agent Skills as files on disk, inline code, or reusable classes and compose them freely through source classes that handle discovery and deduplication. Skills can come from local repos, internal package indexes, or quick definitions. This removes previous friction around mixing skill sources in agent workflows. Teams using Microsoft’s framework should refactor existing skills into composable classes to improve reuse across projects. Source: [devblogs.microsoft.com](https://devblogs.microsoft.com/agent-framework/agent-skills-for-python-file-code-and-class-composed-in-one-provider/)

**ztok Fast Tokenizer: r/LocalLLaMA**
ztok is a new multithreaded tokenizer in Zig that loads tiktoken, Hugging Face, SentencePiece, and other formats while delivering 2–5× speedups. It remains bit-identical to reference implementations and exposes eight language bindings over a single C ABI. The library targets RAG chunking and dataset tokenization to .bin/.npy files. Local pipeline builders should benchmark it against HF tokenizers on their current vocabularies for immediate throughput gains. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tkd45g/ztok_a_fast_multithreaded_tokenizer_in_zig_that/)

**RankJudge Multi-Turn Judge Benchmark: arXiv**
RankJudge generates synthetic multi-turn conversation pairs with single injected flaws to evaluate LLM-as-a-judge systems on complex dialogues. It supports domains including machine learning, biomedicine, and finance and ranks 21 frontier judges using Bradley-Terry modeling. The benchmark enables precise isolation of failure modes to individual turns. Evaluation teams should adopt it when current single-turn judge benchmarks no longer match their conversational agent complexity. Source: [arxiv.org](https://arxiv.org/abs/2605.21748)
---
### Practical & Community
**Low-Level Coding Dataset: r/LocalLLaMA**
A community effort is collecting a JSONL dataset focused on C++ and systems programming for fine-tuning local models on memory ownership, thread safety, and optimization. Categories include generation, optimization, debugging, organization, and tool calling. Contributors are discussing structure and whether tool-calling examples need separate emphasis. Builders targeting systems-level code should contribute examples or test early fine-tunes on Qwen3.6-27B variants. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tk9a7o/lowlevel_coding_dataset/)

**ACC for Long-Context Training: arXiv**
Agent Context Compilation converts multi-turn agent trajectories from search, software engineering, and database agents into long-context QA pairs. It supplies direct supervision on cross-turn dependencies without additional annotation. Training Qwen3-30B-A3B with ACC yields +18.1 on MRCR and +7.6 on GraphWalks while preserving general capabilities. Teams extending context windows should incorporate ACC trajectories into their SFT mix for measurable long-range gains. Source: [arxiv.org](https://arxiv.org/abs/2605.21850)

**PromptNCE for Zero-Shot PMI: arXiv**
PromptNCE estimates pointwise mutual information using only LLM prompts and contrastive estimation with an explicit OTHER category. It recovers true conditional probabilities rather than simple rankings and reaches 0.82 Spearman correlation with human-derived PMI on three datasets. Education researchers are already using it to score student knowledge summaries in low-data settings. Practitioners needing lightweight information-theoretic metrics should test PromptNCE before training task-specific critics. Source: [arxiv.org](https://arxiv.org/abs/2605.21776)
---
### Under the Hood: Hypergraph Tokenization for LLMs
Everyone talks about feeding graphs into LLMs as if you just serialize edges into text. In practice, hypergraphs require a fundamentally different tokenization strategy because multiple vertices share a single high-order relation that pairwise edges cannot express. The core move is to project native incidence structures into the model’s token space using a bidirectional message-passing projector that decouples semantic content from structural roles. This adds a fixed-shape hybrid template containing both local incidence details and overview summaries, which the projector maps without collapsing higher-order connections. The engineering tradeoff is clear: you gain faithful representation of joint relations at the cost of roughly 15–20% more tokens per hyperedge compared with naive flattening. Quality gains are largest on tasks with dense multi-way dependencies and shrink once graphs become mostly pairwise. When your relational data contains frequent n-ary patterns that matter for correctness, adopt hypergraph-native tokenization; otherwise stick with standard graph linearization and accept the semantic loss. The gotcha most teams hit is underestimating how quickly token budgets explode once incidence details are preserved at scale.
---
### Things to Try This Week
- Test OpenAI Codex Goal mode on a multi-hour refactoring task to see how well it maintains context without intervention.
- Run Fara1.5-9B against your current browser automation scripts and measure task completion rate versus OpenAI Operator.
- Benchmark ztok against your existing tokenizer on a 100k-document RAG corpus for throughput improvements.
- Apply Sem-Detect to a sample of recent peer reviews to evaluate its false-positive rate on LLM-refined human text.
- Generate RankJudge pairs in your domain and score your preferred judge model to identify turn-level weaknesses.
---
### On the Horizon
- Continued expansion of Codex computer-use capabilities beyond macOS expected in the next release cycle.
- More labs likely to release browser or desktop agent families following Microsoft’s Fara1.5 results.
- Growing adoption of hypergraph modeling techniques in relational reasoning benchmarks.
- Further arXiv work on probabilistic attribution and long-context compilation methods for agent trajectories.