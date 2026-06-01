# Models & Agents
> **OpenAI’s model cracked an 80-year math problem by leaning on its native strengths in structured reasoning rather than brute force.**

**What You Need to Know:** OpenAI published a solution to a long-standing math problem that had resisted human efforts for decades. NVIDIA released a large open-source collection of physical AI agent tools and skills. JetBrains shipped Mellum 2, a 12B MoE coding model, while DeepSeek-V4-Flash showed strong high-context performance on DGX Spark hardware. Builders should watch how these releases affect agent reliability and local inference economics this week.
---
### Top Story
An OpenAI model produced a solution to a famous math problem that had stumped human mathematicians for 80 years. The work highlights how current reasoning models can exploit structured search and verification patterns that differ from typical human approaches. Ars Technica’s write-up focuses on clarifying the method beyond OpenAI’s original presentation. Practitioners working on formal reasoning or theorem-proving pipelines now have a concrete example of where test-time compute delivers outsized gains. Watch for follow-up papers that dissect the exact search strategy and whether it generalizes beyond this single problem. Source: [arstechnica.com](https://arstechnica.com/ai/2026/06/openais-math-breakthrough-played-to-ais-strengths/)
---
### Model Updates
**Mellum 2 12B A2.5B: r/LocalLLaMA**
JetBrains released Mellum 2, a 12B-parameter MoE model with 2.5B active parameters focused on coding. The reasoning variant reportedly matches Qwen 3.5 9B on coding tasks while trailing the smaller Qwen 3.5 4B on general benchmarks. Models and a technical report (arXiv:2605.31268) are available on Hugging Face. Builders evaluating small coding agents should test whether the MoE routing improves multi-file edit consistency compared with dense 9B baselines. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tts4f7/mellum_2_12b_a25b/)

**DeepSeek-V4-Flash on DGX Spark: r/LocalLLaMA**
A user reported running the original MXFP8/MXFP4 DeepSeek-V4-Flash on a two-node DGX Spark (GB10) setup with vLLM, achieving roughly 1680–2150 tokens/s prefill and 37–49 tokens/s decode across 4K–256K context at batch size 1. The model maintained stable performance at 256K context with low degradation and handled 3–4 concurrent requests without major issues. It outperformed several denser models on private high-context retrieval and reasoning tests while consuming ~280 W at load. Teams running MoE models under 15B active parameters on ARM-based inference nodes should examine the posted Docker compose for RoCE multi-node setups. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1ttlp99/deepseek_v4_flash_performance_on_dgx_spark/)

