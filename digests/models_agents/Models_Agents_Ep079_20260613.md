# Models & Agents
> **US export controls just forced Anthropic to pull its newest frontier models offline for every user worldwide.**

**What You Need to Know:** Anthropic disabled Fable 5 and Mythos 5 for all customers after the US government issued an export control directive targeting foreign nationals. Moonshot AI open-sourced Kimi K2.7-Code, a coding model that reduces thinking-token usage by roughly 30% while claiming double-digit gains on internal benchmarks. Google researchers introduced "faithful uncertainty," a technique that lets models express calibrated doubt instead of refusing or hallucinating. Developers should watch how these changes affect production agent routing and compliance workflows this week.
---
### Top Story
The US government issued an export control directive requiring Anthropic to suspend all access to Fable 5 and Mythos 5 by any foreign national, including its own employees. The company responded by disabling the two newest models for every customer to maintain compliance, while all other Claude models remain available. The directive cites national security authorities and applies both inside and outside the United States. Anthropic called the order a misunderstanding and stated it is working to restore access. Builders relying on the latest Claude releases for agentic coding or research tasks must immediately reroute workloads to unaffected models or alternative providers. The incident highlights how quickly regulatory actions can alter the available frontier model surface. Source: [x.com](https://x.com/AnthropicAI/status/2065597531644743999)
---
### Model Updates
**Kimi K2.7-Code: Moonshot AI**
Moonshot AI released Kimi K2.7-Code under a Modified MIT license as an open-source update to its K2.6 coding model. The new model uses the same trillion-parameter mixture-of-experts architecture, adds a 256K context window, and reduces reasoning-token usage by approximately 30%. It reports gains of +21.8% on Kimi Code Bench v2, +11% on Program Bench, and +31.5% on MLS Bench Lite, all proprietary benchmarks. The model runs exclusively in thinking mode with temperature fixed at 1.0 and is available through the Kimi API and Kimi Code. Teams already routing through OpenAI-compatible gateways can swap it in to test lower inference costs on agentic coding workflows without architecture changes. Source: [marktechpost.com](https://www.marktechpost.com/2026/06/12/moonshot-ai-releases-kimi-k2-7-code-a-coding-model-reporting-21-8-on-kimi-code-bench-v2-over-k2-6/)

**OpenAI Codex rate-limit changes: [@OpenAI](https://x.com/OpenAI)**
OpenAI began rolling out the ability for Go, Plus, Pro, and Business users to bank Codex rate-limit resets for later use, starting each with one free reset. Plus and Pro users can also invite up to three friends to try Codex for two weeks; both parties receive an extra banked reset when the friend sends their first message. The changes address user requests for more flexible usage timing. Developers running sustained Codex workloads can now plan around saved resets rather than daily expirations.
---
### Agent & Tool Developments
**GitHub Copilot CLI delegation improvements: The GitHub Blog**
GitHub updated Copilot CLI with better orchestration logic that reduces unnecessary handoffs between agents. The change improves progress speed on multi-step tasks without requiring users to adjust any new settings. It builds on existing delegation patterns while tightening when the CLI decides to pass work to another component. Teams using Copilot CLI for terminal-based coding can test the update immediately for fewer context switches. Source: [github.blog](https://github.blog/ai-and-ml/how-we-made-github-copilot-cli-more-selective-about-delegation/)

**NanoClaw + JFrog registry integration: VentureBeat**
NanoClaw agents now route all package, CLI tool, and MCP server requests exclusively through JFrog registries, blocking installation of unvetted or malicious dependencies. When a request is rejected, the agent receives a 403 policy error and is guided to an approved alternative. The integration is free for open-source users via JFrog’s public vetted registry and plugs directly into enterprise JFrog environments for compliance tracking. Operators gain a system of record for every package an agent consumes without manual approval steps. Source: [venturebeat.com](https://venturebeat.com/security/nanoclaw-and-jfrog-launch-immune-system-to-block-ai-agents-from-downloading-malicious-code)

**PixelRAG visual retrieval system: VentureBeat**
UC Berkeley, Princeton, EPFL, and Databricks researchers released PixelRAG, which renders web pages as screenshots, indexes image tiles with Qwen3-VL-Embedding-2B, and feeds them to vision-language models. On SimpleQA it reaches 78.8% accuracy versus 71.6% for the strongest text parser, with similar gains on table and multimodal tasks. An agent using PixelRAG consumed 3.6 million prompt tokens versus 37.5 million for text retrieval on the same workload. The system requires Qwen3-VL-4B-class models or larger; smaller models lose the accuracy advantage. Source: [venturebeat.com](https://venturebeat.com/data/pixelrag-beats-text-parsers-on-accuracy-and-cuts-ai-agent-token-costs-10x)
---
### Practical & Community
**PaddleOCR-ncnn-CPP: r/MachineLearning**
A community developer released an updated C++ implementation of PaddleOCR v3 through v6 using the lightweight ncnn inference engine. The project removes the heavy dependencies of the official Paddle C++ runtime, making deployment simpler and faster for OCR tasks. Code and examples are available on GitHub under the original author’s repository. Developers needing on-device or low-dependency OCR can drop this in without managing the full Paddle stack. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1u4hy2x/paddleocr_v3v4v5v6_implemented_in_c_with_ncnn_p/)

**olmo-eval workbench: Hugging Face Blog**
AllenAI published olmo-eval, an evaluation workbench designed to fit inside the iterative model development loop. It supports rapid iteration on open models with standardized metrics and logging. The tool is aimed at teams training or fine-tuning models who need consistent evaluation without building custom harnesses. Check the AllenAI section of the Hugging Face blog for setup details. Source: [huggingface.co](https://huggingface.co/blog/allenai/olmo-eval)
---
### Under the Hood: Faithful Uncertainty in LLMs
Everyone talks about reducing hallucinations as if the only options are “answer everything” or “refuse when uncertain.” In practice, faithful uncertainty separates a model’s internal statistical confidence from the linguistic signals it uses to express doubt. The core mechanism trains the model to output hedging phrases such as “my best guess is” only when its own token probabilities for the factual claim fall below a learned threshold. This alignment avoids the utility tax that occurs when strict abstention discards large numbers of correct answers the model actually knows. Adding the technique requires supervised fine-tuning on uncertainty-labeled data, which creates a bootstrapping problem because the correct label depends on what that specific model knows at training time. In agentic systems the payoff appears in tool-use decisions: the model can decide whether to invoke search or trust its parameters without external classifiers. The practical limit is that prompting alone cannot fully close the gap; reinforcement learning on uncertainty-aware trajectories is still required for production reliability. Teams should adopt faithful-uncertainty prompting today for low-stakes chat while planning RL stages for any long-horizon agent.
---
### Things to Try This Week
- Swap Kimi K2.7-Code into any OpenAI-compatible gateway you already run for coding agents and measure thinking-token reduction on your own workloads.
- Route NanoClaw agents through a JFrog registry (free for open-source) if you need an immediate block on unvetted package installs.
- Test PixelRAG on a Wikipedia-scale factual QA task if your current text RAG pipeline loses structured content; start with Qwen3-VL-4B or larger.
- Update your Codex usage pattern to bank rate-limit resets now that the feature is rolling out to paid tiers.
- Add hedging prompts that mirror faithful-uncertainty phrasing to any agent that currently oscillates between over-confident answers and full refusals.
---
### On the Horizon
- Anthropic continues working with regulators to restore Fable 5 and Mythos 5 access; watch for an update on affected customer workloads.
- Moonshot AI has not yet submitted Kimi K2.7-Code to independent benchmarks such as DeepSWE; expect community runs in the coming weeks.
- Google’s faithful-uncertainty work points toward future RL stages that bake metacognition deeper into frontier models.
- More visual-retrieval systems are likely to appear as teams replicate the PixelRAG screenshot-tiling approach on domain-specific corpora.