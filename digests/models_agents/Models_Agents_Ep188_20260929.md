# Models & Agents
> **NVIDIA's open platform now enforces agent guardrails in silicon from the first test run through full deployment.**

**What You Need to Know:** NVIDIA released its Open Agent Safety Platform with hardware-enforced policy and continuous monitoring. Anthropic's Sonnet 5.5 model now runs the free tier on Claude.ai. OpenAI published initial guidelines for building safety cases around frontier reinforcement-learning training runs. Microsoft extended Fabric with new agentic data engineering tools. Bloomberg introduced an Enterprise MCP layer for financial data access by agents.
---
### Top Story
 The system combines OpenShell for external policy, BlueField-4 DPUs, and DOCA software to create a host-independent layer. One hundred firms have already joined the effort. The platform is available now for developers building agent fleets at enterprise scale. TrendAI extended the same platform with threat intelligence that informs policy boundaries across the model, harness, and tool layers. Rachel Jin, Chief Platform and Business Officer at TrendAI, noted that security must cover every component an agent touches. The integration supplies visibility and response capabilities that complement NVIDIA's enforcement layer. Source: [nvidianews.nvidia.com](https://nvidianews.nvidia.com/news/open-agent-safety-platform)
---
### Model Updates
**Claude Sonnet 5.5 — Simon Willison (AI builder) (X)**
Sonnet 5.5 runs more than thirty percent faster and costs up to thirty percent less than the prior Sonnet version while beating it on every benchmark. It is now the default model for the free tier at claude.ai. Free users can therefore run the same coding and animation experiments previously limited to paid accounts. ChatGPT's free tier still uses the less capable GPT-5.6 Luna model. Simon Willison highlighted that free-tier users can now build three-dimensional WebGL animations that previously required paid access. The model also resolves the same long-thinking bug observed in Opus 5.5 when using maximum effort settings. Source: [x.com](https://x.com/simonw/status/2104682232522944909)

