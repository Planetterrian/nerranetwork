# Models & Agents
> **CoreWeave’s new platform lets agents improve themselves between training and inference runs without manual retraining cycles.**

**What You Need to Know:** CoreWeave launched a unified agentic platform that closes the training-to-inference gap for continuous autonomous improvement. Perplexity open-sourced a Unigram tokenizer that cuts reranker latency 5x versus Hugging Face. Multiple teams showed practical Qwen3.6-35B-A3B inference on single consumer GPUs with strong context handling. Builders should watch how these infrastructure and tooling shifts affect agent deployment costs this week.
---
### Top Story
CoreWeave launched a unified agentic AI platform that enables continuous autonomous agent improvement by closing the training-to-inference gap. The system supports self-improvement loops where agents can iterate on their own outputs without requiring full retraining cycles. It targets production workloads where agents need to adapt in real time rather than waiting for scheduled fine-tuning runs. Teams building long-running autonomous systems can now test tighter feedback loops between inference results and model updates. Watch for how other inference providers respond with similar continuous-improvement tooling. Source: [Google News](https://news.google.com/rss/articles/CBMirwFBVV95cUxPWFR2TUFkc2JQVl81ekxGOGtMZzdVc0J0bHFWMW9CZDdaaFF0Ti1pYmRZVGs1SlZaQllsUUxURF9XemxfelRmTWJlVmpteVR5Q3gtYUtfXzRfZlNrU3g1cEFfS2dlQmxjMDRjMHpWcWw2STNiOVdOLVYyNS00amJSbkE3cjlQakN2RnNJaTVaZjZBdHNzTzFkZ25KMFFSUFh1VG9hSUhKeXBVZm0xZ1FB?oc=5)
---
### Model Updates
**Perplexity AI Open-Sources Unigram Tokenizer: MarkTechPost**
Perplexity released a rewritten Unigram tokenizer that delivers 5x lower p50 latency than the Hugging Face tokenizers crate while cutting production CPU utilization 5-6x. The tokenizer targets reranker workloads where tokenization overhead previously dominated latency. It maintains compatibility with existing pipelines while reducing the CPU footprint for high-throughput search and retrieval tasks. Builders running reranking stages at scale should benchmark this drop-in replacement this week. Source: [marktechpost.com](https://www.marktechpost.com/2026/05/28/perplexity-ai-open-sources-unigram-tokenizer-that-achieves-5x-lower-p50-latency-than-hugging-face-tokenizers-crate/)

**Qwen3.6-35B-A3B-APEX on RTX 3060 12GB: r/LocalLLaMA**
A user demonstrated Qwen3.6-35B-A3B-APEX-MTP-I-Compact running at 37 t/s generation with 72k context on a single RTX 3060 12GB using spiritbuun’s CUDA fork and mudler’s APEX quantization. The setup offloads a 17.3 GB model while keeping PPL at 3.25 and achieving 100% needle-in-haystack retrieval up to 200k tokens. MTP heads hurt performance on this hardware and should be left disabled. Anyone targeting long-context inference on 12 GB cards now has a concrete recipe to test. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tq0h1p/qwen3635ba3bapex_128k_ctx_on_rtx_3060_12gb_37_ts/)

**Krasis Runtime Update for Qwen3.6: r/LocalLLaMA**
Krasis v1.0 added full Rust execution, 4-bit and 6-bit KV cache, and sensitivity-aware HQQ attention that mixes 4/6/8-bit precision per layer. On an RTX 3070 Mobile 8 GB it reaches 222 prompt tokens/s and 12.48 tokens/s generation for Qwen3.6-35B-A3B Q4. The runtime now supports Ampere cards and reduces system RAM requirements to roughly 1x model size plus overhead. Users running models that exceed VRAM should evaluate the new KV cache options. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tpyqng/krasis_update_qwen3635ba3b_q4_at_reading_speed_1x/)

