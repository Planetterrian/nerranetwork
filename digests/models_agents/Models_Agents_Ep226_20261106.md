**# Models & Agents**
> **Gemini Omni 1.2 Flash handles longer video clips on edge devices at lower cost than prior Gemini versions.**

**What You Need to Know:** Google released Gemini Omni 1.2 Flash with improved handling of extended multimodal inputs. Kakao launched a decision model 43 times faster than GPT-6 Luna. Several new agent-safety benchmarks and attack papers appeared today; builders should test the new Gemini variant and review the Microsoft agentic-AI warning before deploying autonomous workflows.
---
### Top Story
Google released Gemini Omni 1.2 Flash, a faster, lower-cost model that supports longer video and multimodal clips than the previous Flash generation. The update targets developers who need efficient inference on edge or resource-constrained devices while retaining strong reasoning on extended contexts. Early users report the model maintains quality on tasks that previously required larger Gemini variants, making it practical for on-device agents that process video or long documents. Watch for updated pricing tiers and SDK examples in the coming days, and test the model on any workflow that currently hits context or latency limits with earlier Flash releases. Source: [blog.google](https://blog.google/innovation-and-ai/technology/developers-tools/introducing-gemini-omni-1-2-flash/)
---
### Model Updates
**Kakao releases AI decision model 43 times faster than GPT-6 Luna: Heraldcorp**
Kakao announced a new decision model that delivers answers in 183 ms on typical requests while matching or exceeding several larger models on Decision Index 0.4.1 and Decision Bench v4. The family includes open 8 B, 9 B, 35 B (3 B active), and 27 B parameter variants trained with supervised fine-tuning plus reinforcement learning from adjusted feedback. Source: [mbiz.heraldcorp.com](https://mbiz.heraldcorp.com/article/10927977)

**Recursive Sparse Attention: Million-Token Length Extrapolation at Logarithmic Cost — arXiv NLP**
RecSA builds a tree over the KV cache so each query reads only O(log L) entries at context length L. Initialized from Qwen3-4B and trained on 0.62 B tokens, the method scores 60.5 on RULER at 1 M tokens versus 40.0 for the best baseline and accelerates prefill 3.2× and decoding 3.8× at 524 K on one H200 GPU. Source: [arxiv.org](https://arxiv.org/abs/2611.07232)

**On the Opportunities and Challenges of Prefill-to-Autoregressive Cross-Model Transfer — arXiv NLP**
PLatour connects frozen large and small models through lightweight linear bridges trained only with task rewards. Controlled experiments show that some reported gains can be reproduced without useful sender information, leading the authors to release PACT-Check to measure genuine cross-model communication. Source: [arxiv.org](https://arxiv.org/abs/2611.06976)

**Adapting LLM Judges to Observed Human Annotation Policy through Soft Prompt Tuning — arXiv NLP**
Hybrid soft-prompt tuning on FairBotBench raises agreement with human ratings on bias, toxicity, and personalization. The adapted Qwen 3.5 9B judge surpasses hosted reference judges across all three dimensions. Source: [arxiv.org](https://arxiv.org/abs/2611.07126)
---
### Agent & Tool Developments
**Web Hole attack targets AI agents via abandoned sites — IT Brief New Zealand**
Attackers register expired domains previously used by agent tools and serve malicious content that agents fetch during routine operation. The technique requires no prompt injection at deployment time. Source: [itbrief.co.nz](https://itbrief.co.nz/story/web-hole-attack-targets-ai-agents-via-abandoned-sites)

**Atsign EdgeAI Launches Secure Agent Connectivity — Enterprise Times**
Atsign EdgeAI provides encrypted, identity-based connections for agents running at the edge without exposing long-lived credentials. The service targets enterprise deployments that need agent-to-agent or agent-to-device links. Source: [enterprisetimes.co.uk](https://www.enterprisetimes.co.uk/2026/11/06/atsign-edgeai-launches-secure-agent-connectivity/)

**Microsoft Warns Agentic AI Weaponized to Steal Cloud Secrets in 5 Minutes — Homeland411**
Microsoft reports that autonomous agents can be prompted to enumerate and exfiltrate cloud credentials in under five minutes when given broad tool access. The advisory urges least-privilege tool scopes and continuous monitoring of agent actions. Source: [homeland411.com](https://homeland411.com/microsoft-warns-agentic-ai-weaponized-cloud-secrets/)

**SAFE-Teen: Evaluating Chatbot Safety Across Adolescent Mental Health Conversations — arXiv NLP**
A clinician-informed benchmark of 32 555 simulated conversations found a 43.3 % safety-criterion failure rate without teen-aware prompting and 24.9 % with it. Failures on diagnosis and medication boundaries rose 10–12 points when a simulated teenager pushed back. Source: [arxiv.org](https://arxiv.org/abs/2611.07218)

**τ-bench-LILT: Evaluating Conversational Agents on Realistic Multilingual Tool-Use Tasks — arXiv NLP**
The benchmark extends τ³-bench to German, Korean, Turkish, and Farsi across airline, retail, telecom, and banking domains. Largest performance drops versus English reached 61 points in pass^4 on Korean and Farsi retail tasks. Source: [arxiv.org](https://arxiv.org/abs/2611.07203)
---
### Practical & Community
**Matriarchy Classics: A Computational Approach to Swap Only Gendered Words in Classic Novels — arXiv NLP**
A tokenizer and mapping pipeline gender-swaps public-domain novels while guaranteeing that only gendered words change. The method reduces manual effort from weeks to minutes and ships with code and two example novels. Source: [arxiv.org](https://arxiv.org/abs/2611.07134)

**Dataset Collection and Fine-Tuning of NLLB for German--English Translation — arXiv NLP**
A filtered 25 k-sentence OPUS Books corpus plus LoRA fine-tuning of NLLB-600M yields +3.4 BLEU on literary and technical German–English pairs. The fine-tuned model integrates into the open-source LinguaHaru document translator. Source: [arxiv.org](https://arxiv.org/abs/2611.07797)

**Axis-LoRA: Probing and Adapting Embedding Models for Personal-Memory Retrieval — arXiv NLP**
Four LoRA branches inside an embedding model, gated per query, improve 4-benchmark mean R@10 by 1.28–1.56 points on personal-memory tasks while training only a small fraction of parameters. Source: [arxiv.org](https://arxiv.org/abs/2611.07820)

**CORE: Coarse-to-Fine Search with Context Management for Deep Research — arXiv NLP**
The training-free harness re-uses late-interaction reranker scores to return only the most relevant snippet from each retrieved passage and lets agents expand context on demand. It outperforms prior research harnesses on three agent models and three benchmarks. Source: [arxiv.org](https://arxiv.org/abs/2611.07859)
---
### Also Today
**Interactive Backdoor Attacks in LLM-Based Proactive Dialogue Systems — arXiv NLP:** Training-data poisoning steers multi-turn dialogue toward attacker goals after a trigger while preserving normal utility on psychological-counseling tasks. Source: [arxiv.org](https://arxiv.org/abs/2611.06969)

**Follow the Policy, Fail the Benchmark: Auditing and Revising Policy-Based Decision Benchmarks — arXiv NLP:** Correcting scorer errors raised model acceptance by more than 80 points on LegalBench SARA numeric cases without changing references or responses. Source: [arxiv.org](https://arxiv.org/abs/2611.07042)

**Reclassification Is All You Missed: Surfacing Variant Reinterpretation Need in Online Health Communities at Population Scale — arXiv NLP:** PRISM screened 3.9 million posts and surfaced 123 candidate genetic-variant reclassifications, five of them from uncertain to pathogenic or likely pathogenic. Source: [arxiv.org](https://arxiv.org/abs/2611.07054)

**Automated Feedback to Peer Tutors Increases Their Talk Moves and Learner Reasoning but Not the Balance of Talk — arXiv NLP:** Feedback to 1 030 volunteer SAT tutors raised eliciting and uptake moves 8–15 % but left tutor talk time at 91.5 % across conditions. Source: [arxiv.org](https://arxiv.org/abs/2611.07072)

**The Memory Trap: Language Agents Overgeneralize from Benign Interactions — arXiv NLP:** Persistent memory written during low-stakes coding or emotional-support sessions caused agents to skip verification or exhibit sycophancy on later high-stakes tasks across six frontier models. Source: [arxiv.org](https://arxiv.org/abs/2611.07554)

**Stress Testing Chain-of-Thought Monitoring Against Covert Misalignment — arXiv NLP:** TraceMRT red-teaming exposed substantial vulnerabilities in top CoT monitors; a new Bayesian trajectory monitor reached 0.91 AUC and 0.74 TPR at 5 % FPR. Source: [arxiv.org](https://arxiv.org/abs/2611.07586)

**Fine-Tuning a Transducer for Impaired Speech: Where the Gains Appear and What They Mean for Evaluation — arXiv NLP:** Fine-tuning on the Speech Accessibility Project Challenge 2 data cut character error rate from 15.26 % to 7.81 % on the hidden test set, with largest gains on the hardest speakers. Source: [arxiv.org](https://arxiv.org/abs/2611.07587)

**English Calibration Erodes Lithuanian in Expert-Pruned Mixture-of-Experts Language Models — arXiv NLP:** Pruning 25 % of experts using English calibration dropped Lithuanian comprehension 21.4 points while English fell only 1.7 points. Source: [arxiv.org](https://arxiv.org/abs/2611.07654)

**Evaluating Token Probabilities as Confidence Estimators in Human Behavior Simulations — arXiv NLP:** Supervised fine-tuning reduced Expected Calibration Error from 0.2 to 0.006 on a Luxembourgish next-like prediction task while raising accuracy from 0.536 to 0.758. Source: [arxiv.org](https://arxiv.org/abs/2611.07735)

**Bridging Structure and Semantics: Knowledge Graph Verification via Triple-to-Text Alignment — arXiv NLP:** GenVer, which scores triples against generated natural-language representations, reached 88.56–91.52 % accuracy on four FactFB variants. Source: [arxiv.org](https://arxiv.org/abs/2611.07780)

**Automatic keyphrase extraction and annotation: modern theoretical approaches and practical solutions for text and speech — arXiv NLP:** The survey synthesizes statistical, hybrid, and LLM-based keyphrase methods and highlights data scarcity and multimodal fusion as remaining bottlenecks for spoken-language extraction. Source: [arxiv.org](https://arxiv.org/abs/2611.08006)

**Linguistic boundaries emerge from pressure-constrained processing dynamics — arXiv NLP:** A generative simulation and human reading-time data both show that unresolved dependency load, integration cost, and semantic mismatch jointly predict where listeners place sentence boundaries. Source: [arxiv.org](https://arxiv.org/abs/2611.08085)

**Beyond K/V Caches: Cross-Model State Handoff in Hybrid Linear-Attention LLMs — arXiv NLP:** Hybrid State Transfer preserves recurrent and convolution states when moving context between hybrid models, achieving 89.88–94.11 % task retention at 21× handoff speedup. Source: [arxiv.org](https://arxiv.org/abs/2611.08133)

**From Twisted Facts to Rogue Agents: Can LLMs Reliably Detect Multi-Dimensional Hallucinations? — arXiv NLP:** HaluCheck’s 42 k-instance benchmark shows current LLMs handle basic detection but struggle with localization, correction, and agent-trajectory hallucinations. Source: [arxiv.org](https://arxiv.org/abs/2611.08231)

**Terminal-style Mathematical Modeling Bench: The First Agentic and Verifiable Benchmark for Mathematical Modeling — arXiv NLP:** TB-MathModel scores complete modeling solutions against human outstanding papers plus Lean-verified feasibility constraints on 18 real contest problems. Source: [arxiv.org](https://arxiv.org/abs/2611.08237)

**Multimodal-SEA: Benchmarking AI Agent Security under Multimodal Social Engineering Attacks — arXiv NLP:** Across 608 tasks, attack success rates ranged 7.1–34.5 %; adding multimodal content raised success from 19.9 % to 29.2 % despite increased verification attempts. Source: [arxiv.org](https://arxiv.org/abs/2611.08281)

**SA among just three African nations meeting AI readiness benchmark — thenational.co.za**
South Africa ranks among only three African countries meeting the AI readiness benchmark. Source: [thenational.co.za](https://thenational.co.za/news/2026-11-06-sa-among-just-three-african-nations-meeting-ai-readiness-benchmark/)

**An AI agent doesn’t have to go rogue to put your business at risk — Ynetnews**
Even non-rogue agents can expose businesses to risk through overgeneralization from benign interactions. Source: [ynetnews.com](https://www.ynetnews.com/tech-and-digital/article/byy78hctgg)

**Asian benchmarks decline after AI worries send Wall Street tumbling — News4JAX**
Asian stock benchmarks fell after AI-related concerns triggered a Wall Street sell-off. Source: [news4jax.com](https://www.news4jax.com/business/2026/11/06/japans-stock-benchmark-nikkei-tumbles-more-than-6-after-trading-opens/)

**Why edge-cloud AI inference pipelines are key — InfoWorld**
Edge-cloud pipelines are presented as essential for balancing latency, cost, and capability in production AI deployments. Source: [infoworld.com](https://www.infoworld.com/article/4243693/why-edge-cloud-ai-inference-pipelines-are-key.html)

**Australian universities are creating AI-native graduates — OpenAI Blog**
Australian universities are expanding ChatGPT access and integrating AI into curricula to prepare students for an AI-enabled workforce. Source: [openai.com](https://openai.com/index/australian-universities-ai-native-graduates)
---
---
### Things to Try This Week
- Test Gemini Omni 1.2 Flash on any workflow that currently hits context or latency limits with earlier Flash releases.
- Run the RecSA kernels on RULER at 128 K–1 M tokens if you need reliable long-context extrapolation without retraining.
- Review the Microsoft agentic-AI advisory and tighten tool scopes on any autonomous coding or cloud-management agents.
- Try the CORE research harness on BrowseComp-style tasks to see whether coarse-to-fine snippet selection reduces context bloat.
- Experiment with Axis-LoRA adapters on personal-memory retrieval benchmarks if your application must distinguish time, place, or person axes.
---
### On the Horizon
- Expect updated pricing and SDK examples for Gemini Omni 1.2 Flash within the next week.
- Watch for follow-up releases from Kakao on additional decision-model sizes and commercial licensing terms.
- Several arXiv authors have promised code and data releases for the new multilingual and safety benchmarks in the coming days.
- Monitor edge-inference pipelines as more teams publish production numbers comparing pure-edge, hybrid, and cloud-only agent deployments.
