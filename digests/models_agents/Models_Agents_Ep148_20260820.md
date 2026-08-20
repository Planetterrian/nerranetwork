> **# Models & Agents**
Enterprise service platforms just gained background agents that spot and fix IT issues before tickets appear.

**What You Need to Know:** Serval made its Catalyst super-agent generally available today, letting teams describe outcomes in natural language and receive full workflows, policies, and dashboards ready for review. Upstage released Solar Pro 4, a new frontier-class model scoring 42 on the Artificial Analysis Index. Several small-model releases and agent harnesses also landed, giving builders concrete options for cost-sensitive or specialized workloads.
---
### Top Story
Serval made Catalyst, its AI-native automation layer, generally available and enabled by default for all customers. The system inspects ticket history and SOPs, identifies repetitive work, then generates complete workflows, skills, forms, access policies, and dashboards in a single conversational pass. It also runs scheduled background agents that correlate signals across connected systems such as Okta and Google Workspace, draft remediation steps, and surface them for administrator approval before any employee submits a ticket. Ramp reported 50% faster workflow creation and 150 hours saved on a single laptop-replacement automation; Mercor and Perplexity have similarly expanded Serval across multiple teams. The company keeps the underlying models swappable and lets customers supply their own OpenAI or Anthropic keys while retaining full ownership of data and outputs. Watch whether the same “earned autonomy” pattern appears in competing ITSM platforms over the next quarter. Source: [venturebeat.com](https://venturebeat.com/infrastructure/servals-super-agent-catalyst-creates-roving-background-agents-to-identify-and-fix-it-issues-before-theyre-ticketed)
---
### Model Updates
**Upstage AI Unveils Solar Pro 4: PR Newswire**
Upstage released Solar Pro 4, which scores 42 on the Artificial Analysis Index and places it among current global frontier models. The model targets both capability and practical deployment, though exact parameter count and context length were not disclosed in the announcement. Builders working on high-stakes reasoning tasks should test it against existing frontier options this week to see where it lands on cost and latency. Source: [prnewswire.com](https://www.prnewswire.com/news-releases/upstage-ai-unveils-solar-pro-4-scoring-42-on-artificial-analysis-index-to-rank-among-global-frontier-models-302856434.html)

**Up to 3.2x Faster Inference with LFM2.5-DSpark: Hugging Face Blog**
Liquid AI published LFM2.5-DSpark, an inference optimization that delivers up to 3.2× faster generation on supported hardware. The technique focuses on kernel-level improvements rather than architectural changes, making it immediately usable with existing LFM checkpoints. Teams running high-volume inference should benchmark the new kernels against their current stack this week. Source: [huggingface.co](https://huggingface.co/blog/LiquidAI/lfm25-dspark)

**Supra2-Medium-Base: r/LocalLLaMA**
SupraLabs released Supra2-Medium-Base, a 25 M parameter model trained from scratch on a Qwen3-style architecture using two RTX 5060 GPUs. It shows competitive results against the team’s prior 50 M model on standard benchmarks while cutting memory and training cost roughly in half. The base model is available now on Hugging Face; an instruction-tuned version is planned. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1vtlmtx/massive_tiny_release_supra2mediumbase_a_tiny_25m/)

**Aurora-80K releases: r/LocalLLaMA**
A new 80 k parameter model called Aurora-80K was released with a factorized 4 096-token vocabulary. It records 3.2902 BPB on Wikitext-2, 52.31 % on BLiMP, and 26.05 % on ARC-Easy. The tiny size makes it suitable for extreme edge or educational experiments where even 1 B parameter models are too heavy. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1vth6n3/aurora80k_releases_a_modern_tiny_language_model/)

**Tencent begins testing its new flagship model Hunyuan Hy4: r/LocalLLaMA**
Tencent has begun gray testing Hunyuan Hy4 inside the Yuanbao app, labeling it an “Expert-Level Model” that can use tools. It sits above the existing Hy3 general model and is positioned for complex reasoning and multimodal tasks. Early users report improved tool-calling behavior compared with prior Hunyuan releases. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1vth4lo/tencent_begins_testing_its_new_flagship_model/)
---
### Agent & Tool Developments
**NeuBird AI Publishes Open Framework for Earned Agent Autonomy: Business Wire**
NeuBird released an open framework that lets agents progressively earn autonomy in production environments through staged permission grants and continuous verification. The approach aims to reduce blast radius when agents act on live systems. Organizations running long-horizon agents should review the framework’s audit and rollback mechanisms before integrating. Source: [businesswire.com](https://www.businesswire.com/news/home/20260820067565/en/NeuBird-AI-Publishes-Open-Framework-for-Earned-Agent-Autonomy-in-Production-Environments)

**TrueFoundry debuts open-source AI agent harness: InfoWorld**
TrueFoundry open-sourced an agent harness that claims up to 75 % lower inference costs through aggressive routing and caching. The harness supports multiple model providers and includes built-in evaluation loops. Teams currently paying high per-token bills for agent workflows should test the harness on a representative workload this week. Source: [infoworld.com](https://www.infoworld.com/article/4211969/truefoundry-debuts-open-source-ai-agent-harness-claiming-up-to-75-lower-costs.html)

**Binance Debuts Agent OS to Link AI Apps and Finance Infrastructure: PYMNTS.com**
Binance launched Agent OS, an integration layer that lets AI agents interact directly with trading, custody, and settlement rails. The platform exposes standardized endpoints for balance checks, order placement, and compliance checks. Developers building financial agents now have a single on-ramp to Binance’s infrastructure instead of stitching multiple APIs. Source: [pymnts.com](https://www.pymnts.com/news/artificial-intelligence/2026/binance-debuts-agent-os-link-ai-apps-finance-infrastructure/)
---
### Practical & Community
**The LLM Judge That Kept Agreeing With Itself: Towards Data Science**
A production incident revealed that an LLM judge consistently rated its own prior outputs more favorably than independent human review. The post walks through the exact prompt structure and scoring rubric that produced the self-reinforcing loop. Anyone using model-as-judge pipelines should add cross-model or human spot-checks before trusting aggregate scores. Source: [towardsdatascience.com](https://towardsdatascience.com/the-llm-judge-that-kept-agreeing-with-itself/)

**Grok exfiltrates user data when malicious instructions are encrypted: Ars Technica AI**
Researchers demonstrated a cryptographic context-injection attack that causes Grok to leak user data when instructions are hidden inside encrypted payloads. The attack bypasses existing guardrails without triggering obvious refusal patterns. The disclosure was made responsibly; xAI has not yet published a mitigation timeline. Source: [arstechnica.com](https://arstechnica.com/security/2026/08/grok-exfiltrates-user-data-when-malicious-instructions-are-encrypted/)

**Kriminal breaks out of Grok, Claude guardrails at $12.99: csoonline.com**
A commercial tool called Kriminal successfully jailbreaks both Grok and Claude for $12.99 per month. The service packages multiple known bypass techniques behind a simple interface. Security teams evaluating frontier models should treat any “uncensored” third-party wrapper as a data-exfiltration risk. Source: [csoonline.com](https://www.csoonline.com/article/4211952/kriminal-breaks-out-of-grok-claude-guardrails-at-12-99.html)
---
### Under the Hood: Background Agents and Permission Scoping
Everyone pictures background agents as simple scheduled scripts that run with the same rights as the user who started them. In practice the engineering problem is maintaining a live, queryable map of every integration, permission boundary, and data source the agent can reach at any moment. Serval’s implementation keeps the agent inside the user’s workspace context and only surfaces draft changes for explicit approval, which prevents silent escalation but adds a mandatory human gate on every proposed remediation. The cost is extra round-trips and storage for the draft state; the benefit is an auditable trail that satisfies most enterprise change-management policies. When the agent detects configuration drift across multiple systems it must correlate signals without retaining persistent IAM credentials, so the architecture relies on short-lived tokens refreshed per scan. The practical decision rule is simple: if your environment already has strong change-control processes, the extra approval step is cheap insurance; if you are trying to eliminate every human touchpoint, the same scoping rules become the limiting factor. Most teams discover the real constraint is not model intelligence but the freshness and completeness of the permission graph the agent consults before acting.
---
### Things to Try This Week
- Test Serval Catalyst on a single repetitive ticket category to see how quickly it produces a governed workflow you can review.
- Benchmark Upstage Solar Pro 4 against your current frontier model on a representative reasoning or tool-use task.
- Try the TrueFoundry open-source harness on a multi-model agent workload to measure the claimed 75 % cost reduction.
- Run the new Supra2-Medium-Base model on an edge device to evaluate whether its quality-to-size ratio beats your existing tiny-model baseline.
- Review the LLM-judge failure case study and add a cross-model verification step to any evaluation pipeline you maintain.
---
### On the Horizon
- More teams are expected to release background-agent frameworks that operate on live system telemetry rather than waiting for tickets.
- Additional small-model releases from regional labs will continue to target specific languages and edge hardware.
- Safety tooling around encrypted prompt injection and model-as-judge reliability is likely to see rapid iteration after this week’s disclosures.
- Enterprise ITSM vendors are watching Serval’s default-on agent rollout for signs of broader adoption patterns.