**Ling-2.6-1T discussion: r/LocalLLaMA**
InclusionAI open-sourced Ling-2.6-1T, a ~1T-parameter MoE with 63B active parameters, 1M native context, and 256K exposed via API. Local users are prioritizing three questions before adoption: whether quality per active parameter justifies the size, whether practical serving is feasible, and whether the long context remains stable. The model is positioned as a flagship open release, so developers tracking the open-versus-closed gap should monitor early independent long-context evaluations. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tttmob/for_ling261t_what_would_make_the_size_feel/)
---
### Agent & Tool Developments
**NVIDIA Releases Major Collection of Open Source Agent Tools and Skills for Physical AI: GlobeNewswire**
NVIDIA published a substantial set of open-source tools and skills aimed at physical AI agents. The release targets robotics and embodied scenarios, complementing earlier simulation work. Developers building hardware-adjacent agents can now pull the components directly rather than starting from scratch. Expect integration examples with existing frameworks in the coming weeks. Source: [Google News](https://news.google.com/rss/articles/CBMi7wFBVV95cUxNX2trR1p3QUhIc3paM2lpUEp5MkFRQS1LZUMwdWdCUFlzaTRxRXlNVnNleVhKSWxYNk9uS3dKWjM2dUROaEsxTm12dFBHZ1NDT3lrcF9RTE5laGdtY2ZYampINU5CZFMzby1uekVzV3hWT0o5eDk3WTM1YUZlNFRVTGNyNGNsZHhxUktNS01tcy1YYVo5UDZ6cklSNmxpN3k1MzBPc2xOWTI3X1pPZVhrSmJjekV0Sm5qX3JySEkxdmZwSHRvSVRndVJpckVRN1Vnc2Juek1MNW5rbGJJMDZnaWQ1VGE2YjFyR3VRQzU0bw?oc=5)

**Microsoft Agent Framework at BUILD 2026: Microsoft Agent Framework**
Microsoft will present updates to its Agent Framework at BUILD 2026 starting June 2, alongside Microsoft Foundry announcements. The session will cover new agent orchestration and interoperability features. Attendees and remote viewers should watch for concrete SDK changes and sample code that demonstrate multi-agent workflows. Source: [devblogs.microsoft.com](https://devblogs.microsoft.com/agent-framework/microsoft-agent-framework-at-build-2026/)

**Cadence And Nvidia Team To Develop First Fully Autonomous EDA Agent: Forbes**
Cadence and NVIDIA announced ChipStack AI Super Agent, an autonomous electronic design automation agent. The system combines Cadence tools with NVIDIA infrastructure to automate chip design steps. Hardware teams working on complex SoCs can evaluate early access to reduce manual iteration cycles. Source: [Google News](https://news.google.com/rss/articles/CBMivAFBVV95cUxOczdWaFBOSEdiYVMzWEJlVFpmcG8tdW5YajVRR3RWUldxTU53eHM3SDNYSHNUQ293MUhtMVc2WE1CRGoxV0otU3FZN0ZhNjF0V3BBUnNOXzN0bkdBUmtQV0Z1LTZheWdGYXRMWGpkOWtRY1dfbk9PVDBzNVUwaVM3TGlGSGdPRUpvTTJzWm0weXlUZjJIb09ORDhNS2ttemtmQlJXeVU4WFFMaWRjaGhSYi1KM3lYeUZGUmsyMg?oc=5)
---
### Practical & Community
**VibeETL: r/LocalLLaMA**
A former data scientist released VibeETL, a visual data-manipulation platform built on Polars and React Flow as a lightweight Alteryx-style alternative. The project emphasizes zero-copy Arrow transport, a native BFS layout algorithm, and isolated Python subprocess execution with a 30-second timeout. The repo is MIT-licensed and designed for community extensions via manifest-driven tool additions. Users needing fast local ETL pipelines without heavy dependencies should clone and test the launcher scripts. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tthxl4/i_was_a_data_scientist_for_10_years_before/)

**Open Models – May 2026: r/LocalLLaMA**
A community graph summarized May 2026 open-model releases including Ring, Command, StepFun, and LFM families. The post notes that May felt lighter after April’s activity and flags MiniMax-M3 as an imminent arrival. Developers tracking open-weight progress can use the graph as a quick reference for which families to benchmark next. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1ttl45v/open_models_may_2026/)
---
### Under the Hood: Agent Permission Scoping
Everyone talks about “giving agents tools” as if access is a simple on/off switch. In practice, permission models must encode task intent, temporal scope, and blast-radius limits simultaneously. The core mechanism starts with workload identity issued at deployment rather than static service-account keys; the identity carries only the minimal credentials required for the declared task and is revoked on completion. This adds a small issuance latency (tens of milliseconds) but eliminates the long-lived credential surface that agents otherwise accumulate. When the agent attempts an action outside its declared scope, the system can either deny or escalate, avoiding the common failure mode where broad human approvals are granted without context. Most teams still default to “human in the loop for everything,” which reintroduces friction and does not scale; the practical decision point is whether the task’s blast radius justifies the extra round-trip or whether scoped, expiring credentials are sufficient. The gotcha that bites teams is assuming agents will self-limit exploration—without explicit scoping they will probe every available path, exactly as described in recent enterprise security reporting.
---
### Things to Try This Week
- Test Mellum 2 on multi-file refactoring tasks to see whether its MoE routing improves consistency over dense 9B coding models.
- Run the posted DeepSeek-V4-Flash Docker compose on compatible ARM nodes if you need stable 256K context at low power.
- Clone VibeETL and feed it a messy historical dataset to evaluate the Polars-backed visual pipeline against your current ETL stack.
- Watch Microsoft’s BUILD sessions on the Agent Framework for concrete multi-agent orchestration patterns you can prototype immediately.
---
### On the Horizon
- NVIDIA and enterprise partners are expected to publish integration examples for the new physical AI agent toolkit within the next two weeks.
- MiniMax-M3 is scheduled for release in roughly ten days; watch for parameter count and training-token details.
- BUILD 2026 begins June 2 with multiple Microsoft Agent Framework announcements.
- Early access programs for the Cadence–NVIDIA autonomous EDA agent are anticipated shortly after Computex.