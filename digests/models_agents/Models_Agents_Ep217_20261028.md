# Models & Agents
> **Genie 4 now gives builders real-time physics, reasoning, and audio in interactive simulations they can test today.**

**What You Need to Know:** DeepMind has begun rolling Genie 4 out to trusted testers with wider access and a waitlist coming soon. The model combines real-time physics, reasoning, and audio inside simulations that nest inside other simulations. Builders should watch the official blog post and join the waitlist to experiment with world-model creation.
---
### Top Story
DeepMind has started rolling Genie 4 out to trusted testers, with wider access planned soon. The interactive world model integrates real-time physics, reasoning, and audio generation inside nested simulations. It builds on prior Genie versions by adding richer sensory and planning capabilities that let users create and interact with dynamic environments. Developers and researchers interested in simulation, robotics, or game-like world building can sign up via the linked waitlist to explore what the model enables. The release positions Genie 4 as a step toward more capable generative world models that run at interactive speeds. Source: [deepmind.google](https://deepmind.google/blog/genie-4-a-new-generation-of-world-simulation/)
---
### Model Updates
**3, 7, 14, 17, 42: Instruction Tuning Installs and Sharpens Number-Choice Heuristics in Language Models: arXiv NLP**
Instruction tuning on 15 matched base and tuned open-weight model pairs makes number distributions less uniform by installing round-number avoidance and sharpening endpoint avoidance. Base models return endpoints 1 and N at 0.30–0.60 of the interior rate while tuned models almost never do; tuned models also avoid multiples of 10 almost completely. The study evaluated 18 model lines at five ranges up to N=100 under 29 decoding configurations and found no shared modal integer above N=10 across more than 42 percent of tuned conditions. Source: [arxiv.org](https://arxiv.org/abs/2610.36178)

**Beyond IceBERT: Open-Data ModernBERT Encoders for Icelandic from 12M to 1B Parameters: arXiv NLP**
A 1B-parameter Icelandic encoder trained from scratch on 9B open tokens outperforms the prior IceBERT reference on all eleven evaluated tasks, while a warm-started version from an English Ettin encoder of the same shape ranks highest on every task. Warm-start transfer from English layers works at base size and above even when the target vocabulary is transplanted, and the 1B model remains the first monolingual Icelandic encoder of that scale. Source: [arxiv.org](https://arxiv.org/abs/2610.36230)

**MedJev: Evaluating Zero-Shot System-One Decision Making in Medicine: arXiv NLP**
MedJev, an open System-One model that runs locally on a laptop, reaches 72.5 percent on MedQA, 75.4 percent on USMLE, and 80.1 percent on NEJM while staying within 0.028–0.063 ECE on those knowledge tasks. On patient-level prediction from MIMIC IV it exceeds XGBoost on in-hospital mortality (AUROC 0.926) but trails supervised models on operational outcomes such as ED triage admission. A two-parameter recalibration method using 50–200 local labels reduces ECE to 0.007 on patient-level tasks. Source: [arxiv.org](https://arxiv.org/abs/2610.36006)

**OmniBrain-0: A Unified Agentic Model for Embodied Intelligence: arXiv NLP**
OmniBrain-0 is a lightweight unified embodied agent that coordinates manipulation and navigation through a shared high-level decision model trained with embodied pretraining, domain-specialized distillation, and multi-teacher on-policy distillation. It adds Rubric-Guided Recursive Self-Improvement that turns execution evidence into refined rubrics and verified trajectories before reconsolidation. The model is evaluated on LIBERO-Pro, RoboCasa365, RoboTwin 2.0, R2R-CE, and multiple real-world manipulation tasks while showing substantially lower inference and execution overhead than its closed-source teacher. Source: [arxiv.org](https://arxiv.org/abs/2610.36013)

**FinLLM-KG: Knowledge Graph-Enhanced LLMs for Financial Sentiment Analysis in Algorithmic Trading: arXiv NLP**
FinLLM-KG injects temporally grounded company-level facts from SEC 10-K filings into any causal LLM at inference time without weight updates, supplying either natural-language profiles or relevance-ranked triples. The framework attributes each sentiment score to individual sentences and retrieved triples for inspectability and improves portfolio performance over state-of-the-art baselines in simulation. Source: [arxiv.org](https://arxiv.org/abs/2610.36083)
---
### Agent & Tool Developments
**Benchmarking Task Takeover Across Agent Handoffs: arXiv NLP**
The Handoff State Continuity Benchmark (HSC-Bench) contains 1,039 tasks that measure how well a receiving model recovers repository evidence and continues from prior conversational, tool, and file state after an agent handoff. Structured handoff state improves evidence recovery for every tested model and continuation performance for most models, with the strongest receivers differing between the two tracks. Source: [arxiv.org](https://arxiv.org/abs/2610.36523)

**TrawMem: Reframing Agent Memory as Task-Oriented Role-Adaptive Workspaces: arXiv NLP**
TrawMem organizes interaction histories into local threads and builds task-oriented workspaces by assigning roles and jointly selecting complementary memories across Event, Affect, and Time views. On LoCoMo and MemGallery it delivers macro-F1 gains of 2.23–3.14 points over prior memory systems while using 5.1–12.8 percent fewer context tokens on two backbones. Source: [arxiv.org](https://arxiv.org/abs/2610.36918)

**DocSkill: Skill-Integrated Agentic Reasoning for Multilingual Multi-Hop Document Question Answering: arXiv NLP**
DocSkill uses a learned skill-orchestration policy trained via bounded MCTS demonstrations and DPO to select, revisit, or skip skills as evidence state evolves. On the new MMHop-DocBench (60K QA pairs across 10 languages) the Qwen3-VL-8B instantiation reaches 41.0 accuracy and 49.2 F1, exceeding the strongest baseline by 5.5 and 6.3 points. Source: [arxiv.org](https://arxiv.org/abs/2610.36759)

**CAMR: Compatibility-Aware Memory Replay for Continual Learning in Large Language Models: arXiv NLP**
CAMR jointly controls current-example supervision and historical replay via compatibility checks and a learned memory gate, choosing among learning with replay, reinforcing compatible examples, or skipping mastered duplicates. On WikiBigEdit it reaches 93.66 percent Original Match after only 3K facts and leads all evaluated methods on four TRACE tasks while preserving earlier-task performance. Source: [arxiv.org](https://arxiv.org/abs/2610.36734)
---
### Practical & Community
**Lipi-Ghor: A Large-Scale, Diarized, Multi-Domain Bengali Speech Corpus and a Scalable Pipeline for Building It: arXiv NLP**
Lipi-Ghor supplies 885 hours of speaker-diarized long-form Bengali audio from 998 YouTube videos across 17 domains together with SSTT annotations and a human-verified gold split. The construction pipeline is released as reusable code for any language with captioned YouTube presence, and four ASR models show consistent degradation on emotive, dialectal, and long-form content. Source: [arxiv.org](https://arxiv.org/abs/2610.36184)

**No Tokenizer, Still a Gap: Cross-Lingual Fairness of Homoglyph and Invisible-Character Watermarking: arXiv NLP**
Homoglyph and invisible-character watermarks achieve capacity that varies 3.3-fold across 40 language varieties in 24 scripts, with script accounting for 96 percent of the variation. Ordinary copy-paste widens the gap so that a detector needs roughly 2 code points for English or Persian but 93 for Lao. Source: [arxiv.org](https://arxiv.org/abs/2610.36432)

**ETAMem: Decoupling and Aligning Heterogeneous Memory for Long-Term Conversational Agents: arXiv NLP**
ETAMem parses conversations into atomic units, separates affective information, and maintains three hierarchical views (Event, Affect, Time) with adaptively calibrated thresholds. On LoCoMo and LongMemEval-S it improves accuracy by 12.46 percent and 7.96 percent relative to state-of-the-art baselines while keeping competitive token efficiency. Source: [arxiv.org](https://arxiv.org/abs/2610.37443)

**Nothing Left Behind: Finding Evidence from a Large Randomized Evaluation Corpus: arXiv NLP**
An embedding-based retrieval plus LLM filtering approach finds 92 percent of the evidence a systematic review would include in a 7,354-trial corpus, compared with 45 percent for label search alone. The two-stage design supports broad candidate retrieval followed by query-specific filtering at rising per-query cost with depth. Source: [arxiv.org](https://arxiv.org/abs/2610.36910)
---
### Also Today
**ReCoPII: A Relation-Grounded Framework for Building Contextual PII Masking Datasets: arXiv NLP** — ReCoPII produces relation-grounded contextual PII masking data for Korean documents that yields 88.42 percent annotator agreement on KEEP labels versus 26.27 percent for author-based augmentation and supports joint fine-tuning that limits over-masking to at most 5.04 percent within a fixed leakage budget. Source: [arxiv.org](https://arxiv.org/abs/2610.35925)

**Frankly Speaking: The Company Election Integrity Keeps in Congressional Communication: arXiv NLP** — Analysis of 10,420 congressional e-newsletters shows Democrats and Republicans surround the same election-integrity terms with entirely different neighboring language, with divergence growing on “certification” after 2020 and on “rigged” and “stolen” after that year. Source: [arxiv.org](https://arxiv.org/abs/2610.36187)

**Detect Before You Disambiguate: Perturbation-Based Input Ambiguity Detection in LLMs: arXiv NLP** — A label-preserving perturbation framework detects input ambiguity before disambiguation and outperforms output-side uncertainty baselines and LLM-paraphrase baselines across open-domain, conversational, and visual QA datasets. Source: [arxiv.org](https://arxiv.org/abs/2610.36353)

**AK_QMUL at ArGuard Shared Tasks: A Single Fine-Tuned JAIS for Arabic Harmful-Prompt Detection: arXiv NLP** — A single JAIS-6.7B backbone fine-tuned with 4-bit QLoRA ranks first on both the binary safe/unsafe track (macro-F1 0.984) and the seven-way harm-domain track (macro-F1 0.790) of the ArGuard-2026 shared task while remaining accurate across six Arabic dialects. Source: [arxiv.org](https://arxiv.org/abs/2610.36360)

**LLM Hallucination Detection via Low-rank Multilinear Decomposition: arXiv NLP** — LOTUS summarizes variable-length token representations with statistical descriptors then applies low-rank multilinear decomposition to train a lightweight hallucination classifier that improves over recent state-of-the-art baselines across multiple LLMs and QA benchmarks. Source: [arxiv.org](https://arxiv.org/abs/2610.36191)

**Expanding Partnership with USGSA for Claude Access: [@AnthropicAI](https://x.com/AnthropicAI)** — Anthropic’s new OneGov agreement extends Claude access to federal, state, local, tribal, and territorial governments at 40 percent off under a single contract. Source: [anthropic.com](https://www.anthropic.com/news/expanding-partnership-gsa)

**Anthropic Research Partnerships in Drug Development: [@AnthropicAI](https://x.com/AnthropicAI)** — Anthropic scientists have formed research partnerships with six organizations developing new medicines and begun internal drug-discovery efforts, sharing early results on how Claude supports stages of drug development. Source: [x.com](https://x.com/AnthropicAI/status/2115178675050307942)

**Build specialized multimodal models with LFM3: Hugging Face Blog** — Liquid AI releases guidance on building specialized multimodal models with LFM3. Source: [huggingface.co](https://huggingface.co/blog/LiquidAI/lfm3)

**Can we trust LLMs to judge whether a research idea is novel?: Hugging Face Blog** — AllenAI examines whether LLMs can reliably judge research novelty. Source: [huggingface.co](https://huggingface.co/blog/allenai/novelty-bench)
---
### Under the Hood: Causal Head Attribution for Evidence Effects
Causal head attribution works by running controlled symbolic probes that vary only the count and order of two symbols inside otherwise fixed prompts, then measuring how much each attention head shifts the logit difference between two answer tokens. The method first identifies candidate heads whose ablation removes most of the count effect and whose mean-output patching recovers the effect in both directions, then applies conditional bounds to decide which heads survive finite-sample noise. In Pythia-410M this process isolates sets of 1–12 heads that remove 65.5–91.6 percent of the count effect while preserving influence on count comparisons never seen during selection. When the same heads are ablated on a natural-language task that asks which state is supported by more reports, accuracy drops 8.2 points versus 0.8 points for random sets of the same size and layer. The technique therefore supplies a compact, causally validated shortlist rather than a diffuse importance map. Teams should reach for it when they need to know which specific heads carry a particular reasoning behavior before deciding whether to edit, prune, or monitor those heads in production; the main practical limit is that the symbolic probe must be carefully balanced so that the measured effect truly isolates the variable of interest.
---
### Things to Try This Week
- Join the Genie 4 waitlist at the DeepMind blog link if you build simulations, robotics planners, or interactive environments and want early access to real-time physics plus audio.
- Test MedJev on your local laptop for zero-shot medical QA or patient-level prediction tasks where you need low compute and well-calibrated outputs before supervised fine-tuning.
- Run the released Lipi-Ghor pipeline code on your own language’s captioned YouTube channels to create a diarized long-form speech corpus without manual transcription.
- Apply the HSC-Bench handoff tasks to measure how well your current agent setup preserves repository evidence and conversational state when responsibility passes between models.
- Experiment with FinLLM-KG-style knowledge-graph injection on any causal LLM you already use for financial sentiment to add company-level context at inference time with almost zero added cost.
---
### On the Horizon
- Wider Genie 4 access expected after the current trusted-tester phase.
- Additional results from Anthropic’s drug-development research partnerships scheduled for the coming months.
- Further ArGuard shared-task submissions and analyses for Arabic harmful-prompt detection.
- Continued releases of open Icelandic ModernBERT-scale encoders and evaluation harnesses.
