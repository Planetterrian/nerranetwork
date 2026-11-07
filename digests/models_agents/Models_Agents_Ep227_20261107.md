# Models & Agents
> **Ling-3.2-flash ships a 560B/25B multimodal MoE with 1M context and OpenAI-compatible APIs for immediate use.**

**What You Need to Know:** Ant Ling released Ling-3.2-flash, a native multimodal mixture-of-experts model supporting text, image, and video with a 1M-token window. Buoyant open-sourced Kinference, a Kubernetes control plane that adds KV-cache-aware routing and policy enforcement on top of vLLM. Anthropic detailed how offline “dreaming” on interaction logs improves agent memory organization, while OpenAI introduced BioBasicsBench to test agents on routine wet-lab data interpretation.
---
### Top Story
Ant Ling released Ling-3.2-flash, a native multimodal MoE with 560B total parameters and 25B activated parameters plus a 1M-token context window. The model accepts text, image, and video inputs and reports results on MathVision, Humanity’s Last Exam-MM, ZEROBench, OmniDocBench, and several domain-specific suites including MedXpertQA-MM and AndroidWorld. Both OpenAI-compatible and Anthropic-compatible API endpoints are documented, along with demonstrations of PDF-to-code, GUI operation, 3D reconstruction, and multi-agent workflows. Developers can now route long-context multimodal workloads through familiar chat completions interfaces without managing separate vision or video pipelines. Watch for expanded access tiers and any follow-on fine-tunes targeting specific verticals. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1xpye7g/ant_ling_introduces_ling32flash_560b25b_native/)
---
### Model Updates
**Higgs Realtime Duplex: a 45B MoE full-duplex model that listens, watches and talks at once, and thinks, calls tools and delegates in the background [N]: r/MachineLearning**
Higgs Realtime Duplex processes audio, video, and text in 160 ms chunks while running background thinking and tool calls in the same stream. The 45B model uses causal flow-matching for audio and a DiT for face output, with zero-shot voice and face reference at deployment. It trails OpenAI’s best on several full-duplex and proactive-video benchmarks but leads on Big Bench Audio and IFEval in the published comparison set. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1xpn5pv/higgs_realtime_duplex_a_45b_moe_fullduplex_model/)

