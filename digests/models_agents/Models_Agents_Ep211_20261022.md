**# Models & Agents**
> **Frozen Gemma 4 encoders match commercial Arabic ASR on character error while running 3.4× faster on CPU.**

**What You Need to Know:** Researchers kept the 305M-parameter Gemma 4 audio encoder frozen and added lightweight readers, reaching parity with Cohere Transcribe Arabic on several Saudi and Emirati conditions. New evaluation frameworks (SkillEval, SANE, B-CARE) give finer-grained model profiling and judge reliability testing than scalar benchmarks. Open releases include MADARTB parallel dialect treebanks, Lift-Bench scoped instruction constraints, and CSD cross-tokenizer distillation code.
---
### Top Story
Researchers tested the 305M-parameter audio encoder shared by Gemma 4 and EmbeddingGemma 2 on Saudi and Gulf Arabic speech without updating any encoder weights. A frozen CTC reader (22.6M parameters) trained over mixed encoder layers trailed Cohere Transcribe Arabic (2.07B) in word error rate but matched it on character error rate for five of six human-labelled conditions while running 3.4× faster on CPU with greedy decoding. Adding 3.1M low-rank adapters plus a 41.5M-parameter hybrid CTC/attention reader with sub-word language model joint decoding produced statistically indistinguishable WER on a public Saudi customer-service call (19.20 % vs 19.27 %) and clean Emirati speech, with significantly lower CER across all six conditions and better results than a 0.6B SADA-fine-tuned recogniser. The system ranked fourth of fifteen on a blind human-corrected call-centre sample, behind three commercial APIs and ahead of other self-hostable systems by point estimate, with an optimised joint decoder reaching 139× real time on one GPU. Code and public-set results are released. Source: [arxiv.org](https://arxiv.org/abs/2610.28673)
---
### Model Updates
**SkillEval: Learning Interpretable Ability Profiles of LLMs via Cognitive Diagnosis Models: arXiv NLP**
SkillEval applies LLM meta-cognition to discover interpretable skills from questions then fits cognitive diagnosis models to estimate per-skill abilities across 3,811 LLMs and 9,523 items from MATH, BBH, GPQA, MuSR and IFEval. The resulting profiles are more calibrated than average scores, predict unseen-item performance better, and enable LLM routing that cuts inference cost over 60 % while improving accuracy plus efficient Computerized Adaptive Testing for new models. Source: [arxiv.org](https://arxiv.org/abs/2610.28767)

**Where Do Legal Factors Live in LLMs?: arXiv NLP**
All 26 CATO factors are linearly decodable in Qwen3-1.7B, Qwen3-8B and Gemma-2 2B; single-feature sparse readouts from sparse autoencoders cover the full catalog with best-layer test AUCs 0.86–1.00, and five selected features approach full-vector performance. The study reports 78 model-specific layer-feature coordinates. Source: [arxiv.org](https://arxiv.org/abs/2610.28799)

**LIFT: Scoped Constraints for Evaluating and Training Instruction Following: arXiv NLP**
Lift-Bench asks models to draft documents from topic and structured outline with constraints scoped to specific sections, supplying both verifiable and judged constraints plus a matched Lift-Train set. Frontier models struggle on harder subsets; training on Lift-Train reduces reward hacking compared with common IFTrain. Both benchmark and training data plus the generation pipeline are public. Source: [arxiv.org](https://arxiv.org/abs/2610.28819)

**A Parallel Multi-Dialect Arabic Dependency Treebank: arXiv NLP**
MADARTB annotates 5,000 sentences across Beirut, Cairo, Doha, Rabat and Tunis dialects plus MSA using the CATiB scheme. Global construction profiles are similar but local structures diverge; a supervised parser reaches 87.5 % LAS while the best LLM setup reaches 85.7 % LAS across all six varieties. Annotations and models are released. Source: [arxiv.org](https://arxiv.org/abs/2610.28823)

**CSD: Common-Support Distillation for Cross-Tokenizer Knowledge Transfer: arXiv NLP**
CSD builds an explicit or virtual common support at each aligned chunk and matches induced distributions with one objective, handling one-to-one and other alignments via the autoregressive chain rule plus residual events. Across Llama-3.2-1B and Gemma3-1B-PT students with Qwen and Phi teachers it outperforms prior cross-tokenizer methods by up to 1.8 points and beats continued pretraining and same-tokenizer distillation; on Llama-3.1-8B it improves average accuracy up to 4.2 points for base and 1.6 points for instruction-tuned students. Source: [arxiv.org](https://arxiv.org/abs/2610.28895)

**norregel: a preregistered benchmark of dated numeric values in Norwegian law: arXiv NLP**
The benchmark extracts 916 dated numeric values (NOK amounts, percentages, G-multiples, age limits) from Lovdata with full revision history so answers can be classed correct, outdated, wrong or uninterpretable. In the second preregistered run eight models were evaluated; support for the hypothesis that outdated answers rise after a model’s cutoff was not robust under the strictest sensitivity analysis. Source: [arxiv.org](https://arxiv.org/abs/2610.29207)
---
### Agent & Tool Developments
**Is Anyone Enforcing the Cartel? What Reinforcement Learning Teaches LLM Agents in Markets: arXiv NLP**
An audit forces cartel members to cheat in counterfactual markets and measures whether RL-trained pricing and trading agents punish the deviation. Small RL-trained LLMs learn fixed rules in self-play, deterrence against punishing rivals, and matching against cheaters, but rarely discover costly price wars; only matching agents enforce thin collusion and only against large cuts, while Q-learners enforce only in pricing. Source: [arxiv.org](https://arxiv.org/abs/2610.28787)

**Building AI Research Teams for Autonomous Discovery of Linear Attention Architectures: arXiv NLP**
Persistent AI researchers with distinct disciplinary backgrounds, private histories and adaptive research allocation outperform GDN2 at 1.3B scale on language modeling, commonsense reasoning and retrieval tasks. Removing disciplinary backgrounds, private histories or adaptive allocation each produces markedly weaker discoveries. Source: [arxiv.org](https://arxiv.org/abs/2610.28887)

**Let Agents Design How They Search: Automatic Interface Optimization for Agentic Search: arXiv NLP**
SearchWeaver uses execution trajectories and task rewards to jointly revise corpus artifacts, executable tools and usage instructions. With GPT-5.4-nano the optimised interfaces raise answer accuracy from 71.6 % to 78.4 % on BrowseComp-Plus and average nDCG@10 from 45.7 to 55.0 across four BRIGHT subsets. Source: [arxiv.org](https://arxiv.org/abs/2610.29250)

**MOSAIC: An Omni-Modal Benchmark for Long-Term Memory and Cross-Modal Reasoning in Conversational Agents: arXiv NLP**
MOSAIC supplies 923 questions over 11–24 session persona-grounded histories spanning text, image, video and audio with targeted spatial, temporal and prosodic signals. Matched decomposition shows representation loss is modality-dependent, residual reading dominates even with gold evidence, and abstention remains weak. Source: [arxiv.org](https://arxiv.org/abs/2610.29249)
---
### Practical & Community
**KIRA: A Full-Stack Reading Screening System with Dual-Pathway Analysis for Children: arXiv NLP**
KIRA adapts pretrained word and phoneme recognisers to children’s speech, cutting word error rate from 13.88 % to 8.84 % and phoneme error rate from 41.66 % to 23.00 %. It implements Word Reading and Oral Reading Fluency tasks with a teacher-facing web interface that presents fluency scores and phoneme-level feedback. Source: [arxiv.org](https://arxiv.org/abs/2610.28840)

**SANE: Automated Scorer-Specific Metamorphic Testing for LLM Judges: arXiv NLP**
SANE encodes behavioral requirements as reusable agent instructions, automatically derives scorer-specific perturbation recipes and expected score relations, then validates them with a scorer-independent framework. Across five domains it produces 3.7× as many validated test families as the Judge Reliability Harness at comparable validity and detects deficiencies in professionalism and toxicity where JRH finds none. Source: [arxiv.org](https://arxiv.org/abs/2610.28886)

**LTEM: LLM-Friendly Table-Enhanced Markdown for Table Understanding and Generation: arXiv NLP**
LTEM extends Markdown with explicit span and hierarchical-header encoding while remaining minimal. On five state-of-the-art LLMs it matches HTML accuracy with a better accuracy-token trade-off and produces far fewer invalid responses than LaTeX for table generation. Taxonomy, benchmark and specification are released. Source: [arxiv.org](https://arxiv.org/abs/2610.29188)

**TrainBridge: Agentic NPU Training Optimization Guided by GPU Compilation Evidence: arXiv NLP**
TrainBridge extracts optimization intents from GPU execution traces to guide NPU program rewrites and iterates with profiling. It delivers 1.7× average speedup across four workloads (LLM pretraining, image classification, vision-language) and nearly 2.0× across 27 Modded-NanoGPT speedrun records. Source: [arxiv.org](https://arxiv.org/abs/2610.29171)
---
### Also Today
**Scaling Therapy Supervision: Assessing Psychotherapy Fidelity Using Large Language Models: arXiv NLP** Evidence-first reasoning improves fidelity estimation and the pipeline distinguishes CBT from non-CBT sessions on an independent RCT while mental-health experts rate the generated feedback actionable. Source: [arxiv.org](https://arxiv.org/abs/2610.28772)

**How to Use Parallel Data for Multilingual Pretraining: arXiv NLP** Parallel pretraining alone does not consistently beat standard pretraining, but a two-stage approach (PPT then SPT) improves both general language understanding and cross-lingual task performance at matched budgets in high- and low-resource settings. Source: [arxiv.org](https://arxiv.org/abs/2610.28838)

**Guilt by Association: Semantic Leakage Drives Associative Gender Bias: arXiv NLP** Semantic leakage persists even without direct attribution to the queried entity and shifts model outputs toward gender stereotypes at similar rates whether the subject engages with the concept or it merely appears in the scene. Source: [arxiv.org](https://arxiv.org/abs/2610.28944)

**Understanding Target Probability Reuse in Speculative Decoding: arXiv NLP** Retaining the target distribution computed at the next round’s complete context enables reranking and first-token sampling rules that improve expected acceptance over draft ranking, especially at small tree budgets, and can decode faster when the extra target pass overlaps drafting. Source: [arxiv.org](https://arxiv.org/abs/2610.29210)

**Beyond Binary Labels: Diagnostic Evaluation of LLM Safety with Prompt-Level Rubrics: arXiv NLP** DiagSafe’s prompt-level rubrics achieve 95.34 % agreement with human annotations and Cohen’s κ = 0.864 inter-judge consistency while revealing model-specific unsafe-rate patterns and greater susceptibility in Chinese and multi-turn contexts. Source: [arxiv.org](https://arxiv.org/abs/2610.29225)

**A Large-Scale Evaluation of Role-Enhanced Zero-Shot Chain-of-Thought Prompting: arXiv NLP** Role-Enhanced Zero-Shot CoT with static or dynamic expert roles improves performance up to 44 points over zero-shot baselines across 20 LLMs and seven benchmarks; unconventional roles degrade results and smaller models reach notable arithmetic proficiency. Source: [arxiv.org](https://arxiv.org/abs/2610.29073)

**GRAFT: Restoring the Missing Sampling Interface in Continuous Diffusion Language Models: arXiv NLP** GRAFT commits rare words while the model is undecided then regenerates, restoring rare-word share from 0.42–0.77× to 0.82–1.10× human rate (34–109 % relative gain) across three ELF scales and LangFlow. Source: [arxiv.org](https://arxiv.org/abs/2610.29136)

**Why is AI-generated language so hard to understand?: arXiv NLP** Frontier models use more inanimate subjects with animate verbs, longer dependencies, stacked nouns, reduced object relatives and low-frequency n-grams than human writing or round-trip translation paraphrases; fine-tuning under a length penalty reproduces the divergence. Source: [arxiv.org](https://arxiv.org/abs/2610.29162)

**Signals and Queries: Token-Efficient Agentic Context Discovery: arXiv NLP** S&Q trains per-policy logistic classifiers on embeddings of activating examples and hard negatives, removing at least 30 % of candidate policies before LLM evaluation while preserving high recall on 9,144 labels covering 254 conversation prefixes and 36 airline policies. Source: [arxiv.org](https://arxiv.org/abs/2610.29326)

**Seeing the Forest for the Trees: Emergent Agreement from Individual Conversations: arXiv NLP** Internal agreement representations vary across turns and do not track external agreement at the single-conversation level, yet aggregate across conversations they couple with external Markov agreement via a power-law mapping. Source: [arxiv.org](https://arxiv.org/abs/2610.29328)

**Right On Q: Recovering Reasoning under Quantization via Self-Generated Trajectories: arXiv NLP** OnQ combines on-policy distillation with candidate-wise Dynamic KL and raises nine-benchmark average for 2-bit and 3-bit Qwen3 models, with largest gains on long-horizon reasoning and fewer truncations. Source: [arxiv.org](https://arxiv.org/abs/2610.29378)

**Beyond Small Talk: Modeling Disclosure Trajectories in Human-AI Conversation: arXiv NLP** TraDE shows responses to matched-depth disclosures differ by preceding trajectory, with models diverging most from human supporters when users step back rather than open up. Source: [arxiv.org](https://arxiv.org/abs/2610.29413)

**DynaWeave: Learning to Adapt through Dynamic Scenario Synthesis: arXiv NLP** DynaWeave turns static tasks into verifiable dynamic scenarios with exogenous events represented as DAGs; supervised fine-tuning on 2,095 trajectories raises task completion on CostBench by 67.34 points and exceeds Gemini-3.1-Pro-Preview on ToolMaze. Source: [arxiv.org](https://arxiv.org/abs/2610.29443)

**Omnilingual-MsASR: Benchmarking Multimodal, Multilingual, Long-Form Multi-Speaker ASR of Omni Large Language Models: arXiv NLP** The benchmark covers six languages, recordings up to 30 minutes and up to 20 speakers; leading omni-modal LLMs post tcpWERs frequently above 100 %, highlighting fine-grained temporal localization and speaker disambiguation as open challenges. Source: [arxiv.org](https://arxiv.org/abs/2610.29455)

**TenetBench: A Clause-Anchored Russian Corpus for Evaluating Language Models against Professional Codes of Ethics: arXiv NLP** Eleven of fourteen model/reasoning-mode combinations produce conflicting content on most requests that breach professional codes, mostly without warning; enabling reasoning halves refusals for two models. Source: [arxiv.org](https://arxiv.org/abs/2610.29477)

**Keeping Time vs. Understanding Time: Neither Alone Explains Temporal Reasoning in LLMs: arXiv NLP** Finetuning on arithmetic- or semantic-labelled subsets yields mostly dataset-specific gains with near-zero transfer inside the same mode; knowledge, not quantitative or logical reasoning, drives benchmark performance. Source: [arxiv.org](https://arxiv.org/abs/2610.29507)

**Mitigating Query Shortcuts in Chain-of-Thought with Context-Aware Decoding: arXiv NLP** Rationale Contrastive Decoding improves answer accuracy over standard CoT on five reasoning benchmarks and increases behavioral dependence on rationale content. Source: [arxiv.org](https://arxiv.org/abs/2610.29518)

**Anthropic Publishes Annual Public Benefit Report: [@AnthropicAI](https://x.com/AnthropicAI)** The report details five pillars and actions taken to advance them. Source: [anthropic.com](https://www.anthropic.com/public-benefit-charter)

**Codex skill to check PHP vulnerability impact: [@OpenAI](https://x.com/OpenAI)** A packaged Codex skill guides users through checking whether sites are affected by recently disclosed PHP flaws. Source: [github.com](https://github.com/openai/php2shell-checker)

**OpenAI models discover critical PHP security flaws: [@OpenAI](https://x.com/OpenAI) (X)** Frontier models found internet-scale PHP vulnerabilities ahead of attackers, enabling a defender’s window for coordinated fixes. Source: [x.com](https://x.com/OpenAI/status/2112907856018309586)

**GPT-Rosalind identifies cholesterol transport clue for Perry syndrome: [@OpenAI](https://x.com/OpenAI) (X)** A multi-agent GPT-Rosalind run linked DCTN1 disruption to cholesterol-transport hypotheses in 32 minutes. Source: [x.com](https://x.com/OpenAI/status/2112899854569762936)

**GDC survey mentions Claude Code but skips Codex: Simon Willison (AI builder) (X)** The August–September survey includes Claude Code but omits Codex. Source: [x.com](https://x.com/simonw/status/2113027536334766440)

**Coding agent revolution started in 2026: Simon Willison (AI builder) (X)** Most developers surveyed in late 2025 had not yet adopted the new coding agents. Source: [x.com](https://x.com/simonw/status/2113021891124572623)

**Don't lean on old 2025 survey lacking Claude Code: Simon Willison (AI builder) (X)** The January 2026 survey was fielded in November 2025 without Claude Code as an option. Source: [x.com](https://x.com/simonw/status/2113021660421091561)

**How Specializing the Vocabulary of SLMs Can Cut Inference Cost by 77% in Real Applications: Hugging Face Blog** Vocabulary specialization yields substantial inference-cost reductions in deployed small language models. Source: [huggingface.co](https://huggingface.co/blog/Dharma-AI/vocabx-vocabulary-specialization)

**ChatGPT Ads expands to 26 new countries as over 100,000 advertisers have used the platform: OpenAI Blog** Local and global advertisers can now reach users inside ChatGPT in 26 additional countries. Source: [openai.com](https://openai.com/index/chatgpt-ads-expands-26-new-countries)

**Dr. Christopher Stubbs Joins Anthropic's Long-Term Benefit Trust: [@AnthropicAI](https://x.com/AnthropicAI)** Experimental physicist and former Harvard Dean of Science Christopher Stubbs joins the Long-Term Benefit Trust. Source: [anthropic.com](https://www.anthropic.com/news/christopher-stubbs-joins-long-term-benefit-trust)
---
### Under the Hood: Common-Mode Offsets in Preference Optimization
Preference optimization losses operate on relative differences between chosen and rejected pairs, so any shared directional shift that moves both representations equally produces almost no gradient signal. That shared shift, the common-mode offset, accumulates across token positions and prompts because every update slightly nudges the entire hidden-state distribution in the same direction. Once the offset grows large enough it projects through the unembedding matrix and creates a single high-probability token that dominates sampling, producing the well-known vocabulary collapse. The offset is already visible in textbook DPO and SimPO runs that never reach collapse, which explains why ranking metrics can keep improving while generation quality silently degrades. Masking the common component out of the loss during training prevents the well from forming, at the cost of a small drop in the ranking objective. The practical takeaway is to monitor the norm of the mean-centered hidden-state shift on a small validation set after each epoch; when it exceeds roughly 0.3–0.4 of the typical per-token activation norm, generation quality is likely to degrade even if pairwise ranking scores remain high. Teams that already track output entropy or repetition rate can add this cheap hidden-state statistic without extra inference passes.
---
### Things to Try This Week
- Run the released Gemma 4 frozen-encoder code on your own Gulf Arabic audio to measure CPU latency versus a commercial API.
- Apply SkillEval’s skill profiles to route queries between a fast 8B model and a larger reasoning model and track cost versus accuracy on your own benchmark.
- Test SANE’s scorer-specific metamorphic tests on any LLM judge you maintain to surface hidden failure modes in professionalism or toxicity.
- Experiment with CSD distillation when moving a Qwen teacher to a Llama or Gemma student tokenizer to retain cross-family performance.
- Try LTEM-formatted tables in your RAG pipeline if you currently lose merged-cell or hierarchical-header structure with plain Markdown.
---
### On the Horizon
- Continued releases of scoped instruction-following benchmarks that separate main-task performance from constraint adherence.
- Wider adoption of sparse-readout techniques for auditing internal representations of domain-specific concepts such as legal factors.
- More agentic search interfaces that jointly optimize corpus artifacts, tools and instructions rather than fixing the interface by hand.
- Growing use of preregistered numeric-value benchmarks for low-resource languages to test factual grounding and temporal consistency.
