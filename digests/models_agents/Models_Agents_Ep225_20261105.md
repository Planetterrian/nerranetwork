# Models & Agents
> **Together Compiler lets agents re-optimize inference on the fly and delivers up to 2.6 times higher throughput.**

**What You Need to Know:** OpenAI released GPT-Image-2.6 Flare and Sunburst models that generate images in as little as 6 seconds with GIF and SVG export. Together AI introduced an agent-driven compiler that continually tunes inference forward passes. New arXiv work on small-model long-context memory and strategic clarification in dialogue adds concrete benchmarks and methods builders can test immediately.
---
### Top Story
Together AI released Together Compiler, an agent-driven loop that keeps re-optimizing the inference forward pass as traffic shifts. It beat the best InferenceX configurations by up to 2.6x TPS in under 24 hours per model. The system treats inference optimization as a continual compilation task rather than a one-time static pass. Developers running variable workloads on open models can now let lightweight agents monitor token throughput and rewrite kernels on the fly without manual retuning. The approach is model-agnostic and works on existing checkpoints. Watch for open-source releases of the compiler loop and integration guides for vLLM and TensorRT-LLM backends. Source: [marktechpost.com](https://www.marktechpost.com/2026/11/05/together-ai-together-compiler-continual-compilation-ai-inference/)
---
### Model Updates
**OpenAI Launches GPT-Image-2.6 Flare and Sunburst: Adds GIFs, SVG Export and 6-Second API Generation — MarkTechPost**
OpenAI released Images 2.6 and the GPT-Image-2.6 Flare and Sunburst API models. Flare generates images in as little as 6 seconds. Both models add GIF output, SVG export, markup edits, and a complexity parameter. The updates target developers who need faster iteration on visual assets inside agent loops or design tools. Source: [marktechpost.com](https://www.marktechpost.com/2026/11/04/openai-gpt-image-2-6-flare-sunburst/)

**Google AI Research Releases Agile Deliberation Framework for Gray-Area Image Classifiers — MarkTechPost**
Google Research released Agile Deliberation, a human-in-the-loop framework that helps users define subjective visual concepts through borderline images. In 18 live sessions it lifted Gemini-based classifier F1 by 10.5 points over zero-shot. The method surfaces ambiguous examples for human adjudication rather than forcing binary labels early. Source: [marktechpost.com](https://www.marktechpost.com/2026/11/04/google-agile-deliberation-subjective-image-classifiers/)

**SRRM: A Retrieval-Reconstruction Benchmark for Evaluating Long-Context Memory in Small Language Models — arXiv NLP**
SRRM jointly evaluates targeted retrieval and global information reconstruction on synthetic datasets with 10 to 100 factual statements. Qwen2.5-1.5B reached 86.7% retrieval accuracy and 45.7% reconstruction while the 3B variant scored 72.2% and 18.5%. Reconstruction performance fell faster than retrieval as context grew, showing retrieval-only metrics miss memory loss in small models. Source: [arxiv.org](https://arxiv.org/abs/2611.05386)

**When to Ask, When to Answer: Strategic Clarification for Ambiguous Reference Resolution in Dialogue — arXiv NLP**
The work introduces BACE, a belief-aware critic that tracks epistemic status on top of a frozen LM. BACE chooses the optimal number of clarifying questions more consistently than GRPO or ArCHer on the SIMMC 2.1 reference game. The method records how many questions each ambiguous referent needs and penalizes premature answers. Source: [arxiv.org](https://arxiv.org/abs/2611.05517)
---
### Agent & Tool Developments
**Prospective Memory for Proactive LLM Agents — arXiv NLP**
Pro-Memory separates maintaining future intentions from deciding when to realize them. It preserves pending objectives with supporting evidence, assesses new observations against activation conditions, and updates states after actions complete. Experiments on delayed-intention and open-ended assistance benchmarks showed consistent gains across multiple LLM backbones while limiting unnecessary interventions. Source: [arxiv.org](https://arxiv.org/abs/2611.05731)

**Cognitive Bias Signatures in Search-Equipped LLM Agents: A Stage-Resolved Analysis — arXiv NLP**
The study ran 10 models across 1,000 synthetic search worlds and tracked queries, retrieved documents, openings, and final answers. Final answers proved more sensitive to initial evidence order during active search than when all evidence arrived at once. Dead-end histories reduced strategy switching beyond what context length alone predicts. Source: [arxiv.org](https://arxiv.org/abs/2611.05720)
---
### Practical & Community
**Rewrite, Then Veto: Rewriter-Agnostic Edit Gating for LLM-Based Post-OCR Correction — arXiv NLP**
EditVeto places a 0.6B-parameter gate after a full-context LLM rewrite and keeps or reverts each aligned block. The gate improved all five rewriters tested on HIPE-OCRepair-2026, lowering weighted cMER by 0.0026-0.0044. It works on rewriters unseen during training and raises preference scores by 0.15-0.25. Source: [arxiv.org](https://arxiv.org/abs/2611.05539)

**RAGCompass: Generalizable Retriever Routing via Reranking — arXiv NLP**
RAGCompass fine-tunes a reranker on the answer each evidence set produces and adds a small comparison head. It improved answer F1 by 28% relative to the best fixed retriever and kept most gains under unseen corpora, retrievers, or readers. The router reads passage sets directly, avoiding query-only feature limitations. Source: [arxiv.org](https://arxiv.org/abs/2611.05596)

**Editing Large Language Models with Geometry-Aware Regularization — arXiv NLP**
GEdit uses a low-rank plus diagonal factor model to protect a core knowledge subspace while relaxing constraints on hard edits. On GPT-J and LLaMA-3-8B it outperformed baselines in both editing success and knowledge preservation across up to 10,000 sequential updates. The method requires no retraining of the base model. Source: [arxiv.org](https://arxiv.org/abs/2611.06185)
---
### Also Today
**CCDWIKI: Decoupling Case Formulation from Response Generation in Longitudinal CBT Dialogue — arXiv NLP:** CCDWiki encodes clinical hypotheses as mutable entries bound to corroborating and contradicting evidence so longitudinal therapy stays evidence-grounded without backbone retraining. Source: [arxiv.org](https://arxiv.org/abs/2611.05383)

**Matching the Training-Time Weight Rule in Inference-Time Expert Deactivation — arXiv NLP:** Remaining-expert renormalization or unnormalized re-routing produces the lowest perplexity only when the inference rule matches the training rule; mismatches inflate perplexity 14- to 28,740-fold. Source: [arxiv.org](https://arxiv.org/abs/2611.05804)

**Learning When Human Decisions Matter: Executor-Relative Consultation Value for LLM Agents — arXiv NLP:** Consultation Value Distillation estimates human consultation value offline via Monte Carlo rollouts and distills it into lightweight predictors that improve budgeted allocation across batch and sequential settings. Source: [arxiv.org](https://arxiv.org/abs/2611.05814)

**TandemBench: Benchmarking Decision Models for Multi-Agent Collaboration — arXiv NLP:** TandemBench contains 1,200 multi-agent cooking questions where the best native decision model reaches 62.50% accuracy while optimality verification stays near chance. Source: [arxiv.org](https://arxiv.org/abs/2611.05827)

**CARTBench: Rubric-Based Evaluation of Shopping Advice for Complex and Ambiguous Requests with Timelines — arXiv NLP:** CARTBench supplies 1,328 expert-annotated criteria across 17 retail domains; three of ten evaluated models exceed 90% on core criteria while none exceeds 45% on excellence criteria. Source: [arxiv.org](https://arxiv.org/abs/2611.05862)

**When Does Better Confidence Improve a Knowledge-Graph Audit? — arXiv NLP:** An error-rate times fan-out queue leaves 3.98-4.74 percentage points more errors than a joint model with identical actions on held-out Re-DocRED graphs. Source: [arxiv.org](https://arxiv.org/abs/2611.05877)

**Information-Matched Auditing of Conversational Emotion-Shift Forecasting — arXiv NLP:** Under deployable conditions a learned model beats the predicted-label baseline on all four primary corpora, with the largest gain on DailyDialog surviving Holm correction. Source: [arxiv.org](https://arxiv.org/abs/2611.05895)

**Selective, Risk-Controlled Emotion Forecasting in Conversation — arXiv NLP:** A state-space filter exceeds the persistence baseline only when the historical state is observed; estimated anchors collapse performance below a direct forecaster. Source: [arxiv.org](https://arxiv.org/abs/2611.05896)

**Familiar letters, not related languages, let unseen languages into a shared space of meaning — arXiv NLP:** GlyphMind adapted on untranslated Lao retrieved English translations seven times as often as the strongest baseline when the script matched pretraining scripts. Source: [arxiv.org](https://arxiv.org/abs/2611.06006)

**When Every Choice Is Correct: A Causal Study of Numerical Preference in Language Models — arXiv NLP:** A pre-answer edit in a Qwen3-4B case changes the emitted number from 17 to 15 while both runs first emit 1; later MLP clamping reduces the final log-odds gap to 0.0025 nat. Source: [arxiv.org](https://arxiv.org/abs/2611.06025)

**Confucius4-R2T2: A Stable-Prefix Streaming ASR Model for Real Real-Time Transcription — arXiv NLP:** R2T2 is obtained by post-training Qwen3-ASR-1.7B on 1,500 hours of audio while freezing the encoder; it delivers stable text with low emission lag and generalizes beyond the adaptation languages. Source: [arxiv.org](https://arxiv.org/abs/2611.06043)

**Adapting Qwen3 to Tajik from 0.6B to 8B: Lower Text Loss Did Not Mean Better Understanding — arXiv NLP:** Continued pretraining on 375 million Tajik tokens followed by supervised fine-tuning raised Belebele accuracy 11.4 points above Qwen3-8B while English MMLU changed by only -1.2 points. Source: [arxiv.org](https://arxiv.org/abs/2611.06062)

**ProcessPrefBench: Evaluating Cross-Task Transfer of Individual Process Preferences from Naturalistic Human-AI Interaction — arXiv NLP:** Full-history and distilled-preference prompting raise preference realization by 0.204-0.244 points on a 0-2 scale yet increase fabricated-evidence failures from 5.8% to 10.1-10.4%. Source: [arxiv.org](https://arxiv.org/abs/2611.06065)

**Overview of the NTCIR-19 SciClaimEval Task — arXiv NLP:** The best systems reached 98.1% pair accuracy on claim-evidence support but dropped 24.3 points when forced to judge each pair without contrastive examples. Source: [arxiv.org](https://arxiv.org/abs/2611.06090)

**The Harness Is the Model: Agent Scaffolding Changes a Fixed LLM's Compliance with Banking Conduct Rules — arXiv NLP:** The model-by-harness interaction moved correct-case rate by up to 11.5 percentage points within one model while a same-model compliance reviewer cut violations from 9.6% to 6.4%. Source: [arxiv.org](https://arxiv.org/abs/2611.06116)

**Accelerating Long-Context Decoding in Large-Scale Hybrid LLMs Without Retraining — arXiv NLP:** Combined sparse attention on six hybrid models from 4B to 397B parameters yields up to 2.23x faster decoding at 256k context while preserving accuracy on 21 long-context datasets. Source: [arxiv.org](https://arxiv.org/abs/2611.06133)

**AssameseLM-E2B: An Open-Weight Assamese Language Model for Efficient Consumer-Grade Deployment — arXiv NLP:** The 2B model with expanded byte-level BPE vocabulary reaches 0.7488 BPB on FLORES-200 and 96.7% RAG score after parameter-efficient continual pretraining and supervised fine-tuning. Source: [arxiv.org](https://arxiv.org/abs/2611.06170)

**Loop Before You Leap: What Recurrent Depth Can and Cannot Buy in Data-Limited Pretraining — arXiv NLP:** A 12-layer stack repeated four times exceeds a standard 48-layer Transformer by 5.4 BLiMP points at matched inference compute, yet multimodal training lowers accuracy by 3.8 points in both architectures. Source: [arxiv.org](https://arxiv.org/abs/2611.06206)

**Mass Producing Training Data with Surprising Side Effects — arXiv NLP:** An automated pipeline produced 6,575 datasets across eight behaviors that generalize across model families; frontier models outperform humans at predicting the side effects. Source: [arxiv.org](https://arxiv.org/abs/2611.06324)

**Presentation Sensitivity in Typed Decision Models for Subjective Text Evaluation — arXiv NLP:** Jev's second-position probability advantage reaches 6.11 points on summaries; reversing reader endorsements changes Perplexity's selected humor text on 40.40% of pairs. Source: [arxiv.org](https://arxiv.org/abs/2611.06384)

**Where Should a KV-Cache Repair Budget Go? — arXiv NLP:** Reuse loses 19-100% of context-dependent questions; restoring a few non-target chunks recovers little while recomputing the target chunk against the reused cache beats full-prefill insertion in all seven tested settings. Source: [arxiv.org](https://arxiv.org/abs/2611.06397)

**Interpretable Text Embeddings Based on Hierarchical Questions — arXiv NLP:** Hierarchical questions improve interpretability while maintaining task performance; when question count is limited, shallower levels outperform deeper ones on general-purpose tasks. Source: [arxiv.org](https://arxiv.org/abs/2611.06402)

**Ruby-OPD: Enhancing Pronunciation Controllability and Accuracy for Flow-Matching Text-to-Speech via On-Policy Distillation — arXiv NLP:** On the Joyo-Kanji-Yomi benchmark the model reaches 97.13% accuracy and 0.70% sentence PER under raw orthographic text while retaining strong controllability. Source: [arxiv.org](https://arxiv.org/abs/2611.06403)

**Twists and Turns: A Graph-Based Benchmark and Framework for Long-Term Memory in Exploration Tasks — arXiv NLP:** LExMem yields 224 dialogues and 2,018 question-answer instances from graph structures; LExGraph incrementally organizes dialogues into interconnected nodes and outperforms retrieval- and memory-based baselines. Source: [arxiv.org](https://arxiv.org/abs/2611.06414)

**EvoGuard: Mitigating Degradation in Online Skill Evolution — arXiv NLP:** EvoGuard improves success by 11.0% on ALFWorld, 5.9% on ScienceWorld, and 2.7% on LiveCodeBench by training a pairwise selector on private-test utility labels. Source: [arxiv.org](https://arxiv.org/abs/2611.06444)

**ArcRAG: Agentic Compositional Retrieval over Knowledge Graphs — arXiv NLP:** ArcRAG induces a query-local graph interface at inference time and executes Cypher traversals; it stays effective when the underlying graph construction changes from schema-guided to open information extraction. Source: [arxiv.org](https://arxiv.org/abs/2611.06481)

**LibriSpeech-Real-QA: A Benchmark for Streaming Question Answering — arXiv NLP:** The benchmark evaluates whether speech LLMs can identify target words in streaming audio; several commercial models still wait for the full turn before responding. Source: [arxiv.org](https://arxiv.org/abs/2611.06496)

**CRESiST: Self-Enhancing Explorative Policy Learning for Simultaneous Speech Translation — arXiv NLP:** An actor-critic pipeline with intrinsic semantic and latency rewards establishes new quality-latency Pareto frontiers on both sentence- and document-level simultaneous translation benchmarks. Source: [arxiv.org](https://arxiv.org/abs/2611.06501)

**NaijaFacts: A Framework for Disentangling Language from Knowledge in Facts about Nigeria — arXiv NLP:** English-query accuracy on Nigerian statistics sits at 20% versus 49-50% for UK/US facts; scale does not close the gap, with the strongest models reaching at most 31%. Source: [arxiv.org](https://arxiv.org/abs/2611.06504)

**When Do Summaries Become Instructions? Unsupported Policy in LLM Agents' Self-Written Handoff Summaries — arXiv NLP:** Unsupported restrictions appear in 1.2-2.4% of readable summaries; neutralizing false approvals cut unauthorized actions from 24 to 7 of 120 held-out runs. Source: [arxiv.org](https://arxiv.org/abs/2611.06545)

**Replicability, Reproducibility, and Robustness in Political and Social Science Research with Large Language Models — arXiv NLP:** A stacked ensemble of open-weight models improves precision in the correction step while retaining estimate validity when measurement choice reverses regression sign. Source: [arxiv.org](https://arxiv.org/abs/2611.06639)

**ALTO: African and Levantine Tech-Facilitated Gender-Based Violence Corpus — arXiv NLP:** The 3,022-instance corpus improves TFGBV recall after fine-tuning; models still miss covert harms, with markedly higher error rates in Swahili. Source: [arxiv.org](https://arxiv.org/abs/2611.06706)

**Reasoning over Non-Parametric Memory in Multilingual LLMs — arXiv NLP:** Accuracy drops sharply from Apply to Analyze in every open-weight series; Evaluate items remain a bottleneck even for models near ceiling on other levels. Source: [arxiv.org](https://arxiv.org/abs/2611.06715)

**Ranking Agreement Does Not Reveal Paragraph-Edit Agreement in Two Released Paper Acceptance Predictors — arXiv NLP:** The classifier ranks original papers closely with one predictor yet shows no detectable agreement on which rewrites raise scores; edit agreement stays near zero even at full 32-bit precision. Source: [arxiv.org](https://arxiv.org/abs/2611.06789)

**Measuring Risk, Not Harm: Detecting Psychological Harm Risk Factors in LLM Conversations — arXiv NLP:** The best cascade achieves 0.79 macro F1 on held-out labels and reduces LLM-judge calls by 97.1% on WildChat while clustering risk-factor detections within conversations. Source: [arxiv.org](https://arxiv.org/abs/2611.06806)

**LLMs Don't Know What They Know: Benchmarking Temporal Self-Knowledge for Financial Backtesting — arXiv NLP:** GPT-5 answers 76% of controlled facts correctly but claims to know only 38% and answers 61% of the facts it says it does not know. Source: [arxiv.org](https://arxiv.org/abs/2611.06808)

**SAUCE: Summary Analysis Using Conversation Entailment — arXiv NLP:** SAUCE maps summary scores to discrete verifiable facts, capturing information loss from transcription and translation error while aligning strongly with human judgment. Source: [arxiv.org](https://arxiv.org/abs/2611.06812)

**AI agent autonomy remains an elusive work in progress — CIO**
Current agent systems still require substantial human oversight for reliable long-horizon execution. Source: [cio.com](https://www.cio.com/article/4242283/ai-agent-autonomy-remains-an-elusive-work-in-progress.html)

**Full preprint on vault particle structure mapping with Claude — [@AnthropicAI](https://x.com/AnthropicAI)**
Anthropic's biology team used Claude to map the first 3D structure of a bacterial vault particle in days instead of weeks. Source: [www-cdn.anthropic.com](https://www-cdn.anthropic.com/76e55fbe85697afbaae16b839498dc00797dec30.pdf)

**Anthropic uses Claude to map first 3D structure of bacterial vault particle — [@AnthropicAI](https://x.com/AnthropicAI) (X)**
Claude accelerated structure determination while still making simple mistakes that required machine-learning researcher intervention. Source: [x.com](https://x.com/AnthropicAI/status/2118073665296228863)
---
### Under the Hood: Recurrent Depth in Transformers
Recurrent depth re-uses the same transformer layers in a loop instead of stacking new ones, giving a small model more sequential compute steps without extra parameters. The core mechanism is simple: each layer receives both the current token representation and a recurrent state carried from its own previous pass, exactly as described in the Block-Recurrent Transformer paper. This produces linear complexity in sequence length while still allowing the model to refine its internal state over multiple iterations at inference time. The tradeoff appears clearly in the Griffin work: Hawk and Griffin match Llama-2 performance after training on six times fewer tokens, yet the recurrent state must be sized and initialized carefully or the model loses the ability to extrapolate beyond training lengths. Relaxed Recursive Transformers add depth-wise LoRA modules to loosen the strict parameter-sharing constraint, recovering most of the original model's accuracy at roughly one-quarter the parameter count. RecurrentGemma demonstrates the practical payoff: the 2B and 9B variants reach comparable downstream scores to standard Gemma checkpoints despite fewer training tokens, and they run with fixed memory cost on long sequences. The practical rule is to prefer recurrent depth when parameter count or training data is the binding constraint and to fall back to deeper feed-forward stacks when maximum single-pass quality on short contexts matters most. Source: [arxiv.org](https://arxiv.org/abs/2203.07852)
---
### Things to Try This Week
- Run Together Compiler on a variable-load endpoint and measure TPS before and after the agent loop engages.
- Test GPT-Image-2.6 Flare for 6-second GIF generation inside a design-agent workflow that previously waited on slower image APIs.
- Evaluate Qwen2.5-1.5B on the SRRM benchmark to see whether reconstruction quality collapses faster than retrieval as context grows.
- Add BACE-style epistemic tracking to a reference-resolution agent and compare clarification-question counts against GRPO baselines.
- Experiment with EditVeto on noisy historical OCR documents to quantify the cMER reduction without retraining the base rewriter.
---
### On the Horizon
- Open-weight teams are expected to release larger recursive or hybrid-recurrent checkpoints in the coming weeks.
- More labs will publish agent-harness compliance audits following the banking-rule study pattern.
- Additional multilingual factuality benchmarks modeled on NaijaFacts are likely for other low-resource regions.
- Streaming ASR and SimulST systems will see further stable-prefix and policy-learning releases.
