# Models & Agents
> **Export controls lifted on Claude Fable 5 and Mythos 5, letting Anthropic restore global access tomorrow with tighter cybersecurity classifiers.**

**What You Need to Know:** Anthropic is redeploying Claude Fable 5 globally after US government talks, routing some coding tasks back to Opus 4.8 while new classifiers block more misuse. OpenAI introduced GeneBench-Pro, a benchmark focused on agents navigating messy biological data and making real research judgments. Simon Willison added video recording to shot-scraper so builders can generate demos from YAML storyboards.
---
### Top Story
Anthropic announced that the Department of Commerce has lifted export controls on Claude Fable 5 and Mythos 5, with access restoration beginning tomorrow. The company is also redeploying Fable 5 with updated classifiers that target additional cybersecurity tasks after discussions with the US government. Routine coding and debugging will temporarily fall back to Opus 4.8 while the new safeguards are refined. Anthropic has started drafting a consensus framework on jailbreak severity with Amazon, Microsoft, Google, and other partners. Builders working with frontier models should watch how the new classifiers affect legitimate agent workflows over the coming weeks. Source: [x.com](https://x.com/AnthropicAI/status/2072106151890809341)
---
### Model Updates
**Claude Sonnet 5 tokenizer changes: Simon Willison (AI builder)**
The new tokenizer increases costs roughly 1.4x for English text and 1.33x for Spanish while leaving Simplified Mandarin pricing essentially unchanged. Simon Willison notes the shift in a post that also links to his full write-up on the model. Builders running high-volume English or Spanish workloads will see the impact immediately in their token budgets. The change highlights how tokenizer design now directly affects operating costs for production deployments. Source: [x.com](https://x.com/simonw/status/2072068898648949184)

**GeneBench-Pro benchmark launch: OpenAI**
OpenAI released GeneBench-Pro, a research-level benchmark that tests how well agents handle messy biological data, select analysis paths, and make the judgment calls required in actual computational biology work. The benchmark moves beyond clean academic tasks to reflect the noisy, iterative nature of real lab pipelines. Teams building scientific agents now have a concrete way to measure progress on this harder class of problems. Watch for early results as groups begin reporting scores on the new suite. Source: [x.com](https://x.com/OpenAI/status/2072004836674167294)

**Fugu vs GLM-5.2 vs Mythos benchmark comparison: Business Standard**
A new analysis examines why different benchmarks continue to rank Fugu, GLM-5.2, and Mythos in varying orders depending on the evaluation suite. The piece underscores that no single leaderboard yet captures the full picture of model strengths across domains. Practitioners comparing these models for specific workloads should run targeted tests rather than relying on headline rankings. Source: [Google News](https://news.google.com/rss/articles/CBMi3wFBVV95cUxPbzZCdGpaMTFPMFpMS1FBaFZHTkl2YW1idkd3MlNUVFRzZzJycnVGVi1fbEEyTXhROVVvX1VxODMzc0IxQmJoNGV3M1lfZk9BSmZ2bGc2SG1nNWs1TWJ6ck40YXp4azc3ZGE1bWxzaDhlcjVUSHRDRXRkMnRRbzI2Y19fYWl4VWw1blktNGZjR0JEdVN3VjloU2VlRnZMTGJ5NUtQSXZzRThmc0hsX0RfUzM4czhidDc1NmY0UjdtaDUtYVFvR1R0TlJtVElPQnJiazl1VWk4NmFTRTRHRXVz0gHkAUFVX3lxTE5YSmc3N3RJaWJyQlhkWXBSMm5GVlU3MWlxRjF4dmcwWi03ZTBQeVM5SjkwTExkWE1pZm5EaVAzQTFULXZObHpzS3lNalFyV2VtUnNJRnFpcDREQmtfZFhhcGd2TURjcFhGU3c3b2FvcVNDb2FHdjBFLVdLeUFyeTBRRElPTFpxNF9GODZHdE1vVFIzN1dGR0lRTlFSSzhwRWZZVDlURUxqSmlOVEpnYjhGbzdORTdFS0FfX1hrLU1sWVRHbERGOUw0bzk4c09XM3ZycGtLTnBNLWducFhaT09vY2R4Tw?oc=5)
---
### Agent & Tool Developments
**Video support added to shot-scraper: Simon Willison (AI builder)**
Simon Willison extended his shot-scraper browser automation tool with video recording driven by YAML storyboards. Users or coding agents can now generate demo videos of web application features by defining a sequence of steps in a simple config file. The update pairs naturally with tools like Codex Desktop and GPT-5.5 for storyboard creation. Teams documenting new interfaces or building agent-driven demos gain a lightweight way to produce consistent recordings without manual screen capture. Source: [x.com](https://x.com/simonw/status/2072001270978855074)

**Sentinel Gateway for prompt injection defense: r/MachineLearning**
A new middleware layer called Sentinel Gateway enforces strict separation between trusted instruction channels and untrusted data channels in LLM agents. Every tool call now requires a signed, scoped runtime authorization token, decoupling observation from execution. The implementation includes FastAPI middleware, token-based gating, audit logging, and support for multi-agent patterns with either local or Postgres persistence. The approach targets structural causes of injection rather than relying solely on input filtering or model alignment. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1ukgwk1/a_systemlevel_approach_to_prompt_injection/)

**Shadow agents governance guidance: cio.com**
The article outlines how IT leaders should govern headless AI agents before they create uncontrolled enterprise risk. It focuses on visibility, policy enforcement, and oversight mechanisms needed as autonomous agents proliferate inside organizations. Teams running production agents should review the recommended controls against their current deployment patterns. Source: [Google News](https://news.google.com/rss/articles/CBMiwwFBVV95cUxOdlNfNEJRTm5HTVc2TUY2OWI2aDFtVHFBWlh6NzJPQk13Tm5aWWZiZDhaeUxSNW1mMk1YeGRRSzlBYi1LNmZ1emFRODBiYVNLX1RJN3ZDT2tMWHZQc3ZCQmtacnhURF9rS3pGTlMyRXhyNE1lZWUyVWNRZWpPb2pzWTRZZG1rRzNwWmwyaHJVcFhBb1dlYWNoRWNfRHBnVjZyQldqNG1IVHlUZjlBTUVMRFdEUnQwOUpLd3dWSzlWLWw0N2s?oc=5)
---
### Practical & Community
**Karpathy on tokens/watt engineering: Andrej Karpathy**
Karpathy highlighted the low-voltage, high-current cluster-scale memory techniques used to maximize tokens per watt in frontier LLM inference. The discussion contrasts this regime with traditional power transmission engineering and underscores the specialized hardware work required for interactive serving. Builders optimizing inference cost should track similar systems-level innovations as they become public. Source: [x.com](https://x.com/karpathy/status/2072061140943921550)

**AIEWF dispatch on agent loops and software factories: Latent.Space**
The recap from the AI Engineer World's Fair covers discussions on agent loops, software factories, and the role of open models in production workflows. Attendees explored how forward-deployed engineers and structured agent patterns are changing development practices. Teams experimenting with long-running agents will find the reported patterns relevant for their own architectures. Source: [latent.space](https://www.latent.space/p/aiewf-daily-dispatch-loops)

**Semantic-layer NL2SQL agent paper: arXiv**
A new system uses a semantic model query (SMQ) intermediate representation so agents reason over curated semantics instead of raw enterprise schemas. A deterministic compiler then emits dialect-specific SQL for SQLite, BigQuery, or Snowflake. The approach achieved 94.15% execution accuracy on the Spider2-snow benchmark using Gemini 3 Pro. Developers facing complex enterprise schemas can examine the released code for the constrained think-act loop and SMQ design. Source: [arxiv.org](https://arxiv.org/abs/2606.31041)
---
### Under the Hood: Resolution-Adaptive KV Cache
Everyone talks about KV cache compression as if it is a simple eviction problem. In practice, SeKV treats context as entropy-guided semantic spans stored across a GPU-CPU hierarchy instead of discarding tokens outright. Each span keeps a lightweight summary vector on GPU for fast routing while a low-rank SVD basis lives on CPU for on-demand reconstruction of individual tokens. A trained zoom-in step selectively materializes only the spans relevant to the current query, avoiding full cache reloads. This design trades a small amount of added latency for the ability to handle 128K contexts with 53% less GPU memory than full caching. The quality gain comes from preserving information that pure eviction methods lose permanently once a token is dropped. Teams running long-context agents should test resolution-adaptive approaches when memory pressure is the binding constraint rather than raw throughput.
---
### Things to Try This Week
- Test shot-scraper’s new YAML-driven video mode on a web app you are documenting to see how quickly you can produce consistent feature demos.
- Review the Sentinel Gateway repo if you are building tool-using agents and want to add signed authorization tokens between instruction and data channels.
- Run GeneBench-Pro tasks against your current biology or data-analysis agents to establish a baseline before the benchmark sees wider adoption.
- Compare Claude Sonnet 5 tokenizer costs on your English-heavy workloads against your existing setup to decide whether prompt compression or model switching is warranted.
---
### On the Horizon
- Japan’s planned sovereign AI model and 10-million-robot initiative will likely surface more details on training scale and robotics integration in the coming months.
- Further refinements to Fable 5 classifiers are expected as Anthropic works to reduce false positives on legitimate coding requests.
- Sen. Warner’s call for comments on potential AI agents market legislation could produce draft language within the next quarter.
- Additional teams are expected to publish early results on GeneBench-Pro as the benchmark circulates.