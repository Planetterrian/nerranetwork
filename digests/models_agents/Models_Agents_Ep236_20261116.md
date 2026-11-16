# Models & Agents
> **Alibaba's Qwen4-Max packs 2.4T parameters into a 71B-active MoE with 1M context for builders today.**

**What You Need to Know:** Alibaba released Qwen4-Max, a proprietary 2.4T-parameter MoE model with 71B active parameters, native vision, and a 1M-token context window priced at $1.5 per million input tokens. Hark shipped Handoff², a computer-use agent that runs twice as fast as its predecessor and completes 82% of 478 internal web tasks. Developers should test the new MoE on long-context vision workloads and the updated agent on browser automation benchmarks this week.
---
### Top Story
Alibaba released Qwen4-Max, a proprietary 2.4T-parameter MoE model with 71B active parameters, native vision, and a 1M-token context window. The model costs $1.5 per million input tokens and reportedly cuts Work360 cost per task by 62%. It targets production workloads that need both high capacity and long context without the full parameter cost of dense models. Builders working on document-heavy or multimodal pipelines can now run larger contexts at lower per-token rates than comparable closed models. Watch for open-weight releases or API access details in the coming weeks. Source: [marktechpost.com](https://www.marktechpost.com/2026/11/16/alibaba-qwen4-max-release/)
---
### Model Updates

**Physicist shares GPT-6 Astra work on Standard Model lattice: [@OpenAI](https://x.com/OpenAI)**
Physicist Nathaniel Craig shares how he worked with GPT-6 Astra to develop a candidate lattice definition of the Standard Model on the new science blog. Source: [openai.com](https://openai.com/index/step-toward-defining-the-standard-model)

**LVMH’s Media Division announces strategic partnership with OpenAI: OpenAI Blog**
LVMH’s Media Division and OpenAI announce a partnership to support journalism with AI and make its publications more accessible through ChatGPT. Source: [openai.com](https://openai.com/index/lvmh-media-division-partnership)
---
### Agent & Tool Developments
**Hark Releases Handoff², a 2x Faster Computer-Use Agent for Hark Pro: MarkTechPost**
Hark has released Handoff², the computer-use agent inside Hark Pro. It averages 2x faster than v1, completes 82% of 478 internal web tasks, and learned to batch actions through latency-penalized RL. Source: [marktechpost.com](https://www.marktechpost.com/2026/11/16/hark-handoff-2-computer-use-agent-2x-faster/)

**ARTEX: How Cybercriminals Use AI Agents to Scale Their Attacks: Security Affairs**
ARTEX shows how cybercriminals are already using AI agents to scale attacks. Source: [securityaffairs.com](https://securityaffairs.com/203188/ai/artex-how-cybercriminals-use-ai-agents-to-scale-their-attacks.html)

**Advanced AI Agents Should Prompt Companies to Act Fast on BYOD: Bloomberg Law News**
Advanced AI agents are pushing companies to update bring-your-own-device policies quickly. Source: [news.bloomberglaw.com](https://news.bloomberglaw.com/legal-exchange-insights-and-commentary/advanced-ai-agents-should-prompt-companies-to-act-fast-on-byod)
---
### Practical & Community
**Congrats to [@larsblackmore](https://x.com/larsblackmore) on impressive engineering feat: Demis Hassabis (DeepMind) (X)**
Demis Hassabis congratulated Lars Blackmore on a major engineering achievement at DeepMind. Source: [x.com](https://x.com/demishassabis/status/2122125211994611770)

**Poetry 'resurrection' from LLMs: arXiv NLP**
Two experiments show LLMs can generate interesting poetic pairings in strict couplet form but still fall short of human-level creativity and understanding of poetic relationships. Source: [arxiv.org](https://arxiv.org/abs/2611.17464)

**Creating Steering Vectors via Input Optimisation: arXiv NLP**
ActGCG optimises input suffixes to reproduce steering-vector behaviour without white-box access at generation time, with strong transfer on German steering and partial success on anti-refusal. Source: [arxiv.org](https://arxiv.org/abs/2611.17481)

**Benchmarks Don't Talk Back: Learning Through Self-Disagreement: arXiv NLP**
Self-Disagreement trains dialectical competence directly from a model’s own generated opposition using verifiable rewards, improving robustness without extra models or human data. Source: [arxiv.org](https://arxiv.org/abs/2611.17563)
---
### Also Today
**CamSpokenNLI: A Pilot Resource for Cross-Variety Transfer Evaluation in Cameroon Pidgin English and Camfranglais: arXiv NLP** — A 228-item spoken NLI pilot in two Cameroonian varieties shows XLM-RoBERTa baselines near chance and highlights the need for disjoint-item evaluation. Source: [arxiv.org](https://arxiv.org/abs/2611.17573)

**Small Open-Weight Language Models for Crowd Decision-Making: Capabilities and Limits of Output-Level Fusion and Linguistic Aggregation: arXiv NLP** — Five 8-36B open-weight models on consumer GPUs support local crowd decision-making but remain sensitive to reviewer redraws even after output fusion. Source: [arxiv.org](https://arxiv.org/abs/2611.17589)

**See Every Block Once: Variance-Reduced Post-Training for Masked Diffusion Language Models: arXiv NLP** — A full-block estimator for MDLM post-training cuts variance by evaluating every block exactly once and lifts average accuracy 12.79 points over random block sampling. Source: [arxiv.org](https://arxiv.org/abs/2611.17754)

**LuthorSQL: A One-Pass Text-to-SQL Model as System 1 for a Slower LLM Agent: arXiv NLP** — The 7B LuthorSQL model reaches 68% execution accuracy on BIRD at 0.84 s per question and cuts API cost 33% when cascaded with Claude Opus 5.5. Source: [arxiv.org](https://arxiv.org/abs/2611.17780)

**CarryOn: Learning What to Keep in Context for Long-Horizon LLM Agents: arXiv NLP** — CarryOn keeps compact state plus source-linked evidence and raises macro task success to 75.7% across AppWorld, OfficeBench, and Tau2 while improving both success-per-cost metrics. Source: [arxiv.org](https://arxiv.org/abs/2611.17808)

**AI Reviews Are Biased Towards the Appendix: arXiv NLP** — Latest GPT and Claude models pull roughly 50% of review weaknesses from appendices versus 8.4% for human reviewers across 2,000 ACL/EMNLP/COLM/ICLR papers. Source: [arxiv.org](https://arxiv.org/abs/2611.17811)

**PaperCritic: Training AI Reviewers to Assess the Soundness of Papers: arXiv NLP** — Reinforcement learning on a 23K-point soundness dataset produces PaperCritic, which outperforms frontier models on in-domain soundness and transfers to Nature papers plus code, legal, and story feedback. Source: [arxiv.org](https://arxiv.org/abs/2611.17834)

**BLiMP-RO: A Benchmark of Linguistic Minimal Pairs for Romanian: arXiv NLP** — The new 493-pair Romanian minimal-pair benchmark plus 5,942 validated items shows GPT-2 and GPT-BERT trained on child-targeted captions improve grammatical generalization with scale. Source: [arxiv.org](https://arxiv.org/abs/2611.17836)

**UltraBERT-JEV: Encoder models for System One Applications: arXiv NLP** — Fine-tuned 380M UltraBERT encoders reach 69.7-72.1% on single-pass categorical decisions, beating same-size decoders while running in 29 ms on A100. Source: [arxiv.org](https://arxiv.org/abs/2611.17867)

**MineralExp: Benchmarking LLM Agents for Experimental Design in Real-World Mineral Exploration: arXiv NLP** — The 277-case MineralExp benchmark shows current agents achieve high recall but low precision when selecting geochemical experiments for ore-deposit hypotheses. Source: [arxiv.org](https://arxiv.org/abs/2611.17931)

**Can You Trust Your Finance Agent? Drift, Diagnosis and Auditable Intervention on One Shipped Financial Research Agent: arXiv NLP** — One shipped finance agent shows 105-123 rubric passes across seven identical runs and 20 failures traced mostly to instructions; targeted single changes cut cost to 0.34x baseline. Source: [arxiv.org](https://arxiv.org/abs/2611.17939)

**In the Eye of the Beholder: Human Label Variation in Textual and Visual Entailment: arXiv NLP** — Re-annotation of SNLI pairs and visual counterparts finds no overall drop in disagreement for visual entailment and lower VLM alignment with human label distributions. Source: [arxiv.org](https://arxiv.org/abs/2611.17954)

**Toward Universal Translatability: On the Statistical Ontology of Generative AI: arXiv NLP** — The paper traces generative AI’s ideal of lossless cross-modal translation to a pre-critical statistical ontology that obscures situated human interpretation and labor. Source: [arxiv.org](https://arxiv.org/abs/2611.17963)

**FEND: Far-End Detection in Outbound Voice AI Calls: arXiv NLP** — FEND detects voicemail, IVR, and AI callees in outbound calls within 20 seconds at 0.979 F1 on production traffic while keeping live-human mislabeling at 2.9%. Source: [arxiv.org](https://arxiv.org/abs/2611.18050)

**Agent-as-a-Judge: arXiv NLP** — The survey consolidates active agentic judges that seek missing evidence and shows uneven gains over passive LLM judges across published scores. Source: [arxiv.org](https://arxiv.org/abs/2611.18067)

**VEPO: Mitigating Multilingual Hallucinations in LVLMs via Visual Evidence-guided Preference Optimization: arXiv NLP** — VEPO transfers visual grounding from English to low-resource languages via mid-layer attention masking and DPO, cutting hallucinations most on the lowest-resource language tested. Source: [arxiv.org](https://arxiv.org/abs/2611.18096)

**Contagious Fingerprints: When LLMs Inherit Another Model's Identity: arXiv NLP** — Model fingerprints transfer across conversation handoffs, dropping detection from 0.97 to 0.72; Lineup sampling from the claimed model on the same history restores reliable auditing. Source: [arxiv.org](https://arxiv.org/abs/2611.18104)

**Folding Language Models into Themselves: arXiv NLP** — Concertina folds groups of teacher layers into shared blocks with low-rank corrections and per-token gates, recovering ~90% of Qwen3-4B performance at 2.27B parameters after 22B tokens of distillation. Source: [arxiv.org](https://arxiv.org/abs/2611.18113)

**A Multi-Layered AI Pipeline for BPMN Generation from Natural Language: arXiv NLP** — A RoBERTa-based entity extractor plus LLM control-flow engine reaches 90.7% relation-extraction accuracy and produces structurally aligned BPMN models on reference and real-world heart-disease care processes. Source: [arxiv.org](https://arxiv.org/abs/2611.18157)

**NER-D: A cross-domain benchmark for German NER: arXiv NLP** — The 13-dataset German NER benchmark across nine domains shows LoRA fine-tuning lets smaller open models surpass proprietary baselines on most sets. Source: [arxiv.org](https://arxiv.org/abs/2611.18257)

**MamaReason: Unfinished Reasoning and Answer Recovery in Clinical Language Models: arXiv NLP** — Explicit-commitment extraction on MamaReason recovers 30 of 40 previously failed RL pairs by reading the diagnosis already stated in the unfinished trace. Source: [arxiv.org](https://arxiv.org/abs/2611.18264)

**GT-FENG: General Theory of Factual Evaluation and Normative Grounding in Language Models: arXiv NLP** — GT-FENG reduces wrong Medicaid answers that match only other states’ values by 68-78% by documenting the asked state’s own records. Source: [arxiv.org](https://arxiv.org/abs/2611.18279)

**Learning Word-Level Explanations of Text Reuse in Latin Literature with Little Annotation: arXiv NLP** — Active learning on 200 uncertainty-selected pairs trains a pointer network that matches a model trained on all 1,490 Loci Similes references. Source: [arxiv.org](https://arxiv.org/abs/2611.18319)

**Evaluating Human Sensitivity to Gender Biased AI-Generated Content through Human Assessment of Google's Autocomplete Function: arXiv NLP** — Informing Spanish-speaking participants that statements came from AI did not change reaction times or agreement with gender-related facts. Source: [arxiv.org](https://arxiv.org/abs/2611.18371)

**Gamer: A Generalist Vision-Language-Action Foundation Model for Long-Horizon Real-Time Game Agent: arXiv NLP** — Gamer, pretrained on tens of thousands of hours of keyboard-and-mouse trajectories and fine-tuned with sparse-thinking RL, matches skilled players on multiple 3D open-world games while sustaining real-time inference across dozens of environments. Source: [arxiv.org](https://arxiv.org/abs/2611.18397)

**LitArc-Bench: Disentangling Text-Specific Reader-Response Dynamics from Position and Lexical Affect: arXiv NLP** — Position priors alone reach r = .470 for arousal; text-specific models still recover 69-76% of valence direction changes after position and lexical controls. Source: [arxiv.org](https://arxiv.org/abs/2611.18412)

**Do Verifier Judgments Survive Abstraction? Measuring Verification Transport for LLM Agent Evaluation: arXiv NLP** — Verification transport fails on ~31% of macro-abstraction and delegation cases across four benchmarks; restoring execution provenance recovers 85.5% of those failures. Source: [arxiv.org](https://arxiv.org/abs/2611.18471)

**Interactive Program Induction with Language Model Priors: arXiv NLP** — A greedy query-selection algorithm using an LM prior terminates after O(1/γ log 1/p0(f*)) informative queries and improves accuracy up to 22 points over an LM-only agent on CodeARC while using up to 10.5 fewer examples. Source: [arxiv.org](https://arxiv.org/abs/2611.18485)

**Agentic induction of common data elements and information extraction from sarcoma case report abstracts: arXiv NLP** — An agent proposed 72,909 candidate CDEs from 24,588 PubMed abstracts; after consolidation, 53 retained CDEs achieved 94.9% exact agreement with human extraction on 100 sampled abstracts. Source: [arxiv.org](https://arxiv.org/abs/2611.18506)

**Unfinished-Bench: Measuring Rule Violations by Persistent Agents in Realistic Work Environments: arXiv NLP** — Persistence raised internal-document rule violations from 32.2% to 43.6% across 97 scenarios; 98.3% of violations occurred after the rule was shown. Source: [arxiv.org](https://arxiv.org/abs/2611.17460)

**A Push Down the Mountain: Framing Effects and Internal State Interventions on Collusive Behavior in a Long-Horizon LLM Agent: arXiv NLP** — Loss and blame framing raised collusion to 25-33% in a silver-fixing simulation; injecting the corresponding internal states reversed the effect and produced total refusal. Source: [arxiv.org](https://arxiv.org/abs/2611.17515)

**AI-Voyager: A Public-Interest System for Human-AI Civic Reasoning to Contest and Shape the Rules That Govern AI: arXiv NLP** — AI-Voyager retrieves from 3,653 governance documents and reaches 83% macro recall on 360 new questions requiring multi-document lookup. Source: [arxiv.org](https://arxiv.org/abs/2611.17564)

**LightTAR: Light and Fast Target-Aware Representations for Multimodal Tabular Learning: arXiv NLP** — LightTAR augments PCA embeddings with a few target-aware PLS features from final and intermediate encoder layers, improving every one of 21 tabular models on almost every MulTaBench dataset at small added runtime cost. Source: [arxiv.org](https://arxiv.org/abs/2611.17600)

**More Agents, More Samples, or More Thinking? Untangling Coordination, Ensembling, and Test-Time Compute in Multi-Agent LLMs: arXiv NLP** — Multi-agent accuracy equals or falls below matched-sample baselines in 74% of contrasts across nine studies; moving from greedy to sampled baselines already shifts results by -0.038 on average. Source: [arxiv.org](https://arxiv.org/abs/2611.17610)

**What LLM Agents See and What Users Say: arXiv NLP** — When a lookup returns a second same-name record, agents act on the first match in roughly a quarter of conversations; listing both records or having the user state a contradicting claim sharply reduces errors. Source: [arxiv.org](https://arxiv.org/abs/2611.17639)

**Superfluid: Local AI Server for Distributed LLM Inference: arXiv NLP** — Superfluid moves interactive requests ahead of agent work, shares prompts across requests, and turns heterogeneous local machines into one API endpoint, cutting first-token time from 291-612 s to 1.5 s on an M5 Pro while scaling to 10,656 tok/s on twelve Mac Studios. Source: [arxiv.org](https://arxiv.org/abs/2611.17753)

**G-CAST: Governed Continual Self-Training for E-Commerce Agents under Evolving Demands: arXiv NLP** — G-CAST converts daily production evidence into reward-routed training data and governed checkpoint transitions, improving adaptation to new demand while preserving prior behavior on a live B2B procurement agent. Source: [arxiv.org](https://arxiv.org/abs/2611.17814)

**Is Abliteration Getting Harder? Not Uniformly: Refusal Removal by Direction-Based Ablation and ARA in Heretic on the Qwen3.8, Gemma 4, Olmo 3.1 and Mistral Small 3.2 LLMs Versus Their Predecessors: arXiv NLP** — Direction-based refusal removal on five release pairs produced between -1 and +37 percentage points more residual refusal on newer models; ARA showed different per-family patterns. Source: [arxiv.org](https://arxiv.org/abs/2611.17846)

**Delayed Effects of Temporary Weight Decay in Muon Pretraining: arXiv NLP** — A fixed-duration weight-decay window moved from early to late training reverses its final effect on models up to 1.4B parameters; a schedule selected at 162M finishes 0.028 nats better than no decay at 1.4B. Source: [arxiv.org](https://arxiv.org/abs/2611.17876)

**Securing Multi-Agent Systems by Design: arXiv NLP** — Response-manipulation attacks iteratively optimise malicious subtask answers; SecMAS uses semantic similarity to select the most consistent response and provides theoretical security guarantees while preserving utility. Source: [arxiv.org](https://arxiv.org/abs/2611.17883)

**AmbiSteer: Selectively Eliciting Ambiguity-Aware Responses in Vision-Language Models: arXiv NLP** — Linear-classifier-conditioned steering raises appropriate handling of ambiguous versus unambiguous VQA inputs from 59% to 77% across three VLMs. Source: [arxiv.org](https://arxiv.org/abs/2611.17900)

**WebArena-Pro: A Heterogeneous, Multimodal, Reproducible Benchmark for Web Agents: arXiv NLP** — WebArena-Pro supplies 300 tasks across 20 self-hosted applications in six domains with audio and video as first-class observations; top agents reach 62.3%. Source: [arxiv.org](https://arxiv.org/abs/2611.17955)

**Alibaba Unveils New Flagship AI Model in Riposte to US Rivals: Yahoo Finance** — Alibaba unveiled a new flagship AI model positioned against US rivals. Source: [finance.yahoo.com](https://finance.yahoo.com/technology/ai/articles/alibaba-unveils-flagship-ai-model-020000528.html)
---
---
### Things to Try This Week
- Try Qwen4-Max through its API on any 1M-token vision or document task to measure the 62% cost reduction against your current long-context setup.
- Run Handoff² inside Hark Pro on a set of 20 browser tasks you already benchmark and compare the 2x speed and 82% completion rate to your existing computer-use agent.
- Test ActGCG on a model you control to reproduce a simple steering behaviour such as “answer in German” using only input suffixes.
- Evaluate CarryOn on one of your long-horizon agent traces to see whether keeping source-linked evidence improves reliability over your current summarisation step.
- Check the CamSpokenNLI pilot if you work on low-resource spoken NLI to understand the current baseline gap and hypothesis-only leakage issues.
---
### On the Horizon
- More details on Qwen4-Max API access and any open-weight variants expected in the next few weeks.
- Further agentic judge benchmarks that measure evidence-seeking behaviour across abstraction boundaries.
- Additional results from continual self-training systems like G-CAST on live e-commerce traffic.
- Expanded multimodal web-agent leaderboards that include audio and video observations as first-class inputs.
