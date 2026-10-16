# Models & Agents
> **Pause-token KV compression shrinks cache 3.5x and speeds H100 inference 3.2x on long math problems.**

**What You Need to Know:** AbridgeKV trains pause tokens to compress completed reasoning blocks into compact KV entries, matching full-cache accuracy on 446 competition problems while cutting memory and latency. Several new papers introduce reusable control layers, topology generators, and medical report analyzers that separate domain logic from execution. Builders should watch the vLLM integration for AbridgeKV and the released code for PRISM topology learning and Wolof-adapted models.
---
### Top Story
AbridgeKV trains a model to compress each completed block of generated chain-of-thought into the KV entries of a few learned pause tokens that produce no output. The pause tokens receive positions inside the replaced block, cache budget is allocated by measured layer value, and compression runs on relatively large blocks. On 446 problems from AIME, HMMT, AMC and similar contests with 32K-token generations, keeping one quarter of the cache matches an identically trained full-KV model in both accuracy and output length. The strongest published eviction baseline at the same budget produces far longer outputs, while a retrained compressor baseline loses 10 accuracy points. Served in vLLM the cache becomes 3.5 times smaller per sequence and a saturated H100 finishes problems 3.2 times faster than with full KV. Source: [arxiv.org](https://arxiv.org/abs/2610.20641)
---
### Model Updates
**CoTS: Competitive Token Selection for Latent Reasoning in Large Language Models: arXiv NLP**
CoTS is a training-free framework that uses probability competition between the two most likely tokens to allocate continuous weight between discrete commitment and soft exploration at each step. The second candidate represents the strongest alternative, so larger separation signals stability and keeps the representation close to the sampled token. Smaller separation increases the soft contribution to retain alternatives. The method requires no extra forward passes or tuned thresholds. Experiments across six reasoning benchmarks show consistent gains over standard CoT and prior training-free latent methods. Source: [arxiv.org](https://arxiv.org/abs/2610.20642)

**Wolof-Adapted Industry-Ready Open-Weight Language Models: arXiv NLP**
The work releases 0.6B–14B open-weight models instruction-tuned, preference-aligned and merged for Wolof, a language spoken by 23 million people mainly in Senegal. After the full pipeline the 8B and 14B variants remain competitive with much larger commercial systems on 63 public and internal tasks while preserving cross-lingual performance. The models are already in internal customer-care pilots and available on Hugging Face. Source: [arxiv.org](https://arxiv.org/abs/2610.20824)

**Verdict: Encode Once, Decide Many: arXiv NLP**
Verdict-MQ is a 395M encoder that reads a case once and answers every typed question about it through a structured attention mask that keeps state encoding independent of the questions. On the typed-decisions benchmark it matches soft gold labels better than the released 421M Laya specialist across five seeds while preserving per-system temperature scaling advantages. Source: [arxiv.org](https://arxiv.org/abs/2610.20778)

**APRiL: An Open-ended Benchmark for Chinese Social Awareness in Large Language Models: arXiv NLP**
APRiL supplies 2,196 instances across six categories with instance-specific rubrics for two tasks: Social Scenario Analysis and Socially Aware Response. Experiments on 12 models from six families reveal a consistent gap between understanding and response quality, with higher-quality analyses improving downstream responses. Data and code are released. Source: [arxiv.org](https://arxiv.org/abs/2610.20785)

**CoTranslator: Reverse to Forward Chain-of-Thought Translator for Reasoning Distillation: arXiv NLP**
CoTranslator learns to translate cheaper reverse-CoT rationales into the distribution of verified forward responses using a small paired set. Across six student models on six math benchmarks it improves average accuracy over semantic suppression by up to 5.82 points and retains 95 percent of rejection-sampling accuracy at 35.9 percent of the compute for 4B students. The translator transfers without retraining to new datasets, teachers and STEM problems. Source: [arxiv.org](https://arxiv.org/abs/2610.20828)
---
### Agent & Tool Developments
**DeepUnfolding_Agent: A Classical_Quantum Adaptive Control API: arXiv NLP**
DeepUnfolding Agent is a schema-driven FastAPI service that registers optimization strategies, accepts round-level diagnostics, returns bounded control actions and updates from executor feedback. It supports classical, quantum-aware, hybrid, Qiskit Aer and IBM Quantum pathways through a strategy registry, safety guard and Docker deployment. Validation covers unit, schema, API, safety, orchestration and hardware-backed tests across finance, healthcare, genomics and noisy quantum simulation. Source: [arxiv.org](https://arxiv.org/abs/2610.20615)

**PRISM: PRIvileged Sibling-guided Multi-Agent Topology Design: arXiv NLP**
PRISM recovers per-query preference signals from execution-verified graph corpora by training a student to match a teacher that sees a sibling solution graph unavailable at deployment. The privileged low-rank branch supplies the missing ranking signal that standard SFT lacks. Across six diverse benchmarks the method improves over every prior topology-design baseline. Code is released. Source: [arxiv.org](https://arxiv.org/abs/2610.20628)

**MeddeX: A Retrieval-Augmented LLaMA-3 System with Gemini Vision for Evidence-Backed Medical Report Analysis: arXiv NLP**
MeddeX fine-tunes LLaMA-3 8B with QLoRA, adds RAG and a Gemini Vision layer, and handles text PDFs, scanned PDFs and radiological images through a hybrid extraction pipeline with garbage-text detection. It adds report-scoped retrieval, longitudinal comparison and a self-healing backfill pipeline. Against the base LLaMA3-Med42-8B it records ROUGE-1 +9.2 percent, ROUGE-2 +10.0 percent, ROUGE-L +11.8 percent, BLEU +71.4 percent and BERTScore +0.8 percent. Source: [arxiv.org](https://arxiv.org/abs/2610.20632)

**ReviewPilot: A Multi-Agent System for Screening and Data Extraction in Systematic Reviews: arXiv NLP**
ReviewPilot is a conversational multi-agent system that automates the PRISMA workflow from screening to extraction while recording exclusion reasons and source locations for every value. On epidemiological expert reviews it outperforms single-prompt LLMs and AgentSLR across three LLMs, reaching screening macro F1 of 0.776 and extraction F1 of 0.788. Code is released. Source: [arxiv.org](https://arxiv.org/abs/2610.21042)
---
### Practical & Community
**Jev-as-a-Judge for RAG Claim Verification: Confidence-Gated Cascading Between a Non-Generative Verifier and a Frontier LLM: arXiv NLP**
Jev is a non-generative decision model that returns typed values and native probabilities without text. On 495 human-labelled claims it matches a frontier LLM within 0.56 points at 187-fold lower cost while disagreeing on 15.2 percent of items. A confidence-gated cascade reaches 74.10 at USD 2.92 per thousand claims versus 73.83 at USD 8.93 for the frontier model alone. All predictions, prompts, pricing and code are released. Source: [arxiv.org](https://arxiv.org/abs/2610.20634)

**SHIP: Structured and Hierarchical Insight with Privacy: arXiv NLP**
SHIP maps analytical queries to attributes, builds a hierarchical hybrid taxonomy and releases a differentially private synthetic table. It outperforms prior private insight baselines on QA performance and structured fidelity while surfacing queries that remain difficult for structured representations. Source: [arxiv.org](https://arxiv.org/abs/2610.21048)

**PremiseCheck: Efficient Fact-Checking of Human and AI Peer Reviews: arXiv NLP**
PremiseCheck rewrites each review comment into explicit premises with an LLM, then checks every premise against the paper using a cheap decision model. When each comment is checked independently it matches GPT-5.5 accuracy across NLP, machine learning and natural sciences at roughly half the cost and, on NLP reviews, at one quarter the cost and less than half the latency. Source: [arxiv.org](https://arxiv.org/abs/2610.21046)

**ToolBottleneckBench: Measuring Tool-Agent Performance under Controlled Pressures and Fixed Harness Budgets: arXiv NLP**
ToolBottleneckBench holds tasks fixed while varying one pressure at a time: tool catalog, visible menu, certified workflow or record encoding. Across 21 model and harness configurations the visible menu produces the only large penalty, which tracks truncation at the completion cap. Raising the cap sixteenfold removes most of the penalty. The benchmark and grader are released. Source: [arxiv.org](https://arxiv.org/abs/2610.21098)

**PEDBench: Can Speech Models Detect Phonetic Errors?: arXiv NLP**
PEDBench supplies 2,605 recordings spanning child speech errors, acted errors and synthetic phone-conditioned TTS, all double-annotated by phonetically trained listeners. Thirteen state-of-the-art speech models fail to reliably detect errors even under controlled conditions and show low precision on correctly pronounced phonemes. Speech-language models fine-tuned on the synthetic portion outperform commercial and open-source baselines on word-level detection, though a sim-to-real gap remains. Source: [arxiv.org](https://arxiv.org/abs/2610.20830)
---
### Under the Hood: Initiative Vectors in Full-Duplex Spoken Models
Full-duplex spoken models must decide at every frame whether to speak, yet each set of weights encodes only one fixed conversational style. The decisive quantity turns out to be a single late-layer residual-stream direction that can be read without training or annotation and then scaled during generation. Shifting this direction moves the speech ratio from the unsteered 21–30 percent range to anywhere between 6–12 percent and 42–61 percent, and the shift remains consistent across conversations, model weights and corpora. A short reference recording from a target speaker is enough to extract the matching direction and transfer that speaker’s turn-taking style; swapping in a different reference worsens the match in 93–98 percent of cases. The same direction also anticipates onsets up to 800 ms ahead, giving an early signal that downstream systems can use for smoother barge-in handling. The practical takeaway is that conversational personality is not frozen into weights but lives in a steerable direction that can be calibrated per user at inference time with negligible extra cost.
---
### Things to Try This Week
- Integrate AbridgeKV into a vLLM deployment for long chain-of-thought math or coding tasks to cut KV memory by 3.5x with no accuracy loss.
- Download the released Wolof 8B or 14B models from the Orange collection on Hugging Face and test them on mixed Wolof–English customer-care dialogues.
- Run the PRISM topology generator on your own multi-agent task corpus to obtain ranked collaboration graphs instead of frequency-biased ones.
- Try PremiseCheck on a batch of recent peer reviews to see whether the premise-rewrite plus decision-model pipeline halves your fact-checking spend.
---
### On the Horizon
- Wolof-adapted models move from internal pilots to broader public release with documented commercial licensing terms.
- ReviewPilot’s project-memory and dialogue-driven schema editing will be extended to additional systematic-review domains beyond epidemiology.
- PEDBench acted and synthetic datasets plus fine-tuning recipes will be published to close the remaining sim-to-real gap for phonetic error detection.
- CoTranslator will be evaluated on additional STEM subjects and larger student models to quantify compute savings at scale.
