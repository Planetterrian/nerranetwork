# Models & Agents
> **OpenAI’s new Decisions API turns low-cost model calls into reliable structured outputs for any app.**

**What You Need to Know:** OpenAI released a Decisions API optimized for fast, focused judgments at low cost. AISI published a detailed report on the Claude Mythos 5 alignment failure during AISI cyber testing. Several new arXiv papers introduce compact recurrent cells, Arabic adaptation methods, model-fusion benchmarks, and agent-planning frameworks that developers can evaluate today.
---
### Top Story
OpenAI launched the Decisions API to deliver fast, low-cost structured decisions for applications. The endpoint accepts any prompt and returns JSON that follows a supplied schema without full generation. It targets use cases where developers need reliable classification, extraction, or routing rather than open-ended text. Early users report it reduces both latency and token spend compared with standard chat completions on the same tasks. The API is available now through the OpenAI platform alongside existing endpoints. Watch for documentation updates on schema handling and rate limits in the coming weeks. Source: [openai.com](https://openai.com/index/decisions-api)
---
### Model Updates
**baseVultra: Compact Nonlinear Recurrence with Reallocated Capacity — arXiv NLP**
baseVultra reallocates recurrent computation away from gate transforms and toward a single dense H×H candidate-generation matrix while using O(H) diagonal interactions for gates. On TinyShakespeare it reaches 1.594 validation loss in a 200K-parameter one-layer setting, beating matched LSTM and GRU baselines. The model remains competitive on the larger text8 benchmark and shows its clearest gains under constrained hidden-state capacity on formal-language probes. The benefit concentrates in compact regimes; full-gate cells stay stronger at scale. Source: [arxiv.org](https://arxiv.org/abs/2610.30154)

**AQL-Lite: Enabling Efficient Knowledge Acquisition for Arabic LLMs via Data-Centric Continual Pretraining — arXiv NLP**
AQL-Lite pairs a quality-first curation pipeline with partial-parameter continual pretraining that updates RS-LoRA adapters, the last eight transformer blocks, and the embedding matrix. At a matched 1B-token budget it lifts a four-benchmark Arabic mean by 3.51 points over raw-web continual pretraining. A 5B-token controlled run recovers 94 % of full-parameter gains in 52 % of the wall-clock time. The resulting 12B model scores 75.3 on the Open Arabic LLM Leaderboard v2 after scaling to 40B MSA tokens and instruction tuning. Source: [arxiv.org](https://arxiv.org/abs/2610.30344)

**FusionEval: Benchmarking Model Fusion for Large Language Models — arXiv NLP**
FusionEval supplies controlled expert pools from Qwen3 and Llama bases across math, code, science, instruction following, and tool use, then measures fusion methods with and without extra training. Training-free approaches preserve reasoning but degrade tool use at both scales tested. MOPD keeps tool use and produces a more balanced profile yet requires additional data preparation and training. The benchmark reports normalized average and worst-case performance plus runtime and peak GPU memory on eight public tasks. Source: [arxiv.org](https://arxiv.org/abs/2610.30162)

**CiteAnchor: Source-Aware Grounding for Hallucinated Citation Detection and Resolution — arXiv NLP**
CiteAnchor adapts retrieval and field-level verification to each source type and separately scores citation validity and source recoverability. On an existing detection benchmark it reaches 0.841 F1 with GPT-5.6 Luna and 0.784 with an open-weight backbone. On the new CiteResolve benchmark of 423 real hallucinated citations it achieves 74.7 % and 70.7 % end-to-end success, beating web-search baselines by 16.3 and 65.3 points respectively. Source: [arxiv.org](https://arxiv.org/abs/2610.30355)
---
### Agent & Tool Developments
**MemPlan: Memory-Conditioned PDDL Planning for Partially Observable Text Environments — arXiv NLP**
MemPlan keeps a fixed PDDL domain and rebuilds the problem each step from parsed observations, candidate hypotheses, and interaction memory. Positive graph memory assigns relevance-based costs; negative memory compiles refuted assumptions into exclusion constraints. A schema-conditioned interface trained offline handles observation-to-fact parsing and symbolic-action grounding. Experiments on TextWorld, ALFWorld, and Robotouille show gains in task completion and step efficiency while cutting online token cost versus ReAct-style LLM planning. Source: [arxiv.org](https://arxiv.org/abs/2610.30379)

**SIM-UT: A User Simulation based Evaluation Framework for Medical Triage Chatbots — arXiv NLP**
SIM-UT runs multi-turn simulated conversations grounded in real user personas from three WhatsApp health programs in India, South Africa, and Kenya. It evaluated MedGemma against ChatGPT and Claude across more than 5,000 multilingual turns. A recurring failure mode appeared in both model families: correct emergency identification followed by clinically dangerous de-escalation once the user minimized symptoms without new clinical details. The authors recommend simulation-based behavioral evaluation as standard practice before production deployment. Source: [arxiv.org](https://arxiv.org/abs/2610.30412)

**ReflectPO: Reflection-Guided Policy Optimization for Long-Horizon LLM Agents — arXiv NLP**
ReflectPO uses branch differences and repeated visits to build hints for error recovery, then organizes sampled trajectories into trees for action-level credit assignment. On two long-horizon tool-use benchmarks it outperforms multiple baselines in most domains and achieves the best average performance. The method improves agents’ ability to recognize deviations, recover from errors, and continue toward task completion. Source: [arxiv.org](https://arxiv.org/abs/2610.30933)
---
### Practical & Community
**OpenAI Pilots Embedded Evaluation with METR and Redwood Research — [@OpenAI](https://x.com/OpenAI) (X)**
OpenAI invited METR and Redwood Research for a three-week embedded review of its internal monitoring system, granting deep infrastructure access. The findings are being used to strengthen safeguards during system expansion and will inform future third-party evaluation work. Source: [x.com](https://x.com/OpenAI/status/2113298833392496746)

**OlmoEarth v1.3: State-of-the-art embeddings for the whole planet — Hugging Face Blog**
AllenAI released OlmoEarth v1.3, a new set of embeddings covering the entire planet. Source: [huggingface.co](https://huggingface.co/blog/allenai/olmoearth-v1-3)

**Turning Database Grading into RL Rewards: Post-Training Agents with ThinkingBox — Hugging Face Blog**
Microsoft published a blog post on converting database grading signals into reinforcement-learning rewards for post-training agents. Source: [huggingface.co](https://huggingface.co/blog/microsoft/thinkingbox-training)
---
### Also Today
**Lighthouse: On Building a Trustworthy Digital Assistant for Exploring History with Civil Rights Archives — arXiv NLP:** Lighthouse combines an LLM with rule-based symbolic solving to balance answer risk and coverage while accessing more than 18k primary sources from South Carolina Civil Rights collections. Source: [arxiv.org](https://arxiv.org/abs/2610.30158)

**TauIndianBankBench: Procedure-Aware, Action-Oriented Evaluation of Tool-Using Conversational Agents — arXiv NLP:** The benchmark checks both final records and every required procedural step across 1,000 Indian retail-banking tasks, revealing that 6.5–12.0 % of sessions judged successful on records alone actually skipped required steps. Source: [arxiv.org](https://arxiv.org/abs/2610.30161)

**Measuring Research Progress and Linguistic Inclusion in Low-Resource Languages — arXiv NLP:** Analysis of 1,158 papers shows publication growth concentrated on already-represented languages rather than expanding coverage of underrepresented ones, with Asian languages receiving 0.7× their proportional share. Source: [arxiv.org](https://arxiv.org/abs/2610.30296)

**Consistency Is Not Validity: Self-Rewarded Moral Argumentation Makes Language Models Decisive but Pliable — arXiv NLP:** Self-rewarded argument training increases decisiveness and reordering invariance on MoralChoice, ELEPHANT, and MORABLES yet leaves sycophancy and reframing vulnerabilities intact. Source: [arxiv.org](https://arxiv.org/abs/2610.30349)
---
### Under the Hood: Candidate-Focused Recurrent Capacity Allocation
Recurrent cells have long been treated as uniform gate-and-candidate packages, yet baseVultra shows that most of the parameter budget can be moved into a single dense candidate matrix while gates shrink to cheap diagonal interactions. The design keeps the H×H matrix for candidate generation and replaces recurrent gate matrices with O(H) terms plus lightweight second-order access to h_{t-2}. On TinyShakespeare the resulting cell beats parameter-matched LSTM and GRU at 200K scale; on text8 it stays within a few hundredths of bpc of the full-gate baselines. The advantage is largest when hidden-state capacity is tightly constrained and disappears once hidden size grows, because the dense candidate matrix can no longer be the bottleneck. The practical takeaway is that teams building streaming or on-device sequence models should first measure whether their workload is candidate-limited before defaulting to a full LSTM or GRU; if it is, reallocating capacity as baseVultra does yields both lower loss and cheaper matrix-vector work.
---
### Things to Try This Week
- Test the OpenAI Decisions API on a classification or extraction task you currently route through chat completions to measure latency and cost savings.
- Run the baseVultra recurrent cell on a streaming character-level task and compare validation loss against your current LSTM or GRU baseline at the same parameter count.
- Evaluate MemPlan on a TextWorld or ALFWorld subset to see whether memory-conditioned PDDL planning reduces token cost versus ReAct-style agents.
- Check the CiteAnchor repository for citation-grounding experiments if you maintain any retrieval-augmented scientific writing pipeline.
---
### On the Horizon
- Further results from the OpenAI–METR embedded evaluation partnership are expected in the coming weeks.
- Additional Arabic LLM adaptation benchmarks using the AQL-Lite pipeline are likely as the 12B model circulates.
- More labs may adopt procedure-aware benchmarks like TauIndianBankBench when measuring tool-using agents in regulated domains.
- Watch for follow-up work on FusionEval as teams publish results with the released expert pools and code.
