# Models & Agents
> **Enterprise teams can now run governed AI agents inside existing procurement systems instead of leaking data to personal ChatGPT accounts.**

**What You Need to Know:** Zip launched five Superagents plus a native MCP implementation that keeps every action inside compliance controls. Alibaba released Qwen3.7-Plus with vision, tool use, and autonomous iteration. JetBrains shipped Mellum2, a 12B MoE model aimed at specialized coding workflows. Nvidia expanded its agent tooling for both PCs and enterprise deployments.
---
### Top Story
Zip announced five Superagents and a procurement-native Model Context Protocol implementation that connects its platform directly to Claude, ChatGPT, and other MCP-compatible assistants while preserving roles, permissions, and full audit trails. The agents run on a shared LangGraph-based execution engine with separate preprocessing, orchestration, synthesis, and post-processing nodes; the orchestration node uses a ReAct loop to decide between vector search, structured API calls, or policy lookups. Every high-impact action still routes through human checkpoints, and the system explicitly avoids training on customer data via zero-retention agreements with model providers. Procurement teams at OpenAI, Anthropic, Block, and Snowflake are already using the platform, with Anthropic doubling its procurement volume without adding headcount. The Superagents and MCP server are in beta now, with general availability expected this summer. Source: [venturebeat.com](https://venturebeat.com/technology/zips-new-ai-agents-want-to-stop-your-finance-team-from-uploading-contracts-into-personal-chatgpt-accounts)
---
### Model Updates
**Qwen3.7-Plus: MarkTechPost**
Alibaba’s Qwen team released Qwen3.7-Plus on the Bailian platform as a multimodal agent model that adds vision and video understanding, deep reasoning, tool invocation, and autonomous iteration capabilities. The model is positioned for self-programming and multi-step agent workflows rather than pure chat. No parameter count or benchmark numbers were disclosed in the announcement. Builders working on vision-grounded agents should test the Bailian integration this week to see how the new tool-calling loop performs against current Claude or GPT-4o setups. Source: [marktechpost.com](https://www.marktechpost.com/2026/06/02/alibabas-qwen-team-launches-qwen3-7-plus-adding-vision-deep-reasoning-tool-invocation-and-autonomous-iteration-on-the-bailian-platform/)

**Mellum2: MarkTechPost**
JetBrains released Mellum2, a 12B MoE model trained on 10.6 trillion tokens and licensed under Apache 2.0 for fast, specialized tasks inside multi-model pipelines. The model targets AI-assisted coding workflows where low latency matters more than frontier reasoning depth. No MMLU or coding-specific benchmarks were shared. Developers already inside JetBrains tools should try swapping it into existing agent chains for narrow code-editing subtasks. Source: [marktechpost.com](https://www.marktechpost.com/2026/06/02/jetbrains-releases-mellum2-a-12b-moe-model-for-fast-specialized-tasks-in-multi-model-ai-pipelines/)

**OpenAI on AWS Bedrock: [@OpenAI](https://x.com/OpenAI)**
OpenAI frontier models and Codex are now generally available on Amazon Bedrock, letting enterprises use existing security, compliance, and governance workflows without new integrations. The move also signals future availability of cybersecurity capabilities such as Daybreak. No pricing or specific model versions were listed. Teams already on Bedrock should evaluate whether routing OpenAI calls through the service reduces their current compliance overhead. Source: [x.com](https://x.com/OpenAI/status/2061564502160892138)

**Qwen3.6-27B local tests: r/LocalLLaMA**
A developer ran a multi-agent orchestrator on Qwen3.6-27B via Ollama on a single 3090 for two weeks, replacing Claude as the reasoning layer. Plan generation stayed close to Claude quality while tool-call format errors hit roughly 12 % and long-context drift appeared past 14k tokens. The test showed the model works as a planner when every tool call is gated, but not as an autonomous executor. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tunmam/replaced_claude_with_local_qwen3627b_in_my/)
---
### Agent & Tool Developments
**Nvidia enterprise agent tools: IT Brief Asia**
Nvidia released new tools aimed at enterprise AI agents, building on its existing agentic AI PC and data-center platforms. The announcement emphasizes support across “literally every computer maker” for the RTX Spark agentic platform. No specific SDK names, install commands, or benchmark numbers were provided. Teams evaluating on-device agents should watch for the first public RTX Spark SDK release. Source: [Google News](https://news.google.com/rss/articles/CBMifEFVX3lxTE5EUXh3NUJ6ZWJCTUVrbzkxS0s5dk5nZDFPYWdIcUx2UFNldTVTYXA3SlBDZWR0TEtIU25xYWZ1WnhGM2FEUW56bXdPX2dJeE9yUS1qMnlHRmpjN0EwNWRQY19YUVZXNjNXRlNxRnVfMzdzLU4yWDVJV3ZjdnA?oc=5)

**Nvidia RTX Spark: Tom's Hardware**
Jensen Huang positioned RTX Spark as an attempt to “reinvent the single most important tool of humanity” with broad hardware-maker support for agentic AI PCs. The platform targets local agent execution rather than cloud-only workflows. No concrete performance numbers or early-access program details were released. Developers building local agents should monitor partner PC announcements for the first devices shipping with the stack. Source: [Google News](https://news.google.com/rss/articles/CBMihANBVV95cUxNNG5RQV85b2ZwVXI0RFp6c0FBdjVBWWdsOW1MVjBSdEpnRmo2NWRHZWE1R09ULXJCOXBvbFYyWjBmVzE4NU10Q3NRNlpvLVBBUVl1eUpucFJPTTVvbEhfb3JOMlJ3bl9ycVNOZGFLbVlaQVlKaDU4Q05xQlplR0hya0JsNDZVdXd0OWVpc21LX2Rxc015UHNlZ0dKQmlrQjBmUzdMQzByVHNkZHUzUEItRU8yLXNCTXMtQnhLMF9pLUI5WXA1MFhKTDdxc2JweTdGaGJRcE9KcEJOUEdLOGpVM0hMcUxJb0I4WEVuVzdYeTNZSkNkY1Z5Vkcwb3hvX2FfTjNRelJMWUJzY2xsQkY5TnlJbk5qOHZYZ0diZWJZSFJmbEtqcmdOaWJ1a2phZFBuTFFOa3B2ZFROVURjQXp3ZWlid2pXcnVyNkNpQnM5bUZMaVE2aFBFMDRzMFdtTlZ4RW1pcFhkR3lHQ2p5bFRrQk9RT1ViVzYzVjl3bzdQVkNJaVhN?oc=5)

**Codex desktop update: Simon Willison**
Simon Willison reported that the Codex desktop app has been updated and restored, crediting Philipp Spiess for the fix. The update returns local Codex functionality after a period of unavailability. No version number or changelog details were shared. Users who rely on the desktop client should reinstall and test current compatibility with their local workflows. Source: [x.com](https://x.com/simonw/status/2061640879224521081)
---
### Practical & Community
**GitHub Copilot token billing: AI News**
GitHub switched Copilot to token-based billing, and early users are reporting price increases compared with the previous flat monthly rate. The change took effect the day after the April announcement window closed. No exact per-token rates or organization-level examples were published. Teams should audit their current usage patterns before the next billing cycle to avoid surprise costs. Source: [artificialintelligence-news.com](https://www.artificialintelligence-news.com/news/github-copilots-billing-changes-users-see-use-based-price-hikes/)

**CVPR 2026 papers browser: r/MachineLearning**
Hugging Face’s Niels Rogge added conference support to paperswithcode.co, indexing all CVPR 2026 papers with arXiv IDs, task categories, GitHub links, and Hugging Face artifacts. The site now lets users filter accepted oral and spotlight papers. Researchers preparing for next week’s conference can use the new view to quickly surface relevant agent and multimodal work. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1tukrf4/browse_cvpr_2026_papers_on_paperswithcode_p/)

**CVE-Bench agent evaluation: r/MachineLearning**
A new benchmark tested five frontier models on 20 real CVEs across 18 Python projects, scoring agents on whether they produced a correct security patch that also passed hidden regression tests. Best solve rate reached 50 % overall and 60 % under full advisory prompts; no model reliably identified vulnerabilities from file-and-function hints alone. The work highlights that passing tests does not guarantee the vulnerability is closed. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1tukvjt/llm_agents_patch_security_bugs_pass_all_tests_but/)
---
### Under the Hood: Non-CUDA inference realities
Everyone talks about running local agents as if CUDA is the only practical path. In practice, SYCL and ROCm backends force different memory layouts and kernel choices that change both throughput and developer effort. On Intel Arc hardware, Qwen3.6-35B-A3B reached 977 tokens per second prompt processing at Q4_K with a 262k context window, but only after careful ngl and thread tuning; the same workload on ROCm still requires manual workarounds for MI50 cards and lacks mature flash-attention equivalents. The quality gap is smaller than the tooling gap—models themselves run, yet missing optimized kernels for common agent operations like structured JSON decoding or long-context summarization keep non-CUDA stacks behind. When the workload is a small number of parallel 30B-class agents and you already own the hardware, the non-CUDA route is worth the extra setup time; otherwise the CUDA ecosystem still wins on both speed of iteration and library availability. The gotcha that bites most teams is assuming a working llama.cpp binary means production-ready agent throughput.
---
### Things to Try This Week
- Test Zip’s MCP server inside Claude or ChatGPT if your team already uses procurement tools; it surfaces governed data without leaving audit trails.
- Try Qwen3.7-Plus on Bailian for any vision-plus-tool-use agent loop you have been running on Claude 3.5.
- Swap Mellum2 into a narrow code-editing sub-agent inside an existing JetBrains workflow to measure latency versus larger models.
- Run the CVE-Bench tasks against your current agent setup to see where it fails the hidden regression tests even when surface tests pass.
- Check the new paperswithcode.co CVPR view for agent-related papers before the conference next week.
---
### On the Horizon
- Zip Superagents and MCP move from beta to general availability this summer.
- First RTX Spark-enabled PCs expected from multiple hardware partners in the coming months.
- CVPR 2026 begins next week in Denver with new agent and multimodal tracks.
- Further OpenAI capability expansions on AWS Bedrock, including Daybreak cybersecurity features, are planned but undated.