**FIA-LLM: feedback conditioned learning state estimation with large language models: Nature**
FIA-LLM produces a Self-Determination Theory-grounded learning-state surrogate, next-item achievement prediction, SDT dimension label, and diagnostic explanation from shared representations. The dual-stream framework uses Confidence-Aware Robust Distillation on 2,000 human annotations plus LLM pseudo-labels and Feedback Intervention Attention to fuse feedback proxies with behavioral history. On frozen expert test sets it reduces macro-average RMSE by 8.6 % and lifts macro-average AUC by 1.2 points. Source: [nature.com](https://www.nature.com/articles/s41598-026-74388-5)
---
### Agent & Tool Developments
**Buoyant Releases Kinference: An Open Source Inference Control Plane for Kubernetes and vLLM: MarkTechPost**
Kinference is an Apache 2.0 inference control plane that sits in front of vLLM workers on Kubernetes and applies declarative routing policies, KV-cache-aware load balancing, token rate limits, and per-tenant metrics. The v0.1.0-alpha.7 release is written in Rust, configured through five CRDs, and ships with a gRPC inference handler. In Buoyant’s three-L40S-GPU benchmark, median TTFT on shared-prefix workloads dropped from 6.88 s to 0.31 s. Source: [marktechpost.com](https://www.marktechpost.com/2026/11/07/buoyant-kinference-open-source-inference-control-plane-kubernetes-vllm/)

**Claude's Memory: How "Dreaming" Improves Learning: [@AnthropicAI](https://x.com/AnthropicAI) [preferred primary source]**
Anthropic describes how offline “dreaming” on agent logs lets Claude reorganize experience, correct mistakes, and surface relevant notes for future sessions without weight updates or in-context learning. The approach mirrors hippocampal replay during sleep and is positioned as a complement to compaction and context-window management. Evaluations isolate the contribution of dreaming to memory organization across multiple agent tasks. Source: [anthropic.com](https://www.anthropic.com/research/components-of-agent-memory)

**OpenAI introduces BioBasicsBench for AI in wet-lab science: [@OpenAI](https://x.com/OpenAI) (X)**
BioBasicsBench comprises 100 tasks drawn from real enzyme-design experiments at Ligo to test whether agents can interpret raw lab data, flag errors, and recognize unsupported conclusions. The benchmark targets routine wet-lab analyses rather than novel discovery and is intended to track progress on scientific reliability and biosafety. Source: [x.com](https://x.com/OpenAI/status/2118782708767965238)

**ToyBlocks: A controlled world for robot learning and evaluation: Hugging Face Blog [preferred primary source]**
ToyBlocks supplies a simulated tabletop environment with a robot arm and blocks plus automatic task and demonstration generation for studying how models improve with more data and how high-level reasoning combines with physical control. The framework records robot trajectories without teleoperation and supplies metrics for behavior over time, serving as the first FoundationWorld in a planned series of controlled robotics domains. Source: [huggingface.co](https://huggingface.co/blog/allenai/toyblocks)
---
### Practical & Community
**Build Your First Multi-Tool AI Agent with Ollama and Python: Towards Data Science**
The tutorial walks through an agent that selects among three database tools, routes on tool results, and stops after eight turns via a circuit breaker, all running locally with Ollama. It demonstrates tool-use loops and state management without external APIs beyond the local model server. Source: [towardsdatascience.com](https://towardsdatascience.com/build-your-first-multi-tool-ai-agent-with-ollama-and-python/)

**Give Your Python AI Agent Persistent Memory with One JSON File: Towards Data Science**
Three Python classes plus an OpenRouter key and gpt-4.1-mini give an agent a calculator, stub web search, and conversation recall that survives process restarts via a single JSON file. The pattern replaces external vector stores for lightweight, restart-safe memory in small agents. Source: [towardsdatascience.com](https://towardsdatascience.com/give-your-python-ai-agent-persistent-memory-with-one-json-file/)
---
### Also Today
**Researchers Establish Rigorous Evaluation Criteria for Artificial Intelligence in Carbon Accounting: Bioengineer.org**
The article outlines new evaluation criteria for AI systems used in carbon accounting, extending prior work on model assessment in that domain. Source: [bioengineer.org](https://bioengineer.org/researchers-establish-rigorous-evaluation-criteria-for-artificial-intelligence-in-carbon-accounting/)

**Israelis in emotional distress are turning to ChatGPT for help, study finds: The Jerusalem Post**
A study finds Israeli users in emotional distress are using consumer ChatGPT instances despite the absence of clinical safeguards or mandates. Source: [jpost.com](https://www.jpost.com/health-and-wellness/mind-and-spirit/article-913917)

**Microsoft AI CEO Mustafa Suleyman reacts to Delaware’s AI agent proposal, says it is ‘deeply concerning t: The Times of India**
Microsoft AI’s CEO called Delaware’s proposed AI agent rules deeply concerning, highlighting tensions between state-level proposals and industry practice. Source: [timesofindia.indiatimes.com](https://timesofindia.indiatimes.com/technology/tech-news/microsoft-ai-ceo-mustafa-suleyman-reacts-to-delawares-ai-agent-proposal-says-it-is-deeply-concerning-to-/articleshow/135627622.cms)

**OpenAI partners on cyber jailbreak framework with FMF: [@OpenAI](https://x.com/OpenAI) (X)**
OpenAI and FMF member firms released a framework for classifying cyber jailbreaks by severity and the capabilities they unlock, aiming to standardize evaluation across labs. Source: [x.com](https://x.com/OpenAI/status/2118795218099253606)

**Beyond code generation: A developer’s guide to agentic engineering: GitHub Blog**
The guide covers planning, code review, change investigation, and production debugging workflows with GitHub Copilot while noting where human judgment remains essential. Source: [github.blog](https://github.blog/ai-and-ml/github-copilot/beyond-code-generation-a-developers-guide-to-agentic-engineering/)

**OpenAI Launches GPT-6 Cyber After AI Helps Find 81 Firefox Flaws, 948 Linux Exploits: The Hacker News**
OpenAI’s GPT-6 Cyber model discovered 81 high-severity Firefox vulnerabilities and developed working exploits for 948 Linux kernel flaws during internal testing. Source: [thehackernews.com](https://thehackernews.com/2026/11/openai-launches-gpt-6-cyber-after-ai.html)
---
---
### Things to Try This Week
- Route a shared-prefix workload through Kinference on a small Kubernetes cluster to measure TTFT reduction before committing production traffic.
- Test Ling-3.2-flash’s 1M context on a long multimodal document task using the documented OpenAI-compatible endpoint.
- Run the ToyBlocks simulation locally to generate robot trajectories and compare policy performance across increasing demonstration counts.
- Add the three-class JSON memory pattern from the Towards Data Science tutorial to an existing Ollama agent to check restart persistence without a vector database.
- Evaluate an agent on BioBasicsBench’s 100 wet-lab tasks to see where interpretation errors cluster before deploying in scientific workflows.
---
### On the Horizon
- Expanded Daybreak Red access for GPT-6 Cyber customers is expected in the coming weeks.
- Further FoundationWorld environments beyond ToyBlocks are planned by the AllenAI and Hugging Face collaboration.
- Anthropic’s engineering blog series on agent memory components will continue with additional evaluation results.
- Delaware’s AI agent proposal is still under review; industry comments are being collected.
