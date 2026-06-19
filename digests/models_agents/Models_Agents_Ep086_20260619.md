# Models & Agents
> **Custom CUDA kernels now keep vector search inside the GPU for agentic RAG, cutting PCIe round-trips that silently throttle long-horizon agents.**

**What You Need to Know:** OpenAI reports GPT-5.5 Instant now matches its frontier models on health queries for free users. A new GPU-resident Top-K kernel delivers deterministic microsecond tail latencies for retrieval. Research papers introduce selective multi-turn distillation, cache-aware RAG ordering, atomic-fact memory for agents, and head-level attention hybridization. Builders should test the kernel and memory systems this week on retrieval-heavy workflows.
---
### Top Story
A developer built and open-sourced a CUDA kernel that performs Top-K vector search entirely on-GPU, eliminating the PCIe transfer latency that previously forced retrieval results to bounce off the CPU during agentic RAG inference. The approach replaces standard CPU-mediated vector search with a device-resident kernel, producing deterministic microsecond-scale tail latencies instead of variable round-trip costs. This directly addresses the silent bottleneck in long-horizon agents where retrieval happens repeatedly inside tool loops. The change preserves answer quality while making tail latency predictable, which matters for production agent deployments that must meet strict response-time SLAs. Teams building retrieval-augmented agents should benchmark the kernel against their current retrieval step this week. Source: [towardsdatascience.com](https://towardsdatascience.com/gpu-resident-top-k-for-agentic-rag-i-built-a-cuda-kernel-so-my-retrieval-step-would-stop-bouncing-off-the-gpu/)
---
### Model Updates
**GPT-5.5 Instant health capabilities: OpenAI**
GPT-5.5 Instant now matches OpenAI’s frontier Thinking models on health-related questions. The model improves at recognizing when urgent care is needed, asking for relevant context, explaining uncertainty, and simplifying complex information. More than 230 million people weekly ask ChatGPT health questions, so the gains reach free-tier users immediately. Physician-led evaluation drove the improvements. Builders working on consumer health tools should test GPT-5.5 Instant against paid frontier models for cost-sensitive deployments. Source: [x.com](https://x.com/OpenAI/status/2067672740539306261)

**IHUBERT Persian PLM: arXiv**
IHUBERT is a 125M-parameter RoBERTa-base model trained from scratch on a curated 45 GB Persian corpus. It leads on extractive QA for PQuAD (F1 88.3542) and ParsiNLU-RC (F1 49.0987) while remaining competitive on NER and topic classification. A vector-database semantic deduplication step balanced domain coverage during pretraining. Persian NLP teams should try it for QA and retrieval tasks where prior models underperformed. Source: [arxiv.org](https://arxiv.org/abs/2606.20089)

**TerraMARS domain-adapted pipeline: arXiv**
TerraMARS fine-tunes Gemma 3 1B with QLoRA on Mars-specific QA and information-extraction data, then converts scientific literature into structured JSON. The pipeline targets atmosphere, hydrology, and surface-chemistry questions relevant to habitability modeling. Output quality still requires further accuracy gains before downstream digital-twin use. Researchers working on scientific literature extraction should examine the multistage chunking and retrieval framework. Source: [arxiv.org](https://arxiv.org/abs/2606.19700)
---
### Agent & Tool Developments
**SAGE-OPD multi-turn distillation: arXiv**
SAGE-OPD adds selective teacher intervention, confidence-weighted token distillation, and loss normalization to on-policy distillation for multi-turn agents. On ALFWorld it delivers up to 13.3% relative improvement in unseen success rate over standard OPD. The method skips turns when environment feedback indicates no intervention is needed and reduces influence of uncertain teacher signals on corrupted histories. Agent developers facing compounding errors in long trajectories should test the turn-level selection logic. Source: [arxiv.org](https://arxiv.org/abs/2606.19659)

**AtomMem atomic-fact memory: arXiv**
AtomMem extracts high-value atomic facts from long interactions via a Fact Executor, then organizes them into hierarchical event structures and temporal user profiles. Retrieval uses an associative memory graph to connect fragmented episodes. On the LoCoMo benchmark it reaches state-of-the-art results for multi-session reasoning tasks. Teams building personalized agents should evaluate the fact-extraction step against coarser memory representations. Source: [arxiv.org](https://arxiv.org/abs/2606.19847)

**CacheWeaver evidence ordering: arXiv**
CacheWeaver maintains a prefix tree of recently served evidence sequences and greedily reorders retrieved documents to maximize prefix-cache hits in vLLM. It reduces median TTFT by 20-33% relative to retrieval-order caching across three vLLM configurations without changing answer quality. The greedy policy recovers 97.5% of an oracle ordering’s gains. RAG teams hitting prefix-cache misses on overlapping evidence should integrate the lightweight scheduling layer. Source: [arxiv.org](https://arxiv.org/abs/2606.19667)

**Streaming tool-intent stabilization: arXiv**
The study measures when speculative tool queries in streaming RAG converge to the correct result before the user finishes typing. At realistic settings (600 ms tool latency, 3 words/second input), 73.9% of CRAG questions admit substantial latency hiding. Query-type analysis shows early stabilization is predictable enough to justify learned triggers. Developers shipping low-latency retrieval agents should examine the stabilization distribution on their own query logs. Source: [arxiv.org](https://arxiv.org/abs/2606.20113)
---
### Practical & Community
**STAGE text-to-JSON generation: arXiv**
STAGE uses spreadsheet-grounded LLM synthesis to create paired reports and JSON schemas, validating every ground-truth value against the source spreadsheet. On the 851-example STAGE-Eval set it lifts Qwen3-4B exact match from 31.37% to 74.27%. The pipeline removes the usual hallucination risk in synthetic structured-data creation. Teams extracting from financial or clinical documents should compare STAGE-generated training data against purely synthetic baselines. Source: [arxiv.org](https://arxiv.org/abs/2606.20072)

**GEMS multi-semantic steering: arXiv**
GEMS applies norm-preserving superposition and real-time orthogonalization so multiple non-orthogonal directions can be injected into the residual stream without collapse. On GSM8K it preserves 98% accuracy while adding three concurrent non-mathematical directions; unconstrained addition drops to 4%. The method works across 3B–31B models with no retraining. Alignment and control researchers should test the orthogonalization step on refusal and style vectors. Source: [arxiv.org](https://arxiv.org/abs/2606.19946)

**HydraHead head-level hybridization: arXiv**
HydraHead fuses full and linear attention at head granularity rather than layer granularity, preserving full attention only on retrieval-critical heads. After a three-stage transfer pipeline it matches a 3:1 layer-wise hybrid’s long-context performance at a 7:1 LA-to-FA ratio while training on only 15B tokens. The approach yields >69% improvement over baseline at 512K context. Long-context model builders should study the interpretability-driven head-selection method. Source: [arxiv.org](https://arxiv.org/abs/2606.20097)
---
### Under the Hood: Head-Level Attention Hybridization
Everyone talks about hybrid attention as a simple layer-wise swap between full and linear attention. In practice the decision is finer-grained because heads inside the same layer already specialize: some focus on retrieval while others handle local patterns. HydraHead therefore keeps full attention only on the retrieval-critical heads identified through interpretability analysis and routes the rest through linear attention. Orthogonalization prevents the distributional shift that would otherwise accumulate when mixing the two output distributions. The resulting model reaches 69% gains at 512K context after training on just 15B tokens, showing that head-level selection recovers most of the quality of denser hybrids at far lower cost. When your workload is retrieval-heavy and context exceeds 128K, start with head-level hybridization rather than uniform layer replacement; the main gotcha is that head selection must be redone when the base model or domain changes.
---
### Things to Try This Week
- Test the open-sourced GPU-resident Top-K kernel on your current RAG agent loop to measure tail-latency reduction on repeated retrieval steps.
- Run AtomMem’s Fact Executor on a multi-session conversation dataset and compare fact density against summary-based memory baselines.
- Apply CacheWeaver’s prefix-tree reordering to an existing vLLM deployment handling overlapping evidence sets and record TTFT changes.
- Evaluate STAGE-generated JSON training data on your own extraction task before investing in manual annotation.
- Experiment with GEMS orthogonalization when steering multiple style or safety vectors simultaneously in a 7B–13B model.
---
### On the Horizon
- Watch for production deployments of head-level hybrid models once the 15B-token training recipe is reproduced at larger scale.
- Expect more agent memory systems built around atomic facts as LoCoMo results propagate.
- Monitor open-source releases of selective multi-turn distillation code following the SAGE-OPD ablations.
- Track whether streaming tool stabilization triggers appear in major agent frameworks within the next quarter.