# Models & Agents
> **Apriel's 27B open model scores 98.9 on Big Bench Audio while adding native speech and tool calling.**

**What You Need to Know:** Apriel Voice 27B Preview unifies speech input, reasoning, and tool use in one open model built on Gemma 4. It posts 98.90 on Big Bench Audio, 81.13 on Speech-BFCL, and 65.51% task success on τ-Voice with 1.91-second mean latency. Builders should test its two-stage training recipe for adding speech to existing backbones.
---
### Top Story
Apriel Voice 27B Preview ships as an open speech-language model that processes audio directly and outputs both text responses and tool calls without a separate dialogue model. Built on the post-trained Gemma 4 26B-A4B checkpoint, it keeps text and image modalities while adding a two-stage training process: first establishing the speech interface, then jointly adapting the projector and backbone with supervised fine-tuning, text replay, and source-dependent losses. In thinking mode it reaches 98.90 on Big Bench Audio, 81.13 on Speech-BFCL, and 65.51% task success on τ-Voice at 1.91-second mean latency; English EVA accuracy is 51.27% and experience pass@1 is 74.13%. The model runs on a custom serving platform for interactive voice sessions. Watch for community fine-tunes that extend the same recipe to other 20B–30B backbones. Source: [arxiv.org](https://arxiv.org/abs/2610.40738)
---
### Model Updates
**HyperRepair recovers general capabilities of fine-tuned models at inference cost only: arXiv NLP**
The framework trains a hypernetwork on source-model repairs that generates a prompt-conditioned Repairing Side Net using activation fingerprints. On two model families, 12 LoRA datasets, and 15 general benchmarks it retains 99.5% of domain performance while recovering 93.4% of the base model's average general score. No target-domain examples or extra optimization are required at inference. Source: [arxiv.org](https://arxiv.org/abs/2610.41147)

**KV-Cache Patching transfers fine-tuned behaviors by swapping KV states between base and adapted models: arXiv NLP**
Patching the KV cache from a LoRA-tuned model into the base transfers behaviors such as German response style or emergent misalignment; the reverse removes them. The effect concentrates at a few pivotal positions, especially system-prompt and chat-template tokens, and scales with the fraction of the cache replaced. Source: [arxiv.org](https://arxiv.org/abs/2610.41480)

**Li²SAO lifts single-rollout asynchronous RL with group-relative actor-critic bootstrapping: arXiv NLP**
The method trains the actor with group-relative advantage and the critic with group-centered return while the value model is cold, then switches to single-rollout GAE. It closes the early-training gap with GRPO on agentic tasks and raises the later performance ceiling; code is at https://github.com/jd-cc-coder/Li2SAO. Source: [arxiv.org](https://arxiv.org/abs/2610.40726)

**BYOD converts autoregressive models to diffusion language models with LoRA-only adapters: arXiv NLP**
The recipe works on Gemma 2 9B, Llama 3.1 8B, Qwen2.5 7B, and Ministral 8B using 4.1–5.8% of final parameters and at most 102.4M tokens per conversion. All four models generate from fully masked sequences and retain substantial parent knowledge; BYOD-Gemma reaches 50.6% average accuracy on a nine-task suite. Source: [arxiv.org](https://arxiv.org/abs/2610.41574)

**Saidzoda-Tajik-LFM-2.6B adapts a hybrid model for Tajik tool calling via continued pretraining then SFT: arXiv NLP**
LoRA CPT on 1.48M cleaned Tajik documents for three epochs followed by one epoch of mixed tool-call SFT lifts strict full-call accuracy on a 174-item Tajik BFCL-derived test from 20.69 to 64.14. English tool-calling accuracy stays flat at ~77; CPT alone erases the native tool-call format. Source: [arxiv.org](https://arxiv.org/abs/2610.41576)

**EDU-Jev supplies single-pass decision models at 0.8B–4B for education tasks: arXiv NLP**
A pointer head restricts predictions to predefined options and returns a probability distribution without text generation. The 4B variant hits 67.6% average accuracy across twelve education benchmarks, beating the strongest commercial API by 9.4 points and the best open 4B model by 18.7 points while running ~150 decisions per second on one H100. Source: [arxiv.org](https://arxiv.org/abs/2610.41079)
---
### Agent & Tool Developments
**HCLTech launches AI agents to automate enterprise mainframe operations: The Economic Times**
The agents target routine mainframe tasks in enterprise environments. No further technical details or benchmarks are supplied in the announcement. Source: [m.economictimes.com](https://m.economictimes.com/tech/artificial-intelligence/hcltech-launches-ai-agents-to-automate-enterprise-mainframe-operations/articleshow/135453649.cms)

**Instinct fixes WhatsApp disruption with its personal AI agent: The Indian Express**
The agent handled the service outage for users. Limited technical description is available. Source: [indianexpress.com](https://indianexpress.com/article/technology/artificial-intelligence/instinct-whatsapp-disruption-ai-agents-what-happened-10947160/)

**AI Travel Agents give hotels a new guest to impress: PYMNTS.com**
Hotels must now optimize for AI intermediaries that book on behalf of travelers. The article discusses shifting marketing and service expectations but supplies no concrete metrics. Source: [pymnts.com](https://www.pymnts.com/news/artificial-intelligence/2026/ai-travel-agents-give-hotels-a-new-guest-to-impress/)

**AgenticTuner calibrates cosmological simulations with a present-day LLM as optimizer: arXiv NLP**
The pipeline supplies informal human-readable priors (codebase, documentation, heuristics) to the agent. It reaches competitive calibration performance at a fraction of the CPU cost of Bayesian optimization. Source: [arxiv.org](https://arxiv.org/abs/2610.40685)

**Safin-1.5 adds a safety-native architecture and verifiable reasoning harness for recursive safety improvement: arXiv NLP**
Persistent safety states and hazardous-knowledge disentanglement allow targeted removal of risky experts. The formal-reasoning harness recovers missing relations via proof-obligation-guided semantic bridging and outperforms frontier models on safety and reasoning tasks. Source: [arxiv.org](https://arxiv.org/abs/2610.40751)
---
### Practical & Community
**4" touchscreen for inference engine monitoring: r/LocalLLaMA**
A builder wired an ESP32-based 4-inch screen to display a btop++-style TUI dashboard for a DGX cluster. Firmware is on GitHub with a SKILL.md file so agents can compile it; a 3D-printed dock is in progress. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1xlsuwf/4_touchscreen_for_inference_engine_monitoring/)

**Weekend hack: HackerTube: Andrej Karpathy (X)**
Claude filtered 43M Hacker News comments spanning 20 years down to 6,454 repeatedly recommended videos and built a YouTube-style site around them. The data zip is public; state lives in the browser session with no login required. Source: [x.com](https://x.com/karpathy/status/2116980174667583602)

**SimXAI adds a lightweight LLM-centric conversational layer for existing XAI resources: arXiv NLP**
A single tool-calling LLM replaces separate intent, dialogue-management, and template modules. It improves task accuracy and reduces turns versus GUS-style agents while preserving faithfulness; evaluation code and datasets are released. Source: [arxiv.org](https://arxiv.org/abs/2610.41856)

**PersonaChatBench evaluates chat assistants across diverse simulated users: arXiv NLP**
The benchmark pairs identical tasks with multiple persona cards that encode distinct needs and behaviors. Task performance and need fulfillment vary across personas; strong aggregate scores do not guarantee consistent satisfaction of individual user requirements. Source: [arxiv.org](https://arxiv.org/abs/2610.42060)
---
### Also Today
**Qistas: A Pre-Registered, Portable Protocol for Fairness Evaluation of Large Language Models: arXiv NLP**
The protocol measures procedural symmetry, differential refusal, and stereotype reliance across matched counterfactual pairs for Iraqi social constituencies and releases the full authoring apparatus plus pre-registration. Source: [arxiv.org](https://arxiv.org/abs/2610.40893)

**CoFiBreak improves attack diversity in automated red teaming while preserving effectiveness: arXiv NLP**
A coarse-to-fine diversity reward applied only to successful attacks yields 1.6–2.0× more distinct strategies on HarmBench and 2.1× higher diversity on AdvBench versus the strongest baseline. Source: [arxiv.org](https://arxiv.org/abs/2610.40926)

**Adaptive Personalization Under Preference Epistemic Uncertainty: arXiv NLP**
Models show a 35–46% drop in strategy calibration during open-ended generation versus multiple-choice recognition and default to exploit-first behavior; targeted training on internal strategy representations narrows the generalization gap by one-third. Source: [arxiv.org](https://arxiv.org/abs/2610.40930)

**Better Retrievers, Worse Labels: How Incomplete Relevance Judgments Distort Abstention Evaluation in Conversational RAG: arXiv NLP**
Stronger retrievers increase the share of no-gold contexts that still contain the answer (28% to 72%), dropping shortcut precision from 0.68 to 0.10; the authors release code, runs, and content-based labels. Source: [arxiv.org](https://arxiv.org/abs/2610.40966)

**Fewer Heads, Fewer Memories: Pruning Redundant Attention Heads Suppresses Verbatim Memorisation: arXiv NLP**
Zeroing 729 task-redundant heads in GPT-2-XL cuts memorization count by 91.5% while improving WikiText-103 perplexity by 0.92. Source: [arxiv.org](https://arxiv.org/abs/2610.40974)

**Do Open Language Models Invent Scripture? BILAL-BENCH: arXiv NLP**
Six of seven evaluated models confidently fabricate on 79.3–95.3% of source-production questions in Bengali; hadith provenance is the weakest category with only two of 315 responses correct and sourced. Source: [arxiv.org](https://arxiv.org/abs/2610.40996)

**The Generative Gap Between Speculative Drafter and Continuous Diffusion Language Model: arXiv NLP**
LangFlow outperforms DSpark variants on GenPPL and MAUVE at lengths 128 and 1024 under equal training budgets; increasing denoising steps at fixed weights further improves results at shorter lengths. Source: [arxiv.org](https://arxiv.org/abs/2610.40847)

**TraceSpec improves speculative decoding for LLM agents via trajectory-conditioned draft training: arXiv NLP**
The method raises replay throughput 12.5–22.6% over its DSpark base across three target sizes; adaptive allocation increases accepted length 3.3–10.0% over fixed full-turn supervision. Source: [arxiv.org](https://arxiv.org/abs/2610.41177)

**Beyond Response Scoring: An AI-aware Cognitive Supervision Framework for Automated Mathematical Short Answer Grading: arXiv NLP**
AICG reduces MAE by 50.3% and lifts QWK from 0.798 to 0.927 versus plain RoBERTa regression; AI-aware weighting adds a further 4.2% MAE reduction on post-Gen-AI semesters. Source: [arxiv.org](https://arxiv.org/abs/2610.41215)

**PsyInterviewee separates protected truth and dynamic interaction channels for reliable mental-health interview simulation: arXiv NLP**
Asymmetric write permissions keep clinical facts fixed while allowing disclosure and behavioral states to evolve; it outperforms four baselines on informational invariance and relational adaptivity. Source: [arxiv.org](https://arxiv.org/abs/2610.41289)

**In-Model Context Compression with Agentic Soft Tokens for Long-Horizon LLM Agents: arXiv NLP**
ASTC uses the model's native recurrent dynamics to carry absorbed information forward as soft tokens, cutting end-to-end Attention Pairs by up to 50.68% while matching uncompressed accuracy. Source: [arxiv.org](https://arxiv.org/abs/2610.41291)

**From Transcription to Reformulation: Defining and Benchmarking Grounded Generative Speech Recognition: arXiv NLP**
GSR-Bench introduces a four-level hierarchy of reformulation capabilities and a multi-dimensional evaluation framework; experiments reveal acoustic hallucination and instruction drift as key failure modes. Source: [arxiv.org](https://arxiv.org/abs/2610.41292)

**Comparative Evaluation of LLM-Based Review Paradigms for Academic Paper Quality Assessment: arXiv NLP**
Direct absolute rating matches comparative ranking on rank correlation with human scores yet compresses predictions above the accept threshold; abstract-only input beats full-paper summarization and model choice matters as much as paradigm choice. Source: [arxiv.org](https://arxiv.org/abs/2610.41391)

**BlindToChange measures whether agents proactively discover recent events that affect their responses: arXiv NLP**
A 27.5-point gap appears when the needed fact is not explicitly mentioned versus when it is; more than half of failures trace to agents never searching to verify assumptions. Source: [arxiv.org](https://arxiv.org/abs/2610.41435)

**KEEPER learns control-sufficient textual memory for long-horizon agents: arXiv NLP**
Reward-related prediction yields the highest task performance before and after offline RL; claim-level analysis shows error persistence despite corrective observations. Source: [arxiv.org](https://arxiv.org/abs/2610.41482)

**Sparse Text Diffusion under Dual Budgets: Context Connectivity and Expert Activation: arXiv NLP**
Normalized masked attention and conditional expert computation respect separate edge and activation budgets; a DualBudget configuration cuts cost 20% relative to DiffuSeq under the reported timing. Source: [arxiv.org](https://arxiv.org/abs/2610.41487)

**Enhancing Knowledge Entity Relation Extraction in Abstracts and Full-text Content of Academic Articles Using Large Language Models: arXiv NLP**
LoRA-adapted T5 reaches the highest macro F1 (0.7408 abstract, 0.7013 full-text); LLM-generated entity descriptions help SLMs, and combining strategies with complementary error patterns further improves results. Source: [arxiv.org](https://arxiv.org/abs/2610.41552)

**CEFR Level Assessment across Languages and Text Granularities: arXiv NLP**
Focal loss plus supervised contrastive learning outperforms strong baselines on sentence- and document-level CEFR prediction in both monolingual and multilingual settings. Source: [arxiv.org](https://arxiv.org/abs/2610.41553)

**When Steering Shifts Discourse: Identifying and Intervening on Discourse-Level Changes due to Activation Steering in LLMs: arXiv NLP**
Steering alters formality, evidence use, and ambiguity; a second complementary vector restores ~78% of unintended discourse changes while preserving 93% of the intended behavior. Source: [arxiv.org](https://arxiv.org/abs/2610.41661)

**Precision–Recall Trade-off on the Inference Level for LLMs in Grammatical Error Correction: arXiv NLP**
The repetition penalty parameter alone enables controllable precision–recall adjustment at inference time without architecture or prompt changes. Source: [arxiv.org](https://arxiv.org/abs/2610.41698)

**GraphNIAH: A Benchmark for Long-Context Reasoning over Real-World Graphs: arXiv NLP**
Accuracy falls with reasoning depth; at depths 16 and 32, GPT-5.6 and Qwen3.5 models answer YES/NO questions no better than random, mostly by answering NO. Source: [arxiv.org](https://arxiv.org/abs/2610.41704)

**Stepwise-Querying distills reasoning without teacher chain-of-thought access: arXiv NLP**
Independent queries elicit step-specific explanations that are assembled for SFT; the method wins 14 of 16 comparisons across two teachers, two students, and four benchmarks. Source: [arxiv.org](https://arxiv.org/abs/2610.41769)

**Peeling the Matryoshka: Extracting Ontological Structure from Retrieval Embeddings: arXiv NLP**
Prefix length in Matryoshka embeddings aligns with taxonomy granularity; PEEL recovers taxonomic DAGs with high structural fidelity on two OLLM benchmarks using only a concept vocabulary. Source: [arxiv.org](https://arxiv.org/abs/2610.41785)

**Iterated Integrals as Lexical Fingerprints: Path Signature Embeddings for Lexical Similarity: arXiv NLP**
Depth-2 signatures optimally balance character- and word-level sensitivities and preserve word order; the critical lexical variance sits in a compact PCA subspace. Source: [arxiv.org](https://arxiv.org/abs/2610.41855)

**Text as an Index for Zero-Shot Cross-Domain Knowledge Tracing: arXiv NLP**
TIZSKT separates behavioral sequence modeling from domain-local evidence construction and uses text only as an index; it achieves the highest mean AUC and accuracy on all target domains in leave-one-domain-out tests. Source: [arxiv.org](https://arxiv.org/abs/2610.41883)

**Aligning MLLMs with the Latent Structure of Human Cognition via Behavior-Derived Semantic Dimensions: arXiv NLP**
A 66-dimensional embedding space derived from 4.7M human Odd-One-Out judgments supplies dimension-grounded rationales; RSA on an fMRI dataset shows increased human-model representational alignment. Source: [arxiv.org](https://arxiv.org/abs/2610.41951)

**TurnTurk-GPT predicts turn-taking in Turkish from text: arXiv NLP**
Fine-tuning Turkish GPT-2 with the TurnGPT objective on synthetic and real dialogue beats both rule baselines and a multilingual end-of-turn detector under recording-disjoint and speaker-disjoint evaluation. Source: [arxiv.org](https://arxiv.org/abs/2610.42010)

**Asynchronous Flow Map Language Models enable one-step parallel generation with learned ordering: arXiv NLP**
State-adaptive asynchronous flows define tokenwise denoising schedules; the distilled models set new state-of-the-art one-step performance on Sudoku and GSM8K code generation. Source: [arxiv.org](https://arxiv.org/abs/2610.42018)

**CRoS improves CoT faithfulness by scrambling step order while preserving content: arXiv NLP**
The metric avoids confounding from information changes; on Reasoning Gym it raises out-of-domain accuracy to 46.8%, CoT quality, and hint-acknowledgment score versus outcome-only and prior causality rewards. Source: [arxiv.org](https://arxiv.org/abs/2610.42054)

**RangeSWA enables training-free length extrapolation for continuous diffusion language models: arXiv NLP**
Local sliding-window attention, remote block summaries, and dynamic retrieval plus positional remapping and adaptive window scheduling reduce repetition and semantic drift beyond training length. Source: [arxiv.org](https://arxiv.org/abs/2610.42084)

**Subquadratic Attention with a Hierarchical Tree-Structured Indexer: arXiv NLP**
ZHA grows a tree of compressed key summaries; total cost grows sublinearly in sequence length while preserving long-context retrieval and reasoning performance after a short KL-distillation stage. Source: [arxiv.org](https://arxiv.org/abs/2610.42112)

**DecisionRank trains decision-model rerankers via item-space on-policy distillation: arXiv NLP**
The 1.7B model beats its 27B generative teacher on TREC DL19–23; the 8B version outperforms its listwise counterpart while running 24.5× faster on TREC DL. Source: [arxiv.org](https://arxiv.org/abs/2610.42128)

**Flide accelerates decision inference with exact state forking: arXiv NLP**
ForkAttention navigates request dependencies via GPU-resident indices across attention and Gated DeltaNet layers; it answers queries up to 9.5× faster than vLLM/SGLang while staying closest to float32 reference. Source: [arxiv.org](https://arxiv.org/abs/2610.42148)

**Prevented is Not Protected: What Attack Success Rate Hides about RAG: arXiv NLP**
Existing defenses can introduce unexpected target-positive answers; the matched-query protocol with content-based labeling reveals that defense rankings shift when prevented versus introduced failures are distinguished. Source: [arxiv.org](https://arxiv.org/abs/2610.40742)

**FARO reallocates per-block optimizer budgets by cross-block equal-risk contribution: arXiv NLP**
The adaptive arm matches the best hand-designed recipe; the ERC variant lowers clean-data loss on every seed by an average 0.0136 nats with no added time or memory. Source: [arxiv.org](https://arxiv.org/abs/2610.40858)

**Oh tbc Claude filtered it down a lot: urls, regexes, dropping spam, only the remainder was dispatched to Sonnet with a CC Workflow (so it uses the sub tokens). You can see surviving comments under videos, the comments that recommend videos seem to be of nice & helpful character.: Andrej Karpathy (X)**
Filtering reduced 43M comments to the final 6,454-video set before Sonnet handled the remainder. Source: [x.com](https://x.com/karpathy/status/2116970707867566106)
---
### Under the Hood: Pointer Heads for Single-Pass Categorical Decision Models
Pointer heads let a model output a probability distribution over a fixed set of options in one forward pass by scoring each option with a learned marker instead of generating tokens. The core move is to replace the usual language-modeling head with a small set of option-specific linear probes that share the same encoder; because the output vocabulary is now exactly the allowed choices, calibration becomes a direct softmax over those scores rather than an indirect mapping from free-form text. This removes both the parsing step and the risk that the model produces an out-of-set answer. On education benchmarks the approach yields 67.6% average accuracy at 4B parameters while sustaining 150 decisions per second on a single H100, roughly an order of magnitude faster than any text-generation baseline that must be post-processed. The quality gain disappears once the option set grows beyond a few hundred entries because the pointer head must still compete with the encoder's capacity; at that scale a lightweight reranker on top of a generative model becomes preferable. The practical decision rule is therefore simple: use pointer heads when the task is closed-set classification with a stable label inventory and latency matters; fall back to generation-plus-parsing when the label space is open or changes frequently.
---
### Things to Try This Week
- Test Apriel Voice 27B on speech-conditioned tool-calling tasks; its two-stage recipe is fully described and the model is open.
- Run the HackerTube data zip through your own agent to generate a personalized video feed filtered by topic or era.
- Compare HyperRepair against standard LoRA reversal on any fine-tuned 7B–13B model you already have; the hypernetwork checkpoint is released.
- Try the pointer-head training recipe from EDU-Jev on a small education or multiple-choice dataset to measure single-pass latency gains.
- Apply KV-Cache Patching to a safety-tuned model to see how much of the alignment behavior transfers without retraining.
---
### On the Horizon
- More open speech-language models are expected to adopt the two-stage projector-plus-backbone recipe demonstrated by Apriel.
- Agentic calibration pipelines like AgenticTuner will likely appear for other scientific simulators beyond cosmology.
- Decision-model rerankers trained with item-space on-policy distillation are expected to target additional retrieval benchmarks.
- Portable fairness protocols modeled on Qistas are anticipated for additional languages and regulatory jurisdictions.
