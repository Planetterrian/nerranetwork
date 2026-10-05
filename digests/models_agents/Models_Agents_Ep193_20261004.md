# Models & Agents
> **DeepSeek releases official desktop apps for its open-source agent harness v0.2 with plugin management and scheduled tasks.**

**What You Need to Know:** DeepSeek released version 0.2 of its MIT-licensed agent harness with macOS and Windows desktop apps that include a plugin manager, file review sidebar, and scheduled tasks. OpenAI safety leaders resigned citing a broken development culture. Microsoft ThinkingBox grades agents on database state rather than tool-call logs and is now available on Hugging Face.
---
### Top Story
DeepSeek released official macOS and Windows desktop apps for DeepSeek Harness v0.2, its MIT-licensed agent harness. The apps bundle the dsh command line tool and support sign-in with a DeepSeek account or API key. Version 0.2 adds a plugin manager page, a right-hand sidebar for file and code diff review, document handling for spreadsheets and PDFs, and an Automation Task plugin for recurring prompts. The harness runs on the Cordis paradigm and supports third-party models through OpenAI-compatible endpoints. The repository has reached 240,000 GitHub stars. Users can install via deepseek.com/harness or npx [@deepseek](https://x.com/deepseek)-ai/dsh web. The v0.2.1-alpha.1 build adds an experimental Claude Code Mods compatibility layer. Four session modes are available including Standard, Creator, PTC, and Minimal. The desktop build eliminates the need for separate Node.js or pnpm installs. Source: [marktechpost.com](https://www.marktechpost.com/2026/10/03/deepseek-harness-v0-2-brings-official-desktop-apps-to-its-open-source-agent-harness/)
---
### Model Updates
**Jev offers frontier-class reasoning without hallucinations from the co-inventor of ChatGPT: r/MachineLearning**
TypeSafe AI positions Jev as a smaller model that cannot hallucinate. The team ran 16,379 benchmark requests measuring latency and billing. It targets jobs where other models fall short. The model is built by the co-inventor of ChatGPT. Reviewers describe it as humbler yet genuinely useful for specific tasks. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1wx1knr/jev_not_frontier_but_still_worth_your_attention_r/)

**Sam Altman flags religious framing of AI models as a safety issue: Sam Altman (OpenAI) (X)**
Altman stated he is very uncomfortable with people ascribing religious force or surrendering human judgment to AI models. He called it a real safety issue. The post received 4.1 million views. The statement was posted on October 3, 2026. Source: [x.com](https://x.com/sama/status/2106388373221118198)

**Martian highlights its AI Frontier Framework for cost-efficient LLM optimization: TipRanks**
Martian presented the framework as a route to lower inference costs on frontier models. The company positions the tool as a practical optimization layer for existing large language models. Source: [tipranks.com](https://www.tipranks.com/news/private-companies/martian-highlights-ai-frontier-framework-for-cost-efficient-llm-optimization)
---
### Agent & Tool Developments
**The Agent Said It Was Done. The Database Disagreed.: Hugging Face Blog**
Microsoft ThinkingBox grades agents on terminal backend state and side effects instead of tool-call logs. It runs 507 stateful business workflows twenty times each across various models. The benchmark is available through Hugging Face and OpenEnv. One retail workflow example showed an agent issuing nine valid calls yet leaving a ticket status as solved when the required state was on hold. The approach measures consistency across repeated runs rather than single successful traces. Source: [huggingface.co](https://huggingface.co/blog/microsoft/thinkingbox)

**AI Has Started to Act — NVIDIA Unveils Safeguards for Agents That Go Beyond Control: Korea IT Times**
NVIDIA introduced safeguards designed to keep autonomous agents within defined bounds. The safeguards target agents that exceed intended operational limits during execution. Source: [koreaittimes.com](http://www.koreaittimes.com/news/articleView.html?idxno)

**The Consumer AI Agent Race: Five Platforms, Three Pricing Models, One Winner: forkast.news**
Five consumer platforms compete with three distinct pricing models. The platforms target everyday users seeking autonomous task handling. Source: [forkast.news](https://forkast.news/the-consumer-ai-agent-race-five-platforms-three-pricing-models-one-winner/)

**AI Agents Raise Fresh Risks for Customer Data: CX Today**
Agents introduce new vectors for customer data exposure. The report highlights growing attack surfaces tied to agent autonomy. Source: [cxtoday.com](https://cxtoday.com/this-week-in-cx-security-ai-agents-data-leaks-and-a-growing-attack-s)
---
### Practical & Community
**Just published post on needing default hard budget caps: Simon Willison (AI builder)**
Simon Willison argues that pay-by-usage services must default to hard budget caps that return errors after a set monthly limit. He notes AWS launched spending limits in September and Google Cloud offers Spend Caps. The post recommends an opt-in checkbox for removing the cap. Coding agents lower the barrier to spinning up services that can incur unexpected charges. The feature prevents surprise bills from runaway agent activity. Source: [simonwillison.net](https://simonwillison.net/2026/Oct/3/default-hard-budget-caps/)

**Observations on using Dot vs regular ChatGPT: Simon Willison (AI builder) (X)**
Simon Willison notes Dot appears limited to a single conversation while he prefers controlling context across multiple threads. The observation follows several days of testing the new interface. Source: [x.com](https://x.com/simonw/status/2106500511465869380)
---
### Under the Hood: State Verification in Stateful Agent Workflows
Agent benchmarks that score only tool-call syntax miss cases where the final database record is wrong. ThinkingBox instead replays each workflow twenty times and checks the terminal backend state against the required end state. The approach adds measurable overhead because every run must reach a stable database snapshot rather than stopping at the last function return. This verification layer catches side effects that surface only after the agent declares completion. Teams running long-horizon agents should adopt state checks on any workflow that mutates shared records. The cost is higher per evaluation run but eliminates silent failures that syntax-only graders accept. The benchmark isolates each workflow in separate MCP tool sessions to ensure clean state measurement.
---
### Things to Try This Week
- Install the DeepSeek Harness v0.2 desktop app on macOS or Windows to test the new plugin manager and scheduled automation tasks.
- Run ThinkingBox through Hugging Face on a sample retail workflow to see how state verification differs from tool-call logging.
- Set a monthly spend limit in AWS or Google Cloud before deploying any coding agent that calls paid APIs.
---
### On the Horizon
- Further compatibility updates expected for DeepSeek Harness after the v0.2.1-alpha.1 build.
- Additional agent safety frameworks from NVIDIA anticipated in coming weeks.
- More consumer agent platforms likely to announce pricing adjustments.
