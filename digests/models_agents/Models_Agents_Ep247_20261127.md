# Models & Agents
> **India's Chariot-1 11B model cuts Indian-text tokens by 2.5x while running on phones.**

**What You Need to Know:** Chariot AI released the Chariot-1 suite—an 11B-parameter mixture-of-experts LLM and a context-aware TTS model supporting English plus ten Indian languages—under the IndiaAI Mission. The models were trained from scratch in India with IndicShift tokenization and nested training techniques that delivered measurable efficiency gains. Builders working on Indic-language applications or edge deployments should test the three available sizes this week.
---
### Top Story
Chariot Artificial Intelligence Pvt. Ltd. launched the Chariot-1 foundation model suite on 26 November at Bharat Mandapam in New Delhi. MeitY Secretary S. Krishnan performed the launch under the IndiaAI Mission, making Chariot one of the first four teams selected for sovereign foundation-model development. The suite pairs an 11-billion-parameter mixture-of-experts LLM with four billion active parameters per token and a text-to-speech system, both pre-trained from scratch in India. Three sizes—10.7 billion, 1.7 billion, and 745 million parameters—are provided for data-center, laptop, and smartphone deployment. The TTS model supports English and ten Indian languages—Hindi, Bengali, Marathi, Tamil, Telugu, Kannada, Malayalam, Gujarati, Punjabi, and Odia—while determining context-aware pronunciation for numbers, dates, currencies, URLs, and abbreviations, achieving over 97 percent verbalisation accuracy on the Async TTS Pronunciation Benchmark. IndicShift tokenization, covering 1,012 characters across 12 Indian scripts, delivers up to 2.5 times fewer tokens on Indian text than OpenAI’s GPT tokenizer. Nested training techniques produced a 38 percent improvement in training speed on the same GPUs with negligible change in model loss; a separate reported approach reached 62 percent faster training. Co-founder Parth Sarthi stated that a nation of India’s scale and diversity cannot depend on AI built elsewhere. The company is already developing a 70-billion-parameter model and holds longer-term ambitions for a trillion-parameter system. Developers building Indic-language or on-device applications should download the three available sizes and benchmark token efficiency against existing tokenizers. Source: [wocult.com](https://www.wocult.com/news/indiaai-mission-chariot-1-foundation-models-india)
---
### Model Updates
**Sakana AI Releases Namazu Small, a 30B Model Built on Nemotron 3 Nano: MarkTechPost**
Sakana AI released Sakana Namazu Small, a 30B-A3B reasoning model built on NVIDIA Nemotron 3 Nano. It averages 60.1 across 25 benchmarks, ahead of the 120B Nemotron 3 Super at 56.2. The model demonstrates that a smaller active-parameter count can outperform a much larger dense counterpart on aggregate reasoning tasks. Source: [marktechpost.com](https://www.marktechpost.com/2026/11/26/sakana-ai-namazu-small-30b-nemotron-3-nano/)

**Tencent Open-Sources DFly2: Speculative Decoding That Reuses the Target’s Sparse KV Cache: MarkTechPost**
Tencent open-sourced DFly2, a speculative decoding drafter for sparse-attention LLMs. Each draft layer reuses the target’s KV cache and top-k indexer picks, adding no draft KV memory. The approach lifts 64K serving throughput by up to 81 percent. Because the drafter shares the target’s cache, memory overhead remains zero while still accelerating generation on long contexts. Source: [marktechpost.com](https://www.marktechpost.com/2026/11/26/tencent-dfly2-speculative-decoding-sparse-models/)

**Russian AI model fills void in unfinished Gogol novel. Not everyone is happy: Reuters**
A Russian AI model completed an unfinished Gogol novel, drawing mixed reactions from literary observers. The project highlights both the capability of current models to continue classic literary works and the cultural sensitivities that arise when AI intervenes in national literary heritage. Source: [reuters.com](https://www.reuters.com/technology/russian-ai-model-fills-void-unfinished-gogol-novel-not-everyone-is-happy-2026-11-27/)

**Stable Gated DeltaNet-2: Understanding and Mitigating Recurrent State Instability: arXiv NLP**
Researchers introduced Stable Gated DeltaNet-2, which uses symmetric erasure and decay-regulated residual writing to bound recurrent state growth at O(√T). On approximately 1.6B parameter models the method raised the 128K average RULER score by 6.80 points in the recurrent setting and average accuracy across nine downstream tasks by 0.62 points in the hybrid setting. The fix addresses exponential state growth caused by asymmetric erase operators in the original Gated DeltaNet-2 design. Source: [arxiv.org](https://arxiv.org/abs/2611.34051)

**Lightweight Reasoning Transfer via Chain-of-Thought Vector Projection: arXiv NLP**
A two-stage projected cross-model Chain-of-Thought vector transfer method improved base student models by 10.37-21.98 accuracy points on GSM8K and MATH and by 3.23-9.65 pass@1 points on four code-generation benchmarks while keeping both teacher and student frozen. The approach first learns a task-level CoT vector in the teacher, then trains only a lightweight linear projector to map it into the student’s residual space. No teacher outputs or intermediate traces are required during student adaptation. Source: [arxiv.org](https://arxiv.org/abs/2611.34183)
---
### Agent & Tool Developments
**LaunchDarkly Orchestrates Parallel AI Agents in Cloud Sandboxes to Drive 44 Code Changes: Howl.Link**
LaunchDarkly demonstrated parallel AI agents running in cloud sandboxes that produced 44 code changes. The setup isolates agent execution while still allowing measurable productivity gains on real engineering tasks. Source: [t.co](https://t.co/cTdoZCh4E8)

**EACON announces significant ORCASTRA upgrades plus new mining AI agent: International Mining**
EACON announced ORCASTRA upgrades together with a new mining AI agent. The agent targets autonomous operation of heavy equipment in mining environments, extending the platform’s existing orchestration capabilities. Source: [im-mining.com](https://im-mining.com/2026/11/27/eacon-announces-significant-orcastra-upgrades-plus-new-mining-ai-agent/)

**Metano Emerges from Stealth with $12M Seed to Secure Autonomous AI Agents: FF News**
Metano emerged from stealth with a $12M seed round to unify AI agent security across the enterprise. The funding targets consistent policy enforcement and runtime controls for agents operating inside corporate environments. Source: [ffnews.com](https://ffnews.com/news/metano-emerges-from-stealth-to-unify-ai-agent-security-across-the-enterprise-c03bf277)

**Valory Unveils Onchainbench to Test How Safely and Reliably AI Agents Use Crypto Wallets: HackerNoon**
Valory released Onchainbench, a benchmark for measuring how safely and reliably AI agents interact with crypto wallets. The suite evaluates wallet operations under realistic threat models and provides standardized scoring for agentic financial actions. Source: [hackernoon.com](https://hackernoon.com/valory-unveils-onchainbench-to-test-how-safely-and-reliably-ai-agents-use-crypto-wallets)

**Japan's Amada and Hitachi Push Toward Autonomous Factories With AI Agents, Targeting Equipment and Robot Control: BigGo Finance**
Amada and Hitachi are developing AI agents aimed at autonomous control of factory equipment and robots. The collaboration focuses on real-time decision loops for industrial machinery without constant human oversight. Source: [finance.biggo.com](https://finance.biggo.com/news/0ee2dee9-8116-4894-a452-855cabe93ec2)
---
### Practical & Community
**AI agents need tool response validation for safety: TechGig**
Developers are advised to add explicit validation of tool responses to prevent unsafe agent behavior. Without validation, agents can act on malformed or malicious tool outputs, creating downstream security and correctness risks. Source: [techgig.com](https://techgig.com/news/ai/ai-agents-need-tool-response-validation-for-safety/136206704)

**Puzzling-Bench: Evaluating Language Models on 23,777 Human-Written Puzzles with Community-Verified Answers: arXiv NLP**
Puzzling-Bench supplies 23,777 community-verified puzzles, including a rolling post-cutoff slice and a multimodal pilot, for contamination-resistant evaluation of frontier models. Every puzzle carries the author-accepted answer, short reference answer, author hints, community tags, and creation date. Source: [arxiv.org](https://arxiv.org/abs/2611.34331)

**MINE: A Training-Free Defense against Indirect Prompt Injection via Mutual Information and Embedding Variance: arXiv NLP**
MINE offers a training-free, attack-agnostic defense that reranks retrieved content by mutual information and embedding variance; it leads accuracy-security trade-offs on Inj-SQuAD, Inj-TriviaQA, LC-Inj-SQuAD, and InjecAgent while adding the lowest latency on long contexts. The method was evaluated on a new long-context benchmark averaging 4,032 words per context. Source: [arxiv.org](https://arxiv.org/abs/2611.34188)
---
### Also Today
**Small AI Models Give Banks a Way to Keep Sensitive Data In-House: PYMNTS.com**
Smaller on-premise models let banks retain sensitive data without sending it to external providers. The approach reduces regulatory exposure while still delivering useful inference capabilities inside controlled environments. Source: [pymnts.com](https://www.pymnts.com/news/artificial-intelligence/2026/small-ai-models-give-banks-a-way-to-keep-sensitive-data-in-house/)

**ChatGPT Stock Picks Outperform S&P 500 With 22% Gain: Chosun**
ChatGPT-generated stock selections delivered a 22 percent gain, beating the S&P 500. The result illustrates both the appeal and the limitations of using general-purpose models for financial decision support. Source: [chosun.com](https://www.chosun.com/english/market-money-en/2026/11/27/VCWPUAYMDJC4NPGG425TNLSMAI/)

**OpenAI’s GPT‑6.2 correction means you get less AI for the same fee: InfoWorld**
OpenAI adjusted GPT-6.2 output limits, reducing tokens delivered at the existing price point. Customers now receive fewer generated tokens per request without any change in subscription cost. Source: [infoworld.com](https://www.infoworld.com/article/4253883/openais-gpt%E2%80%916-2-correction-means-you-get-less-ai-for-the-same-fee.html)

**From Data Room to Report: End-to-End AI Support for M&A Legal Due Diligence: arXiv NLP**
LEXI demonstrates an LLM workflow that ingests virtual data room documents, extracts due-diligence information with provenance, and prepares report sections while keeping final legal judgment with lawyers. The system classifies documents under a configurable taxonomy, assigns target entities, and surfaces supporting passages with page-level citations. Source: [arxiv.org](https://arxiv.org/abs/2611.34120)

**IRTIQA: Evolving in English, Evaluated in Urdu -- Does Agent Self-Evolution Transfer from English to Urdu and Code-Switched Input?: arXiv NLP**
Self-evolution frameworks improve goal completion on AppWorld and SkillsBench yet leave persistent gaps between English and Urdu or code-switched performance, with the largest shortfalls on multi-step tasks. The IRTIQA benchmark supplies aligned English, Urdu-translated, and code-switched variants of four existing datasets with human verification. Source: [arxiv.org](https://arxiv.org/abs/2611.34303)
---
---
### Things to Try This Week
- Download the three Chariot-1 sizes and measure token counts on Hindi or Tamil text against your current tokenizer.
- Run Sakana Namazu Small on the 25-benchmark suite you already use and compare against Nemotron 3 Super.
- Add MINE’s mutual-information reranker to an existing RAG pipeline and test on LC-Inj-SQuAD-style long contexts.
- Evaluate LaunchDarkly’s parallel agent sandboxing on a small internal code-change workflow.
- Benchmark Valory Onchainbench against your current crypto-wallet agent test suite.
---
### On the Horizon
- Chariot AI plans a 70B follow-up model under the IndiaAI Mission.
- Sakana AI is expected to release additional sizes in the Namazu family.
- More European CSIRTs are scheduled to publish guidance on autonomous attack agents.
- Additional IndiaAI Mission-backed foundation models from Sarvam, BharatGen, and Gnani are slated for public release.
