# Models & Agents
> **Selective cross-model collaboration lifts frontier model accuracy from 23.1 percent to 28.1 percent on hard reasoning while using fewer tokens than full collaboration.**

**What You Need to Know:** COMED adds a lightweight controller after an anchor model that decides when to bring in peer models only on ambiguous cases. Today's arXiv batch also releases new benchmarks for kinship term generation, legal canon classification, and extractive legal summarization across 24 languages.
---
### Top Story
COMED introduces a post-anchor controller that accepts confident answers from a single model, probes peers only on ambiguous cases, and escalates to collaboration when rescue value exceeds harm. The method decomposes performance into rescued errors versus collaboration-induced harms and shows selective escalation improves results in all sixteen open-weight settings tested. On MedQA the approach adds up to 10.7 percentage points while invoking fewer models and decoding fewer tokens than dense collaboration. On the HLE benchmark COMED raises GPT-5.5 from 23.1 percent to 28.1 percent, beating both the anchor alone and full dense collaboration. The controller relies on anchor self-consistency, router margin, and a lightweight peer probe to make the decision. Source: [arxiv.org](https://arxiv.org/abs/2609.26913)
---
### Model Updates
**Recognized but Not Produced: A Generation Benchmark for Culturally Specific Kinship Terms — arXiv NLP**
Five open-weight models were tested on generating kinship terms in Hindi, Tamil, and Korean. GPT OSS120B selected the correct term in 90.67 percent of valid cells yet produced an accepted term in only 36.00 percent of the same cells. Llama 3.370B showed 77.92 percent selection accuracy versus 24.24 percent generation accuracy. Accuracy on explicitly specified L3 prompts ranged from 72.29 percent for GLM-5.1 to 24.24 percent for Llama-3.370B. The paternal-lineage advantage appeared strongly in Hindi but was weak or reversed in Korean. Source: [arxiv.org](https://arxiv.org/abs/2609.26942)

**Classifying Interpretive Canons at the Sentence Level: A Benchmark from the German Federal Constitutional Court — arXiv NLP**
A sentence-level dataset of German Federal Constitutional Court decisions was annotated for seven interpretive canons in the Larenz-Savigny tradition. Four LLMs from three families were evaluated under expert-written prompts and Genetic-Pareto optimized prompts. Mean F1 across the seven binary subtasks ranged between 70.4 and 79.2. Grammatical interpretation proved easiest to identify while systematic interpretation proved hardest. GEPA-optimized prompts did not systematically outperform the hand-written expert prompts. Source: [arxiv.org](https://arxiv.org/abs/2609.26945)

**LEGO: Synergizing Expert GraphRAG and Expert Chain-of-Thought for Legal Reasoning — arXiv NLP**
LEGO combines an expert-annotated civil code graph with greedy normative-coverage retrieval and a structured Provision-Fact-Conclusion reasoning format. With a Qwen3-8B backbone the system reached 40.53 percent exact-match accuracy on LawExamQA_Civil. It outperformed evaluated RAG and CoT baselines and matched larger models while remaining robust on multi-hop questions. Ablation studies confirmed complementary contributions from both the GraphRAG and CoT modules. Source: [arxiv.org](https://arxiv.org/abs/2609.27009)

**EduBehaviors: Assertion-based Schemas for Auditable Coding of Educational Dialogues — arXiv NLP**
The framework uses LLMs to measure repeated observable behaviors then trains a classifier on those behaviors for construct-level labels. On the TalkMoves dataset the best configuration achieved 0.673 macro-F1 and 0.688 Cohen's kappa. The approach proved competitive with direct prompting while providing mechanistic insight into label decisions. Two open tools for operationalizing the framework were released. Source: [arxiv.org](https://arxiv.org/abs/2609.27043)
---
### Agent & Tool Developments
**UniDataAgent: An Ontology-Grounded Agent for Enterprise Question-to-Report Automation — arXiv NLP**
UniDataAgent separates ontology acquisition from online execution using expert-authored business skills and constrained generation. Ontology construction for 27 enterprise tables took hours instead of a week. Report generation dropped from several working days to minutes. Strict accuracy on real business questions reached 95.0 percent versus 72.5 percent for document RAG. The system has already been deployed inside an enterprise. Source: [arxiv.org](https://arxiv.org/abs/2609.27257)

**LOCKR: A Hidden-State Trajectory-Guided Planner for Detecting and Repairing Stable-but-Wrong Lock-In in Diffusion Language Models — arXiv NLP**
LOCKR uses hidden-state trajectories to detect early lock-in on incorrect answers during iterative denoising. Across two diffusion models and three mathematical reasoning benchmarks it delivered absolute accuracy gains of 2.21 to 5.37 percentage points. Repair rates ranged from 22 percent to 41 percent. Hidden trajectories outperformed surface signals for both detection and repair selection. Source: [arxiv.org](https://arxiv.org/abs/2609.27220)

**Planned Test-Time Scaling with Coordinated Reasoning Paths — arXiv NLP**
PTTS replaces independent sampling with a planner that generates distinct solution outlines for each branch before an executor completes them. PTTS-ZS improved pass@64 by up to 6.7 points over repeated sampling. PTTS-RL raised the gain to 13.4 points across five mathematical reasoning benchmarks with Qwen3-1.7B and 4B models. The method requires no changes to the underlying executor models. Source: [arxiv.org](https://arxiv.org/abs/2609.27374)
---
### Practical & Community
**The Illinois Social Attitudes Aggregate Corpus (ISAAC): An Open Tool and Reproducible Pipeline for Analyzing Social Group Discourse at Scale — arXiv NLP**
ISAAC contains 527 million English Reddit posts spanning 2007 to 2023 and filtered for six social group distinctions. A human-audited pipeline kept irrelevant content below 10 percent. Each post carries region estimates plus validated labels for moralization, sentiment, emotion, and linguistic generalization. The corpus is accessible via website, SQL playground, Python package, and Hugging Face. Source: [arxiv.org](https://arxiv.org/abs/2609.27059)

**What Changes When Fact-Verification Scores Improve? Evidence and Answer Accounting Across Trained Verifiers and LLMs — arXiv NLP**
Replacing DCUF evidence with UnifEE evidence raised strict score by 9.61 percentage points on FEVEROUS while answer accuracy rose only 1.96 points. The evidence-only contribution accounted for 7.92 to 9.08 points when answers were held fixed. Increasing context from 256 to 2,048 tokens raised the fixed-answer evidence gain by 3.10 to 3.84 points for two 8B models. Source: [arxiv.org](https://arxiv.org/abs/2609.27064)

**Phonemizing User-Generated Text: A Benchmark, Taxonomy, and Compositional Approach — arXiv NLP**
UGTPhon provides the first G2P benchmark for user-generated text in English, Vietnamese, and Korean. Existing models showed canonical-to-non-canonical gaps reaching 66.8 PER points. A compositional approach using canonical-form lookup and staged decoding reduced non-canonical errors across ByT5 and Qwen2.5-0.5B backbones. The 0.5B model performed competitively with larger few-shot frontier LLMs. Source: [arxiv.org](https://arxiv.org/abs/2609.27205)

**AraGenre 2026: A Hierarchical Definition-Guided Arabic Genre Classification Shared Task — arXiv NLP**
The task supplied natural-language definitions for 74 previously unseen specific genres in a zero-shot setting. Thakaa ranked first with 0.7352 hierarchical macro F1. HoangPhong followed at 0.7169 and NAMAA at 0.7013. Broad-genre recognition was strong while fine-grained classification showed a substantial gap under linguistic variation. Source: [arxiv.org](https://arxiv.org/abs/2609.27387)
---
### Under the Hood: Working-Set Inference for Recurrent Language Models
Recurrent language models keep applying the same blocks across depth, yet most teams still recompute full attention at every step. Attention support and distributions actually stabilize well before hidden states finish refining. WISE therefore runs unrestricted global attention only in the early recurrent steps to discover a sparse working set, then reuses that block-structured support for the remaining steps while still allowing dynamic within-support attention. The approach preserves full-attention quality through 2K context with measurable loss only at 4K. An optimized sparse implementation delivers up to 1.76 times attention speedup at 4K and 1.36 times speedup across a full 32-step trajectory. Teams facing long recurrent traces should adopt working-set reuse once context exceeds roughly 1K tokens; below that threshold the discovery overhead outweighs the reuse gain.
---
### Things to Try This Week
- Test COMED-style selective escalation on medical or scientific queries using your current router plus a lightweight peer probe to see token savings firsthand.
- Run the UGTPhon compositional G2P approach on sample user-generated text in English or Vietnamese to measure the non-canonical error reduction.
- Explore the ISAAC corpus SQL playground or Hugging Face release if you analyze social group discourse at scale.
---
### On the Horizon
- More results from the NADI 2026 multidialectal Arabic speech tasks are expected in the coming weeks.
- Additional papers on test-time scaling and hidden-state trajectory repair are likely in the next arXiv cycles.
- Further enterprise ontology-agent deployments may surface as UniDataAgent-style systems move beyond pilot use.
