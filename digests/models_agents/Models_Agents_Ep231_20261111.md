# Models & Agents
> **A new 0.8B on-device model doubles agentic benchmark scores while keeping all data private.**

**What You Need to Know:** Tether AI released BotPsy, an 0.8B model fine-tuned from Qwen3.5-0.8B for function calling and agentic tasks across web, travel, finance, and device control. It roughly doubles performance on BFCL v4, ACEBench, and τ-bench compared with its base while running entirely locally. TimeOmni-o1 pairs a time-series foundation model with an LLM for joint reasoning and forecasting, and several Google and OpenAI product updates expand agent access for businesses and healthcare.
---
### Top Story
Tether AI Research released BotPsy, a 0.8B-parameter model built on Qwen3.5-0.8B for on-device function calling and agentic workflows. The model supports tools in web search, travel, commerce, device control, files, calendar, and messaging, targeting low-to-medium difficulty tasks. It achieves state-of-the-art tool-use results for its size, lifting BFCL v4 from 23.4 to 44.0, ACEBench from 30.1 to 58.7, and τ-bench from 23.2 to 51.5. BotPsy runs locally with no third-party API calls, addressing privacy and cost concerns of frontier cloud models. Builders working on personal assistants or edge deployments can test the model now on Hugging Face. The release includes explicit intended-use and limitations guidance noting it is not suited for high-stakes decisions. Source: [huggingface.co](https://huggingface.co/blog/qvac/botpsy)
---
### Model Updates
**TimeOmni-o1 couples time-series foundation models with LLMs for joint reasoning and forecasting: arXiv NLP**
The architecture encodes time series into compressed form for the LLM, then feeds LLM reasoning back to the time-series model for forecasting. It was trained on the new MMTR dataset of 500k+ multimodal samples across 12 domains and outperforms both standalone LLMs and time-series models on understanding and forecasting tasks. Gains transfer to three open benchmarks. Source: [arxiv.org](https://arxiv.org/abs/2611.12902)

**One Byte, One Token converts a 27B hybrid-attention model to pure byte-level inference: arXiv NLP**
The conversion shrinks the vocabulary to 384 entries and continues training on 4.77 GB of self-generated dialogue and encyclopedia data for 178.6 hours on 8xH200. The resulting model matches the original on MATH-500, HumanEval+, and MMLU-Pro while improving character-level tasks, at the cost of 3-5x lower token throughput. Source: [arxiv.org](https://arxiv.org/abs/2611.13607)

**Mobile AI Factory searches and quantizes task-specific small language models for target Android phones: arXiv NLP**
The agentic system tests base models and quantizations against real device measurements, rolling back changes that hurt accuracy. On ten tasks across four phones the resulting on-device models beat five-shot frontier models on five tasks and match them on three more, using 19x less GPU time than exhaustive search. Source: [arxiv.org](https://arxiv.org/abs/2611.13509)

**khammoon delivers a 1M-parameter morpheme segmenter for Thai with 0.992 boundary F1: arXiv NLP**
The model operates at the morphological level rather than word level to avoid compounding ambiguity. It was trained on guidelines with near-perfect human agreement and scales annotation via LLM plus human correction. Downstream models trained on its morpheme output match or exceed word-level baselines on POS tagging, NER, and sentiment classification. Source: [arxiv.org](https://arxiv.org/abs/2611.13012)

**Capacity Allocation uses ℓ1 regularization on target hidden states to reduce interference during LLM knowledge editing: arXiv NLP**
The method prunes unnecessary components of each knowledge vector before the parameter edit step. Experiments across multiple LLMs and benchmarks show fewer side effects on unrelated knowledge while preserving edit success. Source: [arxiv.org](https://arxiv.org/abs/2611.12995)

**BioMem introduces Hybrid Memory Retrieval and Utilization for biomedical LLM agents: arXiv NLP**
The training-free framework improves evidence accessibility and task-aware utilization across five memory approaches and four LLMs. It delivers an 8.6% relative gain on biomedical QA and conversational memory benchmarks and cuts conversational answer errors by 24.9%. Source: [arxiv.org](https://arxiv.org/abs/2611.13426)
---
### Agent & Tool Developments
**Synapse-Control selects and times advice for agent experience reuse with a 1.7B classifier: arXiv NLP**
The runtime uses rules to shortlist advice and a lightweight classifier to score candidates instead of calling a generative model for diagnosis. Across 1,308 attempts on AppWorld and WebShop it achieves 29.8% more successes than the base agent while replacing 4,987 generative diagnosis calls and halving auxiliary control time. Source: [arxiv.org](https://arxiv.org/abs/2611.13615)

**OpticalRAG renders documents as images and distills visual tokens to 16 injected tokens for RAG: arXiv NLP**
The system uses Encoder-Bridged Retrieval and Query-Driven Distillation without cross-modal training. On LongBench-v2, BAMBOO, and LooGLE-v2 it records the best compression-aware accuracy while adding only 16 tokens and lifting a Qwen2.5-7B-Instruct backbone by 5.17 points on LongBench-v2. Source: [arxiv.org](https://arxiv.org/abs/2611.13675)

**PolyRoute provides a 12-language and code-mixed benchmark for typed-decision routing with 13 system baselines: arXiv NLP**
The dataset contains 322 native messages, 156 code-mixed items, and optional training rows across 12 languages and 9 scripts. The best fine-tune reaches 96.6% accuracy; TF-IDF with logistic regression hits 91.9%. Source: [arxiv.org](https://arxiv.org/abs/2611.13843)

**Program-Aided Patchable Skill Evolution stores reusable procedural logic in editable programs rather than natural-language documents: arXiv NLP**
PASE separates trajectory-derived experience into executable programs that can be patched without rewriting descriptive text. It improves success rates by more than 2.8% over prior skill-evolution baselines and shows greater evolutionary stability across models and benchmarks. Source: [arxiv.org](https://arxiv.org/abs/2611.14019)
---
### Practical & Community
**Businesses in ChatGPT now in beta with Business Agents and engagement insights: [@OpenAI](https://x.com/OpenAI)**
Eligible businesses can claim their profile, manage information, and receive data on how people interact with them. They can also build a Business Agent to answer customer questions and surface offerings. Source: [openai.com](https://openai.com/index/introducing-businesses-chatgpt/)

**Gemini for healthcare unifies clinical data and automates workflows on Google Cloud: Google AI Blog**
The offering targets administrative burnout by connecting records and streamlining processes. Early users can explore the new clinical capabilities in the Google Cloud console. Source: [blog.google](https://blog.google/innovation-and-ai/infrastructure-and-cloud/google-cloud/gemini-for-healthcare/)

**Adobe creative and productivity tools integrate directly with Google apps and Gemini: Google AI Blog**
Users can edit PDFs in Drive and access Adobe AI features inside Gemini. The partnership brings familiar creative tooling into everyday Google workflows. Source: [blog.google](https://blog.google/company-news/inside-google/company-announcements/adobe-google-partnership-integration/)

**OpenAI Academy expands free ChatGPT workshops to caregivers in five U.S. cities: OpenAI Blog**
The hands-on sessions focus on practical everyday uses of AI. Registration details are available on the OpenAI site for participants in the selected cities. Source: [openai.com](https://openai.com/index/helping-caregivers-use-ai-in-everyday-life/)

**Anthropic begins its IPO roadshow with a filed S-1 registration statement: [@AnthropicAI](https://x.com/AnthropicAI)**
The company is conducting investor meetings ahead of a potential public offering. Securities may not be sold until the registration statement becomes effective. Source: [anthropic.com](https://www.anthropic.com/news/roadshow-launch)
---
### Also Today
**Actionable Feedback filters clinician edits on clinical documentation to avoid teaching hallucination: arXiv NLP** — A taxonomy of editing behaviors plus filtering methods lets models improve on alignment metrics while staying faithful to input context. Source: [arxiv.org](https://arxiv.org/abs/2611.12904)

**SELD detects silent evidence loss in context compression even when the final answer stays unchanged: arXiv NLP** — The label-free detector compares reader-model preferences before and after compression and identifies the evidence-removing edit in 83% of matched pairs. Source: [arxiv.org](https://arxiv.org/abs/2611.12903)

**Deletion Sensitivity varies by 55.7 points across seven open reasoning models when full history is stripped in multi-turn tool sessions: arXiv NLP** — The effect is a stable model-level property measurable with two runs. Source: [arxiv.org](https://arxiv.org/abs/2611.13223)

**An evidence-traceable benchmark links every medical claim to a versioned source-text span across guideline, scenario, and real-world levels: arXiv NLP** — Ten LLMs show guideline recall does not guarantee patient-specific evidence use. Source: [arxiv.org](https://arxiv.org/abs/2611.13562)

**One Sequence Is Enough fingerprints 51 language models from a single fixed-length integer sequence with 92.72% closed-set accuracy: arXiv NLP** — Adding a second and fourth answer raises accuracy to 96.06% and 97.12%. Source: [arxiv.org](https://arxiv.org/abs/2611.14010)

**MISO-BR releases an open, balanced 896-item corpus for misogyny detection in Brazilian Portuguese with Fleiss' κ of 0.788: arXiv NLP** — Fine-tuned BERTimbau reaches 0.833 macro-F1; classical baselines cluster around 0.66. Source: [arxiv.org](https://arxiv.org/abs/2611.14036)

**HandsOnAid fine-tunes a 4-bit Gemma 2B model on 5,550 first-aid QA pairs and scores 2.51/5 on medically reviewed references: arXiv NLP** — Retrieval-augmented version produces first text in 6.86 seconds on a Pixel 7 Pro with no network. Source: [arxiv.org](https://arxiv.org/abs/2611.14059)

**Stagewise emergence of inside-outside computation appears in Transformers trained on synthetic context-free grammars with variable parse trees: arXiv NLP** — Early layers handle local bigram information; later layers refine predictions around an abstract latent tree encoded in the middle layers. Source: [arxiv.org](https://arxiv.org/abs/2611.14221)

**Representational Atoms can be recovered by threshold-activated sparse autoencoders with high fidelity and stability when conditions are met: arXiv NLP** — Stable atoms show greater monosemanticity and compose across layers to match human conceptual structure. Source: [arxiv.org](https://arxiv.org/abs/2611.14168)
---
---
### Things to Try This Week
- Deploy BotPsy on a local device for private personal-assistant tasks and compare its tool-use reliability against larger cloud agents on your own workflow.
- Test TimeOmni-o1 on a multimodal time-series forecasting problem if you combine numeric sensor data with event text.
- Run the Mobile AI Factory pipeline on one of your mobile apps to see how device-specific quantization changes accuracy versus a generic small model.
- Try the byte-level 27B model on a Chinese or code-heavy task where character or token integrity has previously been a bottleneck.
- Explore OpticalRAG if your RAG pipeline handles long PDFs and you want to keep token counts under 20 while preserving layout information.
---
### On the Horizon
- OpenAI Business Agents move from beta to wider availability with more enterprise controls expected in the coming weeks.
- Google continues rolling Gemini Intelligence features to additional Android devices and Workspace apps.
- Anthropic investor meetings continue through the IPO roadshow period.
- More details on Gemini 4 Carbon pricing and availability in Google Cloud are scheduled for release soon.
