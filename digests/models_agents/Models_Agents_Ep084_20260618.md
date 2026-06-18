# Models & Agents
> **OpenAI’s LifeSciBench brings 750 expert-authored tasks from real biotech and pharma workflows into AI evaluation.**

**What You Need to Know:** OpenAI released LifeSciBench, a benchmark spanning seven biological research workflows developed with 173 scientists. GPT-Rosalind outperforms GPT-5.5 across all workflows, while GPT-5.4 drove a full medicinal chemistry project from literature to validated result when paired with Molecule.one’s Maria AI. Builders should watch how these domain-specific evals shift model selection for scientific work this week.
---
### Top Story
OpenAI introduced LifeSciBench, a benchmark containing 750 expert-authored tasks across seven biological research workflows developed with 173 scientists from biotechnology and pharmaceutical research. The tasks emphasize reasoning from evidence, working with scientific artifacts, handling uncertainty, and making decisions under real-world constraints rather than testing isolated biological knowledge. GPT-Rosalind scores above GPT-5.5 on every workflow, while GPT-5.4 successfully proposed an unexpected improvement to a widely used reaction in drug discovery when paired with Molecule.one’s Maria AI and a specialized lab. This moves frontier model evaluation closer to measurable impact on actual research pipelines. Developers working on scientific tooling or life-science agents should test current models against the new tasks to see where gaps remain in artifact-heavy and design-intensive work. Source: [x.com](https://x.com/OpenAI/status/2067346916929937827)
---
### Model Updates
**Claude Fable 5 review: Simon Willison (AI builder)**
Simon Willison called Claude Fable 5 “very, very good” after testing it on multiple tasks. He linked two detailed blog posts documenting its performance on proactive behavior and other capabilities. The model shows clear progress over prior Claude releases in sustained, goal-directed work. Builders focused on agentic coding or research assistance should try Fable 5 on multi-step workflows this week to compare against current Claude 4.x baselines. Source: [x.com](https://x.com/simonw/status/2067321975635386831)

**Opus 4 to 4.5 capability jump: Simon Willison (AI builder)**
Simon Willison described the jump from Opus 4 to Opus 4.5 as comparable to the GPT-3.5 to GPT-4 transition. The improvement appears substantial enough to change which models he reaches for on harder tasks. This continues the pattern of rapid iteration within the Claude family. Watch for similar step-function gains in other frontier lines over the coming months. Source: [x.com](https://x.com/simonw/status/2067326875576455209)

**SproutRAG hierarchical retrieval: arXiv**
SproutRAG organizes sentence-level chunks into a binary tree using learned inter-sentence attention, enabling multi-granularity retrieval without extra LLM calls or lossy summaries. It improves information efficiency by 6.1% on average across scientific, legal, and open-domain benchmarks. The framework trains end-to-end and uses hierarchical beam search at inference time. Teams building long-document RAG should test the released code on their corpora this week. Source: [arxiv.org](https://arxiv.org/abs/2606.18381)

**JetFlow speculative decoding: arXiv**
JetFlow introduces a causal parallel draft head over fused hidden states that produces branch-wise conditioned candidate trees for speculative decoding. It delivers up to 9.64x speedup on MATH-500 and 4.58x on conversational workloads on H100 GPUs while integrating with vLLM. The method avoids the causality-efficiency tradeoff of prior head-based and bidirectional approaches. Inference teams should benchmark it against existing speculative decoding baselines on their target models. Source: [arxiv.org](https://arxiv.org/abs/2606.18394)

**Continuous Audio Thinking (CoAT): arXiv**
CoAT adds a continuous latent workspace to large audio language models via distillation from audio experts, preserving phonetic, prosodic, and affective information before text generation. It improves performance across audio reasoning, music classification, speech emotion, and transcription benchmarks on Qwen2-Audio, Qwen2.5-Omni-7B, and Audio Flamingo 3 without extra autoregressive cost. Audio and multimodal teams can adopt the thinking block as a drop-in enhancement. Source: [arxiv.org](https://arxiv.org/abs/2606.18273)
---
### Agent & Tool Developments
**VISUALSKILL multimodal skills: arXiv**
VISUALSKILL supplies computer-use agents with hierarchical, application-specific skills that retain both text and visual UI figures instead of verbalizing them away. A Claude Opus 4.6 agent using the skills reached 0.456 average score on CUA-World and OSExpert-Eval, an 8.3-point gain over a matched text-only skill set. The two-stage construction pipeline combines authored docs with live UI exploration and exposes content via a load_topic MCP tool. Agent developers targeting GUI-heavy workflows should examine the released skill index format. Source: [arxiv.org](https://arxiv.org/abs/2606.18448)

**CoreMem long-term memory: arXiv**
CoreMem replaces cosine similarity with a Riemannian Fisher-Rao metric for retrieval and adds Fisher-guided discrete token distillation for context compression in dialogue agents. It delivers +4.51 pp on open-domain and +4.17 pp on temporal reasoning within the strict 8 GB VRAM limit of edge devices. The approach directly targets hubness and fragmentation problems common in long-term agent memory. Teams deploying persistent agents on consumer hardware should evaluate the edge-cloud split. Source: [arxiv.org](https://arxiv.org/abs/2606.18406)
---
### Practical & Community
**MCompassRAG topic-guided retrieval: arXiv**
MCompassRAG enriches chunk embeddings with topic metadata and trains a lightweight retriever via LLM-teacher distillation for topic-aware retrieval without additional LLM calls. It improves information efficiency by 8.24% on average across six complex benchmarks while cutting latency more than 5x versus strong baselines. The method is especially useful for deep research tasks over heterogeneous corpora. Check the GitHub release if your RAG system struggles with semantic noise in large document collections. Source: [arxiv.org](https://arxiv.org/abs/2606.18508)

**Activation steering for low-resource languages: arXiv**
Steering on early layers of open-source LLMs improves diversity of generated synthetic data for 11 typologically diverse low-resource languages while often boosting downstream classifier performance. The approach works in both zero-shot and few-shot settings and avoids the lexical anchoring of few-shot prompting. Researchers generating training data for under-resourced languages should experiment with Language Steering and Quality Steering vectors. Source: [arxiv.org](https://arxiv.org/abs/2606.18389)
---
### Under the Hood: Hierarchical Chunking Trees for RAG
Everyone talks about “better chunking” for RAG as if it is a simple preprocessing choice. In practice, SproutRAG-style systems learn which attention heads and layers best capture document structure and then build a binary tree that groups sentences into progressively larger coherent units. The tree is constructed once at indexing time using inter-sentence attention scores rather than external LLM calls or fixed window rules, so retrieval can later pull candidates at multiple granularities with a single hierarchical beam search. This removes the usual tradeoff between fine-grained precision and cross-sentence context while avoiding the information loss that comes from summarization-based hierarchies. The quality gain is largest on long, multi-topic documents; on short or already well-structured text the overhead of maintaining the tree brings diminishing returns. When your corpus contains dense technical or legal material that spans many pages, the attention-guided tree is worth the extra indexing step; for simple FAQ-style collections the added structure rarely justifies itself.
---
### Things to Try This Week
- Test GPT-5.4 on a medicinal chemistry or reaction-planning task using the Molecule.one integration to see where it proposes unexpected improvements.
- Run SproutRAG or MCompassRAG on a long-document corpus you already use and measure the change in information efficiency versus your current chunking method.
- Add VISUALSKILL-style multimodal skill files to an existing computer-use agent and compare success rates on GUI workflows that previously relied on text-only descriptions.
- Apply early-layer activation steering to synthetic data generation for any low-resource language you work with and check downstream classifier gains.
---
### On the Horizon
- More labs are expected to release domain-specific benchmarks modeled on LifeSciBench in the coming months.
- Continued work on edge-friendly long-term memory architectures like CoreMem will likely appear in production agent frameworks soon.
- Hierarchical retrieval methods that avoid extra LLM calls during indexing are gaining traction and may become default options in major RAG libraries.