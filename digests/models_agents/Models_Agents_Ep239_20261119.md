# Models & Agents
> **Google's Gemini 4 Neon ships with 1M context at $3 per million input tokens for enterprise reasoning tasks.**

**What You Need to Know:** Google released Gemini 4 Neon, the new mid-tier model in its Gemini 4 family, positioned between Carbon and Hydrogen with four effort levels and strong agentic coding results. Deutsche Telekom committed $110 million to Mistral while Anthropic priced its IPO at $83 per share. Builders should test Neon in Antigravity or the Gemini API this week for long-context agent runs and watch the December 1 pricing adjustments on the rest of the Gemini 4 line.
---
### Top Story
Google introduced Gemini 4 Neon as the middle model in its Gemini 4 series, retiring Argon and targeting coding agents, knowledge work, and science workflows with a 1M-token context window. It carries $3 per million input tokens and $15 per million output tokens, four effort levels, and a default 64K output that can reach 1M via background long decode. At high effort it matches Carbon on the Intelligence Index while posting 58.6 on the AA Coding Agent Index and 95.2% on GraphWalks long-context tasks. Neon runs only on Google-hosted infrastructure with closed weights and supports orchestration of parallel Hydrogen sub-agents inside Antigravity. The rollout reaches the paid Gemini API, AI Studio, Android Studio, Gemini for business, and Pro/Ultra subscribers in the Gemini app under the “Deeper analysis” label. Developers working on agentic coding or long-horizon science tasks should compare Neon directly against Carbon and Hydrogen on their own workloads before the December 1 price changes take effect. Source: [blog.google](https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-gemini-4-neon/)
---
### Model Updates
**Deutsche Telekom’s Tech Fund Invests $110 Million in Mistral AI: WSJ**
Deutsche Telekom’s tech fund placed $110 million into Mistral AI, adding to the French lab’s existing European backers. The investment supports continued development of Mistral’s open-weight and enterprise model families. Source: [wsj.com](https://www.wsj.com/business/deutsche-telekoms-tech-fund-invests-110-million-in-mistral-ai-13597573)

**Anthropic Prices IPO at $83 Per Share: [@AnthropicAI](https://x.com/AnthropicAI)**
Anthropic priced its IPO at $83 per share, above the initial range, with Nasdaq trading expected to begin the following day. The filing covers Class A common stock and lists Goldman Sachs and Morgan Stanley as lead underwriters. Source: [anthropic.com](https://www.anthropic.com/news/anthropic-prices-initial-public-offering)

**New LoRA Adapter Lifts Qwen3.8 Coding Success From 39% to 65%: MarkTechPost**
Hugging Face released Qwen3.8-27B-pi-adapted, an Apache-2.0 LoRA adapter trained with reinforcement learning for the pi coding agent. It raises SWE-bench Pro hard-51 pass@1 from 39.2% to 64.7% and Terminal-Bench 2.1 from 39.5% to 55.8%. Source: [marktechpost.com](https://www.marktechpost.com/2026/11/18/hugging-face-qwen3-8-27b-pi-adapted-lora/)

**AI models deliver up to 14% chip design gains in AMD collaboration: ET CIO**
OpenAI reported that its models produced up to 14% improvements in performance, power, and area on AMD’s flagship GPU IP relative to already-optimized baselines, with some changes already taped out. The same workflow delivered single-digit gains on AMD’s next-generation CPU blocks and reduced standard-cell area by 13% and 10% in the vector and matrix units of OpenAI’s custom Jalapeño inference chip. Source: [cio.economictimes.indiatimes.com](https://cio.economictimes.indiatimes.com/news/artificial-intelligence/ai-models-deliver-up-to-14-chip-design-gains-in-amd-collaboration/135977170)
---
### Agent & Tool Developments
**The Envoy agentic stack: Routing models, tokens, and MCP: Google Cloud**
Google Cloud described an Envoy-based agentic stack that routes requests across models, manages token budgets, and supports the Model Context Protocol for tool calling. The approach aims to give operators fine-grained control over cost and latency in production agent deployments. Source: [cloud.google.com](https://cloud.google.com/blog/products/networking/the-envoy-agentic-stack-routing-models-tokens-and-mcp)

**Daydream launches AI personal shopping agent: Axios**
Daydream introduced an AI personal shopping agent that helps users discover and compare products across retailers. The agent focuses on preference matching and price tracking rather than completing purchases. Source: [axios.com](https://www.axios.com/2026/11/18/daydream-personal-shopping-agent-ai-assistant)

**Early look at Loop, new autonomous AI agent from Google: TestingCatalog AI News**
Google is testing Loop, an autonomous agent capable of multi-step task execution inside the Gemini ecosystem. Early reports indicate it can maintain longer-running sessions than previous Gemini agent features. Source: [testingcatalog.com](https://www.testingcatalog.com/early-look-at-loop-new-autonomous-ai-agent-from-google/)

**Cato Networks launches AgentSense to block harmful AI agent actions: Network World**
Cato Networks released AgentSense, a security control that inspects and can block actions taken by AI agents before they reach enterprise resources. The product integrates with existing network and identity policies. Source: [networkworld.com](https://www.networkworld.com/article/4250389/cato-networks-launches-agentsense-to-block-harmful-ai-agent-actions.html)
---
### Practical & Community
**datasette-arrows 0.1a0: Simon Willison**
Simon Willison published datasette-arrows 0.1a0, a plugin that adds Apache Arrow as a streaming export format inside Datasette. The release demonstrates the new register_output_renderer hook for custom streaming outputs without loading entire tables into memory. Source: [simonwillison.net](https://simonwillison.net/2026/Nov/18/datasette-arrows/)

**Nutrient Data Extraction API: JSON Matching Your Schema With Per-Field Citations and Confidence: MarkTechPost**
MarkTechPost covered a Nutrient Data Extraction API that converts PDFs, scans, and Office files into JSON matching a user-defined schema while attaching page, region, and match-label citations to every field. A Studio interface lets teams test extraction before writing code. Source: [marktechpost.com](https://www.marktechpost.com/2026/11/18/nutrient-data-extraction-api-citations-confidence/)

**Code Effects Releases Version 7 with Secure AI Agents, Rule Governance, and Auditing for .NET: HackerNoon**
Code Effects shipped version 7 of its .NET rules engine, adding secure AI agent integration, rule governance controls, and full auditing capabilities. The update targets enterprise teams that need auditable decision logic alongside agent workflows. Source: [hackernoon.com](https://hackernoon.com/code-effects-releases-version-7-with-secure-ai-agents-rule-governance-and-auditing-for-net0)

**Microsoft launches cheaper, specialised AI models with flexible licensing: TechGig**
Microsoft announced a new line of cheaper, domain-specialized models accompanied by more flexible licensing terms. The offering is positioned for enterprises that want lower per-token costs on narrower tasks. Source: [techgig.com](https://techgig.com/news/ai/microsoft-launches-cheaper-specialised-ai-models-with-flexible-licensing/135974357)
---
### Also Today

**The Gemini app is now available on lower-memory Android devices.: Google AI Blog**
Google extended the Gemini app to lower-memory Android devices, enabling Gemini Live and custom image creation on a wider range of phones. Source: [blog.google](https://blog.google/innovation-and-ai/products/gemini-app/gemini-lower-memory-devices/)

**Microsoft brings AI inference closer to enterprise data with Windows Server 2028: Network World**
Microsoft announced Windows Server 2028 features that bring AI inference closer to on-premises enterprise data. Source: [networkworld.com](https://www.networkworld.com/article/4250500/microsoft-brings-ai-inference-closer-to-enterprise-data-with-windows-server-2028.html)

**Understanding Cross-Modal Inconsistency through Representation Subspaces in Omni Models: arXiv NLP**
A new arXiv paper analyzes how omni models produce inconsistent answers across modalities and isolates the representation subspaces responsible. Source: [arxiv.org](https://arxiv.org/abs/2611.22619)

**Contract-Explicit Evaluation: From Auditing Learned Readers to Scoped Certificates: arXiv NLP**
Another arXiv paper introduces a contract-explicit evaluation protocol that delivers distribution-free certificates for document-level relation extraction and LLM-judge leaderboards. Source: [arxiv.org](https://arxiv.org/abs/2611.22665)
---
### Under the Hood: Decision Models vs Generative LLMs on Bounded Tasks
Decision models return a typed answer plus probability directly instead of generating free text, which removes the need for post-hoc parsing on classification and judging tasks. In contact-center workloads they match frontier LLMs on six classification problems while running at the lowest per-request cost among the API options tested. Their main weakness is abstention behavior: most models rarely select the explicit “no-answer” option, creating the largest gap versus the strongest generative baselines. On two judging tasks the same models lose accuracy sharply once parameter count drops, and they show higher position bias than generative judges. The paper’s eight real-world use cases demonstrate that routing high-confidence decision-model predictions automatically while sending uncertain cases to generative LLMs or humans yields the best accuracy-cost trade-off. Teams facing high-volume intent classification or compliance checking should therefore benchmark a decision model first on their exact label set before defaulting to a full generative call. Source: [arxiv.org](https://arxiv.org/abs/2611.22949)
---
### Things to Try This Week
- Test Gemini 4 Neon at high effort on a long-context coding or science task inside Google Antigravity and compare cost per task against Carbon.
- Install datasette-arrows and export a large table as Arrow to see streaming performance without full memory load.
- Run the new Qwen3.8-27B-pi-adapted LoRA on a SWE-bench-style repo task to measure the 25-point lift on hard instances.
- Evaluate a decision model such as Gemini-Decision-1 on your contact-center intent labels to check abstention rates before routing production traffic.
- Review the Envoy agentic stack configuration examples on Google Cloud if you need token-budget controls across multiple models.
---
### On the Horizon
- Anthropic shares are expected to begin trading on Nasdaq following the $83 IPO price.
- Google continues rolling out Neon to additional Gemini app surfaces and business customers.
- Microsoft’s Windows Server 2028 inference features move into preview for enterprise data-center operators.
- More European funding rounds for open-weight labs are anticipated after the Deutsche Telekom–Mistral announcement.