**DiffuJudge-AV Framework: Towards Data Science**
A diffusion-inspired framework for calibrated LLM-as-a-Judge evaluation was released, focused on safety-critical autonomous vehicle video assessment. It applies iterative denoising to stress-test judge pipelines and produce more reliable structured scores. The approach targets domains where single-pass LLM judgments are currently too noisy for production use. Teams building evaluation harnesses for multimodal agents can experiment with the denoising loop. Source: [towardsdatascience.com](https://towardsdatascience.com/diffujudge-av-a-diffusion-inspired-framework-for-calibrated-av-video-evaluation/)
---
### Agent & Tool Developments
**Snowflake acquires Natoma: Coverager**
Snowflake acquired Natoma to expand governance capabilities for AI agents, focusing on MCP-based controls. The move adds agent-specific policy and oversight tooling to Snowflake’s existing data platform. Enterprise teams already using Snowflake for data workloads gain a path to unified agent governance without additional vendors. Source: [Google News](https://news.google.com/rss/articles/CBMilgFBVV95cUxNMHRnSkVtLUtXT09DZ1pzVHZNWTdsRzZMRlRhSU1TcDMyUzBaWXV3UGgtNnZocml6UTNXQ1luSVZkeEh4anJkcXAwcjRiYlk4VEVFblYwMzVJWWZ3VmVuWndrbkZwTXpfSGVIdVExeXQtc2dDN3ZBZnZEYllRSkhyN3QzQ1pxcDRmR3QzdlUzQzJ6LTg2VGc?oc=5)

**Geordie AI Raises $30M: Unite.AI**
Geordie AI closed a $30M Series A to build security and control layers for enterprise AI agents. The funding targets the growing demand for guardrails around autonomous agent deployments. Companies evaluating agent platforms now have another funded option focused on runtime safety rather than core orchestration. Source: [Google News](https://news.google.com/rss/articles/CBMilwFBVV95cUxOUVU5RTVEZ0tXMGZCZVp2ZWFNWHYtMUIyeDNhN1BzZE5oTVlRajYtSGVSTC1NRmd1WEtpQUwtMWVrcFI4NjRqQzZZQ0dOczNqbXlvbmFoOVdaYkRJd2tnYzVkeHFLMnByYXh2NGQtdDRnSVBockdMbHRLN2hvRTRqdXFCQkZwdlAwbmtFRjZJNTFuYk5NLVlN?oc=5)

**Microsoft Cloud PCs for Agent Controls: Help Net Security**
Microsoft introduced new cloud PC offerings that place AI agents under enterprise policy and access controls. The update integrates agent execution into existing Windows endpoint management surfaces. Organizations already managing devices through Microsoft Intune can extend the same controls to agent workloads. Source: [Google News](https://news.google.com/rss/articles/CBMilAFBVV95cUxOUHV3cUxaWng0N0F1TGJOR0lXMDZiM2M3VFZWdmRBamluU3FRcHBHak9GVVRZaWdqN0UwcHYtVVBLTDRNd3dsZWxjVmx0bEFYWTVZdWVNbWlzUVhPWlVqZnRqcjllaG5wbHBxekhQcURJU3Zla21FVFBTeDMzY3d1blg4NS1Nd09VQzZZZ20wR1ktUWUy?oc=5)

**Salesforce AI Agents Outperform Human Support: CX Today**
Salesforce reported that its AI agents now handle more support volume than human teams in certain workflows. The agents operate inside existing Service Cloud routing and escalation paths. Companies using Salesforce support tooling can evaluate agent-first configurations without changing their CRM backend. Source: [Google News](https://news.google.com/rss/articles/CBMinAFBVV95cUxQVm84WGw5VGFvSTk3VU41dE9iQXdtenRUQzNiRnBvSlZkbVQ4OExBNjB1YTFXMUZJUXFzQU5hZzVJMno3SHBPeWxfdS1sYUd2Q3VxeXJ0UWo5blNuT3J6dmtQejZsV01UMnNyai16XzJfY2VKZVdnc3ZEN3p0M1J3MGQ1d1Z4b042eEdWU2RKTlFFNXB4cTJ3cUZwdks?oc=5)
---
### Practical & Community
**Zai ZCube Network Architecture: r/LocalLLaMA**
Zai replaced a standard ROFT network with its ZCube flattened bipartite topology on a thousand-GPU GLM-5.1 inference cluster. The change cut switch and optical module costs 33%, raised throughput 15%, and reduced P99 first-token latency 40.6% while keeping the same GPUs and model. The design specifically addresses asymmetric KV cache traffic created by prefill-decode disaggregation. Teams running large-scale disaggregated inference should examine the topology details. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tq35a0/zai_replaced_the_network_architecture_running/)

**pgvector Semantic Search Tutorial: MarkTechPost**
A complete Colab notebook demonstrates building semantic, hybrid, sparse, and quantized vector search inside PostgreSQL with the pgvector extension. The guide covers extension compilation, Psycopg integration, SentenceTransformers embeddings, and index configuration. Developers wanting to avoid separate vector databases can run the notebook to test production-grade search inside an existing Postgres instance. Source: [marktechpost.com](https://www.marktechpost.com/2026/05/28/a-coding-guide-to-implement-a-pgvector-powered-semantic-hybrid-sparse-and-quantized-vector-search-system/)

**Qwen-Image-Bench on Hugging Face: r/LocalLLaMA**
Qwen released Q-Judger, a 27B vision-language model fine-tuned to score text-to-image outputs across five top-level quality dimensions with structured JSON output and chain-of-thought reasoning. The model supports fine-grained evaluation of realism, composition, anatomy, and safety attributes. Anyone building automated image generation pipelines now has an open judge model to integrate. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tpww8m/qwenqwenimagebench_hugging_face/)

**Multi-User Local LLM Setup: r/LocalLLaMA**
A user shared a working stack using vLLM behind llama-swap and LibreChat for multi-user access with API keys and HTTPS termination via Apache. The setup targets fewer than ten concurrent users and highlights current concurrency limits in llama-swap. Teams needing simple self-hosted multi-tenant inference can adapt the described proxy and key-management pattern. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tq0cj7/local_run_for_multi_users_which_software_set/)
---
### Under the Hood: Asymmetric KV Cache Traffic in PD-Disaggregated Inference
Everyone treats prefill-decode disaggregation as a simple split that just needs more GPUs. In practice the KV cache handoff between prefill and decode nodes creates highly directional, bursty traffic that standard fat-tree or rail-optimized topologies were never designed to carry. The prefill side generates large contiguous KV blocks that must cross the network in a short window, while decode nodes request smaller, latency-sensitive slices on different schedules. This mismatch produces leaf-switch hotspots and PFC backpressure even when aggregate bandwidth looks sufficient. Zai’s flattened bipartite design removes the spine layer entirely so every leaf pair has a direct path, eliminating the static rail mapping that forces traffic through congested spines. The 33% hardware cost reduction and 40% tail-latency improvement come directly from removing those forced hops rather than adding more bandwidth. When your decode cluster is larger than your prefill cluster or when context lengths vary widely, the topology choice matters more than raw switch speed. The practical test is whether your first-token P99 stays flat as you scale the decode pool; if it climbs, the network mapping is the next place to look.
---
### Things to Try This Week
- Run the Perplexity Unigram tokenizer in a reranker pipeline to measure the reported 5x latency drop on your workload.
- Test spiritbuun’s fork plus mudler’s APEX quant on Qwen3.6-35B-A3B if you need 70k+ context on a 12 GB card.
- Evaluate Krasis on an Ampere laptop GPU for models that previously required two cards.
- Add pgvector hybrid search to an existing Postgres application before reaching for a dedicated vector store.
- Prototype a simple agent governance check using Snowflake’s new Natoma integration if you already store agent traces there.
---
### On the Horizon
- More inference providers are expected to announce continuous-improvement loops similar to CoreWeave’s platform.
- Additional open tokenizers targeting reranker and long-context workloads are likely following Perplexity’s release.
- Watch for further single-GPU quantization results on the Qwen3.6 family as the new forks mature.