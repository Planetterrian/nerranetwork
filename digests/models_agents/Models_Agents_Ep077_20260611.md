# Models & Agents
> **Anthropic is asking governments to block unsafe frontier models and fund job-transition programs while committing $350 million of its own money.**

**What You Need to Know:** Anthropic released a detailed policy essay plus three concrete initiatives: a framework for mandatory third-party testing of cyber/bio/autonomy risks, a $200 million economic policy fund, and a $150 million national AI fellowship. Builders should watch how these proposals affect future model release timelines and what compliance tooling emerges. The moves also coincide with fresh agent-payment integrations from Visa, Ripple, and JD.com that remove humans from checkout flows.
---
### Top Story
Anthropic published “The AI Exponential” essay and launched three supporting programs. The essay argues frontier models need mandatory third-party testing for catastrophic risks with revocation power, alongside an economic framework for labor disruption. Anthropic is seeding a $200 million fund to evaluate those ideas and will launch a $150 million national fellowship tomorrow to help early-career workers extend AI benefits. The company also released separate documents on an Advanced AI Framework and an Economic Policy Framework. Developers shipping frontier-adjacent tools should track how these proposals translate into licensing or deployment requirements. Next milestones to watch are any government responses and the first funded evaluation projects. Source: [x.com](https://x.com/AnthropicAI/status/2064783418844762489)
---
### Model Updates
**North Mini Code: MarkTechPost**
Cohere released North Mini Code, a 30B-parameter mixture-of-experts model with 3B active parameters and 256K context. It is the company’s first open-weight developer coding model and runs on a single H100. The model targets agentic coding workflows. Builders working on tool-calling agents can test it this week against existing 7B–13B coding models to see where the extra capacity improves multi-step planning. Source: [marktechpost.com](https://www.marktechpost.com/2026/06/11/meet-north-mini-code-coheres-30b-open-weight-mixture-of-experts-model-with-3b-active-parameters-for-agentic-coding/)

**Minimax M3: r/LocalLLaMA**
Minimax plans to release open weights for M3 on Friday. No parameter count or license details have been shared yet. The announcement has already sparked discussion in local inference communities about expected VRAM requirements. Watch the Friday drop for direct comparisons against current open 30B–70B models. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1u2uje1/minimax_m3_open_weights_release_planned_for_friday/)
---
### Agent & Tool Developments
**Hermes Agent Profile Builder: MarkTechPost**
Nous Research shipped a dashboard that builds complete agent profiles—identity, model, skills, and MCP servers—in a single flow. It replaces the previous multi-step CLI setup. The tool is aimed at users who need repeatable agent configurations without manual YAML editing. Early users report faster iteration when switching between different base models and tool sets. Source: [marktechpost.com](https://www.marktechpost.com/2026/06/11/nous-research-ships-hermes-agent-profile-builder-identity-model-skills-and-mcp-servers-in-one-dashboard-flow/)

**TiDB Agent State Stack: Yahoo Finance Singapore**
TiDB launched the Agent State Stack at the SuperAI Summit Singapore, adding production-grade memory to AI agents. The stack provides persistent, queryable state across sessions and tool calls. It targets teams moving agents from prototypes into long-running production workloads. Source: [Google News](https://news.google.com/rss/articles/CBMihwFBVV95cUxPSWg2OE1xN0F1cnRDOEJoT29iYmxLcmI5RzFacWh0a3QySUhjTExXTnNrNlRrZnZiZFgxbHdvdHhmQWNmRWRNdzU1TFlmWUY0MjZkTkNGdEFRSTdaS185QldVdDkzRjVJNXN2NjkxWWJPSlAwWWtkTEc4NTBPWElaUjlxcTh3Njg?oc=5)

**Visa ChatGPT integration: AI News**
Visa connected its payment rails directly to ChatGPT so agents can recommend products and complete purchases without human intervention. The integration lets agents browse merchant catalogs and finalize checkout using existing Visa infrastructure. Merchants supporting the rails can now be reached by autonomous agents. Source: [artificialintelligence-news.com](https://www.artificialintelligence-news.com/news/visa-chatgpt-integration-enables-ai-agent-retail-purchasing/)

**Ripple XRPL AI Starter Kit: The Cryptonomist**
Ripple released an XRPL AI Starter Kit that lets agents settle payments without human approval. The kit provides templates for on-chain agent wallets and transaction signing. It is positioned for developers building autonomous financial agents on the XRPL ledger. Source: [Google News](https://news.google.com/rss/articles/CBMidkFVX3lxTE5EVzluNzAyT0o5b2pWSHd2LWY3WVhWZE9SLXh5UHpNNUR2a3BULXA3SDFhclBsNEpWNDUyUkM5aWVzQm1NVTJIV29Va2xfejJJN3NZTTRXb3FsQmF1cHJwaXhwc3lmUUh4MHV0UER3aEk0Y3NrU2c?oc=5)
---
### Practical & Community
**ASR Biasing for Voice Transcription: r/LocalLLaMA**
A developer shared an open-source implementation of ASR biasing for local voice dictation apps, modeled after Wispr Flow’s dictionary feature. The technique injects custom vocabulary into system prompts or key-term parameters for providers including Groq, whisper.cpp, and Deepgram. The full project is on GitHub under freestyle-voice/freestyle. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1u2vr8g/how_i_implemented_asr_bias_for_voice/)

**Hardware Trade-offs for Local Inference: r/LocalLLaMA**
Users are comparing a single Radeon VII (32 GB) against dual P100s (48 GB total) for running MoE models at Q8. The discussion centers on whether extra VRAM justifies slower inference speed for larger mixture-of-experts workloads. Several builders are testing Qwen and Gemma variants to measure actual utilization. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1u2wy8s/buy_recommendations_on_a_thight_budget_to_aid_my/)
---
### Under the Hood: Agent State Persistence
Everyone treats “agent memory” as a simple append-only log. In practice it is a set of engineering decisions about durability, query latency, and consistency that quickly become expensive. The core insight is that long-running agents need both short-term scratch space and durable cross-session state; conflating the two leads to either lost context or ballooning storage costs. A production stack therefore splits the two: an in-memory working set for the current trajectory and a separate indexed store (vector + relational) for facts that must survive restarts. Adding the second layer typically adds 30–80 ms per tool call for serialization and indexing but prevents full replay of every prior step. The practical tradeoff appears when agents exceed roughly 200 tool calls in a single session—beyond that point the cost of keeping everything in context exceeds the cost of selective persistence. Teams should start with a simple key-value layer and only introduce vector search once they observe repeated lookups of the same facts across sessions; most early agent workloads never reach that threshold.
---
### Things to Try This Week
- Test Cohere North Mini Code on a multi-step coding agent task to see where the 3B active parameters improve planning over current 7B–13B open models.
- Try the new Visa + ChatGPT integration on a retail recommendation workflow if you have access to the ChatGPT agent builder.
- Add ASR biasing to a local voice app using the freestyle-voice repo to measure transcription accuracy gains on domain-specific terms.
- Spin up the TiDB Agent State Stack demo if you are moving an agent from prototype to multi-day operation.
---
### On the Horizon
- Minimax M3 open weights expected Friday.
- Anthropic $150 million national fellowship program launches tomorrow.
- Continued rollout of agent payment protocols from Visa, Ripple, and JD.com.