**OpenAI on securing frontier RL training runs — [@OpenAI](https://x.com/OpenAI) (X)**
OpenAI released a document outlining how it constructs safety cases for frontier reinforcement-learning training runs. The guidelines cover technical safeguards, operational practices, and procedures for investigating misalignment incidents. The post links directly to the full openai.com index page. The approach requires documented arguments and evidence that each identified hazard is either eliminated or reduced below an acceptable threshold. Source: [x.com](https://x.com/OpenAI/status/2104815409522483470)

**OpenAI shelves new AI model release over safety concerns — Reuters**
OpenAI decided not to release a new frontier model after internal tests revealed safety issues. The decision follows similar pauses at other labs and comes after public statements from former researchers about extinction-level risks. No release date or model name was provided. The move aligns with calls from multiple lab leaders for tighter controls on frontier development. Source: [reuters.com](https://www.reuters.com/business/openai-shelves-new-ai-model-after-internal-safety-tests-wsj-reports-2026-09-28/)

**CoWindow and MassAlloc Attention: collective causal coverage and distribution-adaptive compute [R] — r/MachineLearning**
Two new attention methods reduce redundant computation in long-context models. CoWindow distributes distant context across KV heads with complementary windows while sharing local and prefix-sink windows. MassAlloc uses softmax statistics to skip low-contribution tiles after full causal QK scoring. At 128K tokens on eight H100 GPUs the methods delivered forward speedups of 7.4x and 2.2x respectively versus full attention. Backward speedups reached 8.6x for CoWindow and 3.0x for MassAlloc. At 14B parameters with 32K context the techniques reduced total training FLOPs by 28.5 percent and 23.1 percent while maintaining comparable capabilities on reported evaluations. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1wt1gbk/cowindow_and_massalloc_attention_collective/)
---
### Agent & Tool Developments
**Bloomberg Launches Enterprise MCP to Seamlessly Connect Bloomberg Data with Clients' Enterprise AI Applications — PR Newswire**
Bloomberg released Enterprise Model Context Protocol, an AI access layer for Data License Plus. The protocol supplies AI-ready metadata, semantic context, and workflow-focused Skills so agents can interpret data across more than one hundred million securities and fifty thousand fields. Clients can now query in plain language and receive context-carrying results without manual identifier reconciliation. The solution targets research, portfolio, risk, and operations workflows in capital markets. Source: [prnewswire.com](https://www.prnewswire.com/news-releases/bloomberg-launches-enterprise-mcp-to-seamlessly-connect-bloomberg-data-with-clients-enterprise-ai-applications-302891331.html)

**Microsoft updates Fabric for agentic transformation — cio.com**
Microsoft added Fabric Apps, agentic data engineering features from the Osmos acquisition, and a Monitor Hub for proactive operations inside Microsoft Fabric. Fabric Apps lets teams build end-to-end governed applications directly on OneLake without deploying containers. The new agentic engineering tools let users define an outcome and boundaries while an agent executes, validates, and refines the work autonomously. The Monitor Hub provides a unified view across jobs, capacities, workspaces, and workloads to support proactive operations. Source: [cio.com](https://www.cio.com/article/4227790/microsoft-updates-fabric-for-agentic-transformation.html)
---
### Practical & Community
**How we found 24 Android vulnerabilities using our open source AI security agent — GitHub Blog**
GitHub researchers used an open-source AI security agent to discover twenty-four vulnerabilities in Android. The post details the targeted taskflows that produced the findings and explains how developers can run the same agent against their own applications. The agent is released under an open-source license. The work demonstrates concrete taskflows for automated security testing on mobile platforms. Source: [github.blog](https://github.blog/security/how-we-found-24-android-vulnerabilities-using-our-open-source-ai-security-agent/)

**From Autonomous Cars to Autonomous Agents: The Five Levels of AI Agent Autonomy — MIT Media Lab**
MIT Media Lab published a framework mapping five levels of AI agent autonomy, drawing parallels to the SAE levels used for autonomous vehicles. The document provides a structured way to classify agent capabilities and required safeguards at each level. It is available on the Media Lab site. The framework helps teams define required controls as autonomy increases. Source: [media.mit.edu](https://www.media.mit.edu/articles/from-autonomous-cars-to-autonomous-agents-the-five-levels-of-ai-agent-autonomy/)

**Holo4: powering generalist computer-use agents — Hugging Face Blog**
Hugging Face released Holo4, a model aimed at generalist computer-use agents. The announcement includes details on training approach and intended use cases for agents that interact with graphical interfaces. The model and associated resources are hosted on the Hugging Face platform. The release targets agents that perform actions across desktop and web environments. Source: [huggingface.co](https://huggingface.co/blog/Hcompany/holo4)
---
### Under the Hood: Safety Cases for Frontier RL Training
Safety cases for frontier reinforcement-learning runs require evidence that specific hazards have been controlled rather than relying on a single test score. The approach begins with hazard identification, then demands documented arguments and evidence that each hazard is either eliminated or its likelihood reduced below an acceptable threshold. Technical safeguards such as sandboxed execution and output filtering form one layer while operational practices such as staged rollouts and independent review boards form another. When an incident occurs the case must be updated with new evidence showing why the controls failed and how they were strengthened. The method forces teams to quantify uncertainty instead of claiming safety from the absence of observed failures. Teams should adopt this structure when the training run involves novel capabilities whose failure modes are not yet fully characterized; simpler evaluation checklists remain sufficient for narrower fine-tuning projects. The OpenAI document emphasizes that safety cases must address both technical and operational dimensions simultaneously.
---
### Things to Try This Week
- Try Sonnet 5.5 on the free tier at claude.ai for coding or animation tasks that previously required a paid account.
- Test the GitHub open-source AI security agent against an Android app you maintain to surface vulnerabilities the same way the researchers did.
- Explore Bloomberg Enterprise MCP if you build financial agents that need context-rich data retrieval without manual identifier mapping.
- Run the CoWindow or MassAlloc attention implementations from the arXiv papers if you train or serve long-context models on multiple H100 GPUs.
---
### On the Horizon
- OpenAI DevDay takes place tomorrow with expected announcements on new capabilities.
- Anthropic indicated Haiku 5.5 will arrive in the coming weeks.
- More labs are expected to publish safety-case frameworks following OpenAI's release.