# Models & Agents
> **Z.ai’s GLM-5.4 runs 28 layers twice via shared weights to deepen reasoning at fixed parameter count.**

**What You Need to Know:** Z.ai released GLM-5.4, its first Loop Transformer model, available only through a paid Coding Plan API subscription. Simon Willison’s datasette-charts 0.2a0 now integrates directly with Datasette Agent so users can request charts in chat that render inline and update live. SeoulTech published SLAKE, a training-free method that approximates attention on low-value tokens while preserving KV-cache eviction for long contexts. Builders should test the Z.ai Responses API endpoint for the new model and try the live demo at agent.datasette.io.
---
### Top Story
Z.ai released GLM-5.4, its first model built with a Loop Transformer architecture. A group of weight-shared layers runs multiple iterations per forward pass, refining hidden states without increasing parameter count. The 750B-scale model runs the middle 28 layers twice. It is accessible only via the company’s Coding Plan subscription on the shared OpenAI-compatible endpoint at https://api.z.ai/api/v1. Simon Willison built a temporary llm-glm plugin because the existing llm-zai plugin did not yet support the new model. The architecture matches a similar looped design described earlier this month by Thinking Machines Lab for Inkling 2 Mini. Willison tested image generation by prompting pelicans riding bicycles across GLM versions 5.1 through 5.4 and observed a stark style shift between 5.2 and 5.3, with later versions producing results closer in quality to OpenAI and Anthropic outputs. GLM-5.4 remains closed weights for now, with an open release planned after further safety work. Watch for open-weights release after safety work completes and test coding tasks through the Responses API once you have a Coding Plan key. Source: [simonwillison.net](https://simonwillison.net/2026/Nov/23/glm-54/)
---
### Agent & Tool Developments
**datasette-charts gains live agent-driven chart generation: Simon Willison**
datasette-charts 0.2a0 now lets Datasette Agent write and render charts from natural-language requests using the same suggestion and generation tools as the chart builder panel. The integration opens an iframe side panel that updates when the user changes tables or switches views. A demo video shows the agent creating a downloads-over-time chart, then describing the new view after the user switches to the datasette table. datasette-agent 0.7a1 adds support for chat sessions that open an iframe side panel and navigate via fragment hashes, enabling tighter coupling with plugins that update state through those hashes. The release was built specifically to resolve navigation bugs exposed by the charts integration. Users sign in with GitHub at agent.datasette.io to try the combined flow. Source: [simonwillison.net](https://simonwillison.net/2026/Nov/24/datasette-charts/) Source: [simonwillison.net](https://simonwillison.net/2026/Nov/24/datasette-agent/)

**Solana launches solana.ai platform for autonomous agents and payments: Gadgets 360**
The platform bundles Solana Agent Kit, an agent registry, pay.sh for USDC micropayments, and Milo, an autonomous trading agent that runs 24/7. Payment Channels processed over one million messages per second in tests with 100,000 wallets; Alibaba Cloud joined as a launch partner. Confidential Compute runs on testnet and records hardware attestation on-chain without exposing private data. The Solana AI Toolkit supplies a Model Context Protocol server and developer resources for connecting agents to blockchain services. More than 120 teams are already building within the ecosystem. The design lets agents transfer tokens, execute DeFi swaps, and purchase services without maintaining conventional API subscriptions or user accounts. Source: [gadgets360.com](https://www.gadgets360.com/cryptocurrency/news/solana-introduces-solana-ai-to-support-autonomous-ai-agents-and-payments-crypto-adoption-ai-technology-adoption-12366798)

**Workday completes C1.ai acquisition for AI-agent identity governance: citybiz**
Workday now combines C1.ai’s identity platform with its HR, finance, and IT data so permission changes follow employee role events and extend automatically to autonomous agents. The system grants, monitors, and revokes access across Slack, Jira, finance dashboards, and cloud infrastructure. Gerrit Kazmaier called the move a deliberate investment in governing hybrid human-plus-agent workforces. C1.ai previously connected email, CRM, code repositories, and cloud systems so that hiring, role changes, and departures trigger immediate access updates. The combined offering reduces manual ticket-driven administration while enforcing consistent policies for both people and agents. Source: [citybiz.co](https://www.citybiz.co/article/937902/workday-completes-acquisition-of-c1-ai-to-expand-ai-agent-identity-governance-and-security/)

**meshIQ releases Neo AI agent for middleware troubleshooting: IT Brief New Zealand**
Neo is an agent that diagnoses and resolves issues in middleware environments. It is positioned for enterprise operations teams that already run meshIQ monitoring. The agent extends existing meshIQ capabilities into automated remediation workflows. Source: [itbrief.co.nz](https://itbrief.co.nz/story/meshiq-launches-neo-ai-agent-for-middleware-troubleshooting)
---
### Practical & Community

**Surelio raises CHF 1M to secure AI agents: Startupticker.ch**
The Swiss startup will use the funding to build security tooling aimed at autonomous agents. No further product details were released. Source: [startupticker.ch](https://www.startupticker.ch/en/news/surelio-raises-chf-1m-to-secure-ai-agents)
---
### Also Today
**OpenAI introduces Shirudo open-source Linux runtime for agent defense: [@OpenAI](https://x.com/OpenAI)**
Shirudo lets agents write dynamic eBPF controls that shield systems from exploits without downtime while defenders prepare patches. Source: [x.com](https://x.com/OpenAI/status/2124980590717911527)

**OpenAI launches OpenWorks program for small-business AI adoption: [@OpenAI](https://x.com/OpenAI)**
The program funds local AI experts to help small businesses build tools and skills at no cost to the businesses. Source: [x.com](https://x.com/OpenAI/status/2124922133545714160)

**Natural enables voice agents to accept payments over the phone: PYMNTS.com**
The feature lets voice agents complete transactions without handing off to a human operator. Source: [pymnts.com](https://www.pymnts.com/news/artificial-intelligence/2026/natural-enables-voice-agents-to-accept-payments-over-the-phone/)
---
### Under the Hood: SLAKE Long-Context Token Handling
SeoulTech’s SLAKE keeps an approximate representation of discarded tokens instead of dropping them outright. The method combines Partially Taylor-Approximated Attention, which applies a Taylor expansion only to low-value tokens while using full attention on important ones, with Value-Aware Budget Scoring that ranks tokens by their expected contribution to the final output. Because the approximation retains a rough picture of the full context, information loss stays lower than pure eviction while memory usage remains fixed. The quality gain disappears once context length exceeds the point where even the retained high-value tokens no longer fit the budget. SLAKE was evaluated on sequences exceeding 128,000 tokens, the regime where current large language models already strain compute and memory resources. Two standard approaches—discarding low-value tokens or simplifying attention calculations—each introduce distinct problems: outright eviction loses information, while uniform approximation can degrade accuracy across the board. SLAKE applies the approximation selectively and scores tokens according to their downstream impact, preserving the most useful signals inside a fixed memory envelope. Use SLAKE when you need stable long-context performance on hardware with strict memory caps and can tolerate a small accuracy trade-off; fall back to standard eviction or full attention when every retained token must be exact. Source: [techxplore.com](https://techxplore.com/news/2026-11-smarter-tokens-context-ai.html)
---
### Things to Try This Week
- Sign up for Z.ai’s Coding Plan and test GLM-5.4 on agentic coding tasks through the Responses API endpoint.
- Visit https://agent.datasette.io/, sign in with GitHub, and ask Datasette Agent to generate a chart from one of your tables.
- Clone the Solana Agent Kit and run the pay.sh example to see how an agent can spend USDC on services without managing API keys.
- Read the SLAKE paper and benchmark it against your current long-context eviction strategy on sequences over 64k tokens.
---
### On the Horizon
- Z.ai plans to release open weights for GLM-5.4 after additional safety work.
- Solana Foundation expects more than 120 teams to ship production agents on the new platform in the coming months.
- Workday will begin rolling out combined employee-plus-agent access controls to existing customers in Q1 2027.
- meshIQ intends to expand Neo’s middleware coverage to additional enterprise message brokers.
