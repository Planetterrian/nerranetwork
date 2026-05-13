# Models & Agents
> **Real-time multimodal agents now run full-duplex perception and generation without external VAD or frozen states.**

**What You Need to Know:** Thinking Machines Lab released TML-Interaction-Small, a 276B MoE model with 12B active parameters that processes 200ms chunks of audio, video, and text in parallel streams. ReVision cuts visual token usage by ~46% for computer-use agents while lifting success rates 3 points on OSWorld and WebTailBench. Builders should test the interaction model prototype in Google AI Studio and the ReVision patch selector on their own CUA trajectories this week.
---
### Top Story
Thinking Machines Lab released a research preview of TML-Interaction-Small, a native multimodal architecture built for continuous human-AI collaboration. The 276B-parameter MoE model activates 12B parameters and ingests synchronized 200ms chunks of audio, video, and text through a multi-stream time-aligned design, removing the need for separate voice-activity detection. A real-time interaction component maintains full-duplex exchange while an asynchronous background model handles sustained reasoning and tool use, both sharing the complete conversation context. This removes the turn-based freeze that limits most current agents and opens practical paths for fluid desktop or voice-first workflows. Teams working on responsive agents should watch how the dual-model split scales when context length and tool complexity increase. Source: [marktechpost.com](https://www.marktechpost.com/2026/05/13/mira-muratis-thinking-machines-lab-introduces-interaction-models-a-native-multimodal-architecture-for-real-time-human-ai-collaboration/)
---
### Model Updates
**HEBATRON: Hebrew-specialized MoE:**
The first open-weight Hebrew-adapted Nemotron-3 MoE activates only 3B parameters per pass inside a 30B model and reaches 73.8% on Hebrew reasoning benchmarks while supporting 65k native context. It outperforms DictaLM-3.0-24B-Thinking and stays competitive with Gemma-3-27B-IT on GSM8K-HE and Israeli Trivia after a three-phase curriculum plus 2M bilingual fine-tuning examples. Developers targeting Semitic-language tasks now have a high-throughput option that delivers roughly 9× inference speed versus dense equivalents. Source: [arxiv.org](https://arxiv.org/abs/2605.11255)

**ReAD capability distillation:**
ReAD uses an uncertainty-aware contextual bandit to allocate a fixed token budget across interdependent capabilities instead of treating them as isolated targets. The method improves downstream utility while cutting harmful spillover compared with standard distillation baselines. Teams compressing models for specific tasks should test the public GitHub implementation before the next round of size reductions. Source: [arxiv.org](https://arxiv.org/abs/2605.11290)

**Bicameral hidden-state coupling:**
Two frozen language models exchange information through a lightweight neural interface on intermediate activations rather than serialized text. On arithmetic and logic tasks the approach lifts accuracy from 36% to 96% and delivers 1.7× gains on ZebraLogic when paired with a Z3 solver. The ~1% added parameters learn a selective protocol from task loss alone, giving a new route for tool-augmented systems that avoid output-vocabulary bottlenecks. Source: [arxiv.org](https://arxiv.org/abs/2605.11167)
---
### Agent & Tool Developments
**ReVision for computer-use agents:**
ReVision trains multimodal models on trajectories where a learned patch selector drops redundant visual patches across consecutive screenshots while preserving spatial structure. When applied to Qwen2.5-VL-7B with five history frames it reduces token count ~46% on average and raises success rate 3 points on OSWorld, WebTailBench, and AgentNetBench. Agent builders can now keep longer visual histories under the same context budget; the patch selector code is the immediate item to integrate. Source: [arxiv.org](https://arxiv.org/abs/2605.11212)

**SAP Autonomous Enterprise Platform:**
SAP launched an enterprise platform centered on Joule agents and an expanded partner ecosystem for autonomous workflows. The release packages agent operations with existing SAP data and process layers, targeting production-grade automation inside large organizations. Enterprises already on SAP should evaluate the new agent runtime against their current RPA stack this quarter. Source: [Google News](https://news.google.com/rss/articles/CBMisgFBVV95cUxQMG1MRll4LWZkZ0lHZWxGaHRVNHNsUTZOMldsNTJTQmg3Wms5cG9lSk1UNTlJLVhBLVRMVjhxdmx3RWpiS0lSeDJlM1FDXzNYR0RRTkVfYW0tcUhyei15UzJZNnZlSVJkZmJmYWdlUlVSeWNCRnNRMnQ2NWRjdWoxcFg1V21JaHVGVkZXcVduVm1tUHNzN2JPei1Ga2ZvRDdwSndnamdjeEp3ZVFsVTZFMk5B?oc=5)

**Red Hat AI Platform 3.4:**
Version 3.4 adds dedicated agent operations and Model-as-a-Service capabilities to the Red Hat AI platform. The update supplies managed runtimes for agent orchestration and model serving inside existing OpenShift environments. Teams running containerized AI workloads can now deploy agents without separate infrastructure stacks. Source: [Google News](https://news.google.com/rss/articles/CBMirgFBVV95cUxPdGtQS196blpPUEY2WE9INHFpQ29vQmdmSkl6WTBFUnc0d1QxMThTUTRWYjZfQWppS1ZjZF9ySTRjZXFkZUV6WWZBZ1JrOU1aLUN6OFZlTWQ4al95Vk5YaWtmT25yTER6X05kd2lQWXd6R0xhNjEzTFA5RGVVOE0zYmxwZFZLM2pGZHdMejdrUVA3bDJLdlBFZjQtTVprRFdDSFdEbkxZUEhNRTNvUGc?oc=5)
---
### Practical & Community
**KGC 2026 production knowledge-graph decks:**
A Reddit user shared the full set of decks from this year’s Knowledge Graph Conference, highlighting live enterprise systems from Bloomberg, AbbVie, and Morgan Stanley that treat graphs as reasoning infrastructure rather than vector retrieval layers. The collection shows concrete SHACL drift detection, ontology governance, and LLM companions grounded in the graph as source of truth. Anyone building retrieval-augmented agents should review the AbbVie ARCH example for patterns that move beyond simple RAG. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1tbt6wl/sharing_all_kgc_2026_decks_more_productiongrade/)

**Local VLMs for desktop GUI automation:**
r/LocalLLaMA users are testing quantized vision-language models on Apple Silicon to drive GUI actions from screenshots, noting that small icons and dense interfaces remain difficult while visual token counts quickly throttle prefill speed. Early experiments show basic navigation works; the thread collects model choices and token-budget workarounds. Developers targeting on-device agents should join the discussion before scaling to production. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tbsojv/has_anyone_tried_local_vlms_for_desktop_gui/)

**BeeLlama.cpp fork for constrained hardware:**
A maintained fork adds DFlash and TurboQuant features plus reasoning and vision support, enabling Qwen 3.6 27B Q5 at 200k context on a 3090 at 2–3× baseline speed. Users with 8 GB VRAM laptops are already running agentic coding loops; the creator’s linked thread contains command examples and performance numbers. Anyone limited to modest GPUs should benchmark the fork before the features land in mainline llama.cpp. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tbshsl/how_many_of_you_tried_beellamacpp_hows_it_agentic/)
---
### Under the Hood: Diversity Collapse in LLM Decoding
Everyone treats sampling temperature or top-p as simple knobs that control variety. In practice the root cause sits inside the model’s probability distribution before any sampling rule is applied. Order miscalibration means valid tokens are not consistently ranked above invalid ones, forcing any cutoff to trade recall for noise. Shape miscalibration concentrates mass on a few high-probability valid tokens while a long tail mixes valid and invalid continuations, so preserving validity automatically starves diversity. These local failures compound across steps, turning modest per-token bias into large sequence-level repetition. The paper’s controlled diagnostics show the effect persists across 14 models and is not fixed by changing the sampler alone. When you need genuine variety, first measure rank and shape calibration on your domain rather than tuning sampling parameters in isolation; the cheapest win is usually fixing the distribution before you touch the decoder.
---
### Things to Try This Week
- Test the TML-Interaction-Small prototype inside Google AI Studio for any voice-plus-screen workflow where continuous perception matters.
- Apply the ReVision patch selector to your existing computer-use agent trajectories and measure token savings versus success-rate lift on OSWorld-style tasks.
- Run BeeLlama.cpp on an 8 GB laptop with Qwen 3.6 27B Q5 to see whether agentic coding loops become usable before the next mainline release.
- Download the KGC 2026 deck folder and study the AbbVie ARCH graph architecture if your RAG system still treats the vector store as the only source of truth.
- Compare HEBATRON against Gemma-3-27B-IT on any Hebrew or bilingual reasoning benchmark you maintain.
---
### On the Horizon
- More labs are expected to release native full-duplex multimodal models following the Thinking Machines pattern.
- Production knowledge-graph tooling will continue moving from retrieval layer to primary reasoning substrate in enterprise settings.
- Open-weight MoE adaptations for additional languages will likely appear now that the Nemotron-3 Hebrew precedent exists.
- Agent identity registries and verification prototypes from infrastructure providers will move from research to early commercial pilots.