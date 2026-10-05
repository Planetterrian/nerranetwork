# Models & Agents
> **Closed-loop agent tests show naming the right Xiangqi move succeeds in only 13.9 percent of trials once an engine defender responds.**

**What You Need to Know:** Today's arXiv releases include XiangqiBench exposing large gaps between static move naming and actual closed-loop wins for frontier LLMs, HakemBench a Turkish typed-decision benchmark with 2,346 items, and SymCE a corpus of 4,707 false conjectures paired with Python verifiers that reveals an imitation trap under supervised fine-tuning. FinDialogLens demonstrates a hybrid pipeline reaching 92.1 percent accuracy on final price in multi-party financial chatrooms while cutting LLM calls by 85 percent via routing. Builders should watch the shift toward executable, outcome-scored agent benchmarks and verifier-driven training loops.
---
### Top Story
XiangqiBench introduces an executable benchmark that measures whether LLM agents can deliver checkmate against an engine defender in 119 tactical Chinese-chess endgames. The work records 8,568 multi-turn trajectories from 12 frontier models and identifies three overstatements of competence. Models play the stored reference first move in 26.1 percent of sighted trials yet only 13.9 percent of those trials end in a win. The leading model reaches 38.7 percent pass@3 but only 5.9 percent pass^3, winning all three trials on just 7 of the 46 positions it ever solves. Thirty-two point three percent of accepted simulation calls stop on an illegal move and in 49.3 percent of comparable cases the real defender replies differently from the simulated line. The benchmark supplies an interactive REPL that separates real moves, state queries and forward simulation. Source: [arxiv.org](https://arxiv.org/abs/2610.02425)
---
### Model Updates
**HakemBench: A Turkish Benchmark of Typed Decisions: arXiv NLP**
HakemBench version 1.0 contains 2,346 items and 4,275 choice, yes/no and score questions across seven tracks. A single harness scores decision quality via macro F1, calibration via normalised Brier score and selective automation via normalised area under the generalised risk-coverage curve, then combines them by geometric mean with 2,000 bootstrap intervals. On a board of 16 rows the leader reaches a composite of 0.888 while the submitting lab's model sits seventh at 0.660 on all tracks and sixth at 0.678 when restricted to the four non-contaminated tracks. The corpus is released under CC BY 4.0. Source: [arxiv.org](https://arxiv.org/abs/2610.02293)

**Counterexample Generation via Per-Theorem Symbolic Verifiers: When Imitation Hurts and Reinforcement Repairs: arXiv NLP**
SymCE supplies 4,707 false undergraduate-algebra and real-analysis conjectures each paired with an executable Python verifier that also serves as the reward function. Training Qwen3-4B with supervised fine-tuning on counterexamples alone collapses true-theorem recognition from 0.27 to 0.00 while GRPO with sparse outcome-only reward raises it to 0.66. The collapse replicates on Gemma-3-4B. The resulting 4B model outperforms every evaluated 7B open-weights math specialist and remains competitive with six frontier commercial APIs on GSM8K, MATH-500 and MMLU-college-math. Source: [arxiv.org](https://arxiv.org/abs/2610.02444)

**FinDialogLens: Event Extraction over Multi-Party Dialogue for Missed-Trade Identification in Financial Chatrooms: arXiv NLP**
FinDialogLens combines compact fine-tuned classifiers that detect RFQ-triggers and price/trade metadata with an RFQ-Level Module and Trade Engine. GPT-4o reaches 92.1 percent accuracy on final price and 94.3 percent on trade outcome. A difficulty-aware router allocates requests between a rule-based engine and the LLM Trade Engine, cutting LLM calls by 85 percent on final price while recovering half the accuracy gap and saving over 300 dollars per day at 70,000-RFQ daily scale. Fine-tuned open-source models as small as 3B parameters achieve comparable performance with modest in-domain data. Source: [arxiv.org](https://arxiv.org/abs/2610.02455)

**From Retrieval to Typed Decisions: Calibrated System One Models from Biomedical Sentence Encoders: arXiv NLP**
SBERT2S1 converts Sentence-Transformers encoders into bi-encoder, cross-head and prior-fused residual decision models. Retrieval training improves zero-shot matching of content-bearing options and, after fine-tuning, significantly helps the prior-fused residual head in 10 of 15 comparisons across five pairs and three training-set sizes. The cross-head architecture outperforms the prior-fused residual head under every training objective. A human audit of 177 verifier decisions finds 97.7 percent accuracy. Source: [arxiv.org](https://arxiv.org/abs/2610.02486)

**Large Language Continuous Diffusion Models: arXiv NLP**
Sigma is the first large-scale 3B/8B continuous diffusion language model built on steerable low-dimensional ODE/SDE latent trajectories. After pre-training it matches discrete masked diffusion and autoregressive baselines on GSM8K, Minerva, HumanEval and MBPP; after supervised fine-tuning it remains competitive on MATH-500 and AIME. Classifier-free guidance and score temperature are identified as essential for high-fidelity reasoning and coding. Embedding-space steering governs the quality-diversity trade-off and continuous trajectories enable graceful degradation at low NFEs. Source: [arxiv.org](https://arxiv.org/abs/2610.02665)

**A generative-informed neuro-symbolic framework for syntactic ambiguity resolution: Evidence from Arabic DPs: arXiv NLP**
The framework integrates generative syntactic notions with AraBERT by representing ambiguity as a candidate-based decision task. On the unseen evaluation set it achieves 96.88 percent accuracy, 95.92 percent macro-F1, 96.83 percent weighted F1 and 93.94 percent binary F1. Recall reaches 99.71 percent for High/VP Attachment and 89.26 percent for Low/NP/Embedded Attachment. Source: [arxiv.org](https://arxiv.org/abs/2610.02529)
---
### Agent & Tool Developments
**CUEing User Simulators: Calibrated User Embeddings for Multi-Turn Benchmarking: arXiv NLP**
Calibrated User Embeddings encode observed sessions and sample continuous representations that decode into persona commands without training. On tau-squared-Bench the simulators commit fewer simulator-attributed errors and more faithfully reproduce real-user agent failure modes, aggregate success rates and outcomes for specific task-user pairs. After fitting to mostly customer-support interactions the same simulators generalise to document creation, math tutoring and casual conversation across different simulator LLMs. Source: [arxiv.org](https://arxiv.org/abs/2610.02460)

**APDMem: Agent-Controlled Progressive Disclosure for Query-Adaptive Long-Term Memory: arXiv NLP**
APDMem represents conversation history as four progressively detailed layers: thematic summaries, personalised key facts, turn-level evidence notes and raw messages. A controller applies progressive disclosure so simple queries terminate early while complex temporal or multi-hop queries trigger deeper inspection. On LongMemEval the architecture achieves strong performance while accessing only 8 percent of total conversations. Source: [arxiv.org](https://arxiv.org/abs/2610.02472)

**EpiWorld: Grounding LLM Policy Agents in Epidemiological World Models: arXiv NLP**
EpiWorld grounds an LLM policy actor in a learned action-conditioned epidemiological world model and a tiered skill library of public-health protocols. The world model achieves the best out-of-distribution Peak-MAE among forecasting baselines. The closed-loop framework reduces cumulative hospitalisation by up to 59 percent across COVID-19 and Influenza datasets and by an average of approximately 16 percent across six LLM backbones. Source: [arxiv.org](https://arxiv.org/abs/2610.02744)

**Beyond Correctness: Resolving Underspecification in Agentic Text-to-SQL: arXiv NLP**
PlanPool externalises the clarification plan as a mutable question pool that every planned question must be explicitly asked or dropped before submission. Across three benchmarks derived from BIRD-Interact and Spider the approach improves ambiguity coverage and reduces silent failures over unconstrained and prompt-based alternatives while maintaining competitive execution accuracy. Source: [arxiv.org](https://arxiv.org/abs/2610.02739)
---
### Practical & Community
**TPBench: A Turning-Point Benchmark for Dialogue Compression: arXiv NLP**
TPBench evaluates three information targets at shared nominal retention budgets: the user's initial goal, the current value of a revised slot, and both in dialogues containing a late annotated slot update. On the joint probe at 0.30 retained fraction every tested compressed method remains below full context with the main Llama reader. Deleting the turn that carries the update sharply lowers current-value accuracy while deleting one matched irrelevant turn leaves it unchanged. Source: [arxiv.org](https://arxiv.org/abs/2610.02736)

**ConvoDrift: A Multi-Turn Conversational Dataset for Modeling Stylistic Tone Evolution: arXiv NLP**
ConvoDrift contains 15,727 shared multi-turn conversational structures with six prompt-response pairs per conversation annotated for style drift and style direction. Across seven Likert criteria annotated by three human annotators the average Krippendorff's alpha reaches 0.88. Drift events induce lexical changes while preserving semantic similarity. Source: [arxiv.org](https://arxiv.org/abs/2610.02873)

**Evaluating LLM-as-a-Judge Beyond Score Alignment: A Psychometric Analysis of Residual Judging Difficulty: arXiv NLP**
Many-Facet Rasch Models decompose scores into latent summary quality, rater severity, dimension severity and rating-scale thresholds. Across 17 open-weight LLM judges on SummEval moderate alignment in latent summary quality does not imply alignment in residual hardness. Human and LLM judges differ in which summary-dimension units remain difficult, with the mismatch strongly dimension-dependent. Source: [arxiv.org](https://arxiv.org/abs/2610.02877)

**Evaluating VQA in Vision Language Models using Cooperative Principles: arXiv NLP**
VLMs generate question modifiers that add non-essential, ambiguous or false information. In the presence of such violations ChatGPT, Claude, Gemini and Llava all show diminished performance. Human cognitive effort measured through time-on-task is lower for resolving VLM-induced violations yet VLMs themselves perform less accurately in those cases. Source: [arxiv.org](https://arxiv.org/abs/2610.02878)
---
### Under the Hood: Hierarchical Progressive Disclosure for Long-Term Memory Retrieval
The gap between flat retrieval and adaptive memory access appears most clearly when query complexity varies inside a single long conversation. A controller that first reads thematic summaries and only drills into turn-level evidence when needed creates an automatic cost-fidelity trade-off. Simple queries terminate after the first layer while temporal or multi-hop queries expand to raw messages, cutting total tokens examined to roughly eight percent on LongMemEval. The engineering cost is an extra synthesis step that consolidates retrieved evidence and flags contradictions before final generation. When the controller misjudges query difficulty the system either wastes tokens on unnecessary detail or returns incomplete context. The practical decision rule is to adopt progressive disclosure whenever average conversation length exceeds a few thousand tokens and query types mix factual lookup with multi-hop reasoning; otherwise a single-granularity retriever remains simpler and sufficient.
---
### Things to Try This Week
- Run the XiangqiBench interactive REPL against any frontier model you have API access to and measure your own conversion gap between first-move accuracy and final win rate.
- Download the SymCE corpus and verifiers from the linked GitHub repository to test GRPO training on a 4B-class model for counterexample generation.
- Apply the FinDialogLens difficulty-aware router pattern to any multi-party dialogue task where LLM call volume is the dominant cost driver.
- Fit Calibrated User Embeddings on your own customer-support logs and evaluate whether the resulting simulators reproduce your observed agent failure modes on tau-squared-Bench style tasks.
---
### On the Horizon
- Expect further executable agent benchmarks that score closed-loop outcomes rather than static answer correctness.
- Watch for additional verifier-driven reinforcement-learning environments released alongside math and code corpora.
- Look for hybrid routing systems that combine rule-based engines with LLM components to appear in production financial and customer-support tooling.
