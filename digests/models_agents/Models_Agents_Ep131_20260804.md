> **# Models & Agents**
OpenAI’s next internal model just produced ten new results on long-standing math and theoretical computer science problems for roughly $2,000 in tokens.

**What You Need to Know:** OpenAI reported that an internal version of its next major model solved ten open problems in mathematics and theoretical computer science using about $2,000 worth of tokens at GPT-5.6 Sol API rates. The same day, Y Combinator open-sourced QM, a multiplayer agent harness that gives every Slack room scoped memory, files, and permissions. Builders should watch how these developments shift both frontier reasoning cost curves and practical agent deployment patterns this week.
---
### Top Story
OpenAI announced that an internal version of its next major model produced ten new results on long-standing open problems in mathematics and theoretical computer science. The work used roughly $2,000 worth of tokens at GPT-5.6 Sol API rates, showing that test-time compute at frontier scale can now target unsolved research questions rather than only benchmark tasks. This sits in the ongoing frontier-models arc that was active yesterday, where closed labs continue trading capability leads while cost trajectories drop. The result matters for teams that need reliable reasoning on hard, open-ended problems instead of just higher benchmark scores. Watch for whether similar internal runs appear in public APIs or whether the pattern spreads to other labs. Source: [x.com](https://x.com/OpenAI/status/2084352161404920316)
---
### Model Updates
**Qwen 3.8 Max and MiniMax-H3 released hours apart: Simon Willison (AI builder)**
Two new large models appeared within hours of each other. Qwen 3.8 Max joins the Qwen family while MiniMax-H3 arrives from a separate lab. No public benchmarks or parameter counts were shared in the announcement. Builders should test both against current Qwen and DeepSeek releases on reasoning and coding tasks this week to map the latest open-weight frontier. Source: [x.com](https://x.com/simonw/status/2084122690189918549)

**DeepSeek tops China AI model ranking: news.cgtn.com**
DeepSeek now leads Chinese model rankings according to the latest evaluation. The result reinforces the ongoing narrowing of the open-weight versus closed-model gap that the show has tracked since yesterday. Teams choosing between domestic and international providers should re-run their standard evals on the newest DeepSeek checkpoint. Source: [news.cgtn.com](https://news.google.com/rss/articles/CBMiswFBVV95cUxOUnEwc1h2dXpNaXRyaVcyVlM0ZGNKbVlYemhOZGhldF90bzdpZ3c2d3dnbFoybE9pRlFLZGc4RlVrTUY5RDF0UlhKUWh4ZDhOVmYwUVNSUHlUQTdxa18xb3NNX0VFbXJGcXhWLU1LOGl0V09Tb04yRG9xTWRwMUZkT0VvNjM4MnRmbEw2WnJraHkzU3ZCWlJxMHdiME5yR0lPb3JPVzdjZ0RoclpjNDhDYUswOA?oc=5)

**DLLM-TTS block discrete diffusion model: arXiv NLP**
A 0.6B-parameter model called DLLM-TTS formulates text-to-speech as conditional block discrete diffusion over X-Codec2 tokens. It reaches a real-time factor of 0.15 while remaining competitive on the Seed-TTS-eval benchmark after training on 20K hours of data. The approach trades sequential autoregressive decoding for parallel block prediction. Builders working on on-device or low-latency voice synthesis should try the open weights once released. Source: [arxiv.org](https://arxiv.org/abs/2608.00011)

**DiffusionGemma technical report: arXiv NLP**
DiffusionGemma fine-tunes the 3.8B-active / 25.2B-total Gemma 4 mixture-of-experts model with discrete diffusion to generate roughly 20 tokens per forward pass and about 1,500 output tokens per second on a single H100. The two-stage training used less than 10% of the original model’s token budget. It keeps support for thinking mode, multimodal inputs, and long context while adding a hybrid diffusion-AR path. Teams needing high-throughput generation should benchmark it against current speculative-decoding setups. Source: [arxiv.org](https://arxiv.org/abs/2608.00146)
---
### Agent & Tool Developments
**MCP server fitness-tracker example: Simon Willison (AI builder)**
Simon Willison shared a Datasette-based MCP server as a starting point and described extending it into a fitness tracker that logs weights and reps. Once the basic MCP connection works, additional tools become straightforward to add. Developers building personal-data agents should clone the repo and wire it to their own logging workflows this week. Source: [x.com](https://x.com/simonw/status/2084477749549494502)

**Y Combinator open-sources QM multiplayer agent harness: MarkTechPost**
Y Combinator released QM under an MIT license on July 31, 2026. The harness gives each employee an isolated workspace and each Slack room its own scoped memory, files, keychain, permissions, crons, and web apps. Pi, OpenCode, Codex, and Claude Code all drive the same headless core, avoiding vendor lock-in. Teams running multi-user agent workflows inside Slack should evaluate QM as a drop-in coordination layer. Source: [marktechpost.com](https://www.marktechpost.com/2026/08/03/y-combinator-open-sources-qm-multiplayer-ai-agent-harness/)

**MemoryForge lifelong memory synthesis: arXiv NLP**
MemoryForge synthesizes autobiographical memory bases from brief target personas using a context generator, life organizer, and multi-resolution simulator. On PersonaGym and SimulatorArena it produces more human-like role-play and user-simulation behavior than static profile conditioning across multiple LLM backbones. Builders creating persistent agents should test the synthesized memory approach instead of prompt-only persona injection. Source: [arxiv.org](https://arxiv.org/abs/2608.00007)

**AgentMemBench long-term memory benchmark: arXiv NLP**
AgentMemBench evaluates five memory strategies across LoCoMo, MultiDoc2Dial, and MSC using Recall@k, MRR, and LLM-judge faithfulness. External key-value store (EKV) dominates every quality axis while in-context windowing, summarization, and graph methods collapse on long-horizon recall. The benchmark and code are released for full reproducibility. Teams building conversational agents with multi-session memory should adopt EKV or run the harness on their own data. Source: [arxiv.org](https://arxiv.org/abs/2608.00009)
---
### Practical & Community
**RubricReviewer rubric-driven peer review: arXiv NLP**
RubricReviewer separates rubric generation as an explicit step before review writing and combines a training-free Scout agent with a trained Aligner model. It produces more comprehensive and discriminative reviews than prior systems while showing stronger robustness to adversarial prompt injection. Authors and conference organizers should test the framework on real submissions this cycle. Source: [arxiv.org](https://arxiv.org/abs/2608.00005)

**SeDeM selective decompression for long-context QA: arXiv NLP**
SeDeM extracts hidden states from an intermediate Transformer layer, compresses them into memory blocks, and selectively decompresses only query-relevant blocks into the decoder. On four long-context QA benchmarks it outperforms prior compression methods in both 1B and 3B settings and exceeds full-context fine-tuning on three datasets with the 3B backbone. The approach reduces time-to-first-token and improves throughput versus ICAE. Retrieval-augmented teams should evaluate the selector on their own document collections. Source: [arxiv.org](https://arxiv.org/abs/2608.00311)

**XL-DocBench extra-long document benchmark: arXiv NLP**
XL-DocBench contains 1,519 human-verified questions from six professional domains with contexts up to 2,303 pages; 72.6% require multiple evidence pages and 36.6% involve tables or figures. Current systems still struggle with multi-page evidence and structured reasoning over professional documents. Compliance and legal teams should add the benchmark to their evaluation suites. Source: [arxiv.org](https://arxiv.org/abs/2608.00036)
---
### Under the Hood: Capability-Driven Multimodal Scaling Laws
Everyone talks about scaling laws as if bigger models simply get better at everything. In practice the new Capability-Driven Multimodal Scaling Law shows that VLM performance is better predicted from a low-dimensional textual capability score extracted via PCA than from raw compute. The framework measures a per-backbone transfer rate and an absorption rate that quantifies how efficiently additional multimodal data improves results. Experiments training over 150 VLMs across seven model families confirm the law extrapolates from 8B to 72B backbones and generalizes to held-out families. Base LLMs consistently outperform instruction-tuned counterparts because they exhibit higher absorption rates and slower data-scaling decay. The practical takeaway is that backbone selection can now be treated as a quantitative decision rather than an empirical sweep: run the textual capability score first, then choose the family with the best transfer-absorption profile for your target multimodal benchmarks.
---
### Things to Try This Week
- Run the open QM harness inside a Slack workspace to test scoped memory and multi-user agent coordination without vendor lock-in.
- Clone Simon Willison’s Datasette MCP example and extend it with a simple personal logging tool such as weight tracking to explore custom MCP servers.
- Benchmark the new DiffusionGemma weights against your current speculative-decoding setup on high-throughput generation workloads.
- Add AgentMemBench and XL-DocBench to your evaluation harness if you maintain long-context or multi-session agents.
- Test SeDeM-style selective hidden-state decompression on your largest RAG collections to measure time-to-first-token gains.
---
### On the Horizon
- Further public releases or API access tied to OpenAI’s internal next-gen model that produced the recent math results.
- Additional open-weight checkpoints from the Qwen and MiniMax families following this week’s paired launches.
- Expanded agent harness features from the newly open-sourced QM project as more teams integrate it.
- New long-context and memory-management papers building on the benchmarks released today.