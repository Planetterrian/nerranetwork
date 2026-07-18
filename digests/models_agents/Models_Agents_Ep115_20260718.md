# Models & Agents
> **Moonshot just dropped the largest open-source model yet at 2.8 trillion parameters, matching top closed systems on long-horizon agentic benchmarks.**

**What You Need to Know:** Moonshot AI released Kimi K3 with a 1-million-token context window, native vision, and always-on reasoning mode. It leads on BrowseComp at 91.2 and ranks second on AA-Briefcase behind only Claude Fable 5. Full weights land July 27. Builders should test its single-agent long-horizon workflows immediately.
---
### Top Story
Moonshot AI released Kimi K3, a 2.8-trillion-parameter frontier model with a 1-million-token context window, native visual understanding, and an always-on "thinking mode." The model uses two internal architectural innovations—Kimi Delta Attention (hybrid linear attention) and Attention Residuals—and is priced at $3 per million input tokens and $15 per million output tokens, with cached inputs at $0.30. On GDPval-AA v2 it scored 1,687 (third overall), on AA-Briefcase it reached 1,527 (second), and it set a new state of the art on BrowseComp at 91.2 in a single-agent setup without context compression. The company also demonstrated 48-hour autonomous chip design and compressed multi-week astrophysics research into two hours. This moves the open-weight frontier forward from last week's coverage of DeepSeek and earlier Chinese releases, directly addressing the open-vs-closed performance gap. Full weights arrive July 27; watch for community fine-tunes and agent harness integrations. Source: [venturebeat.com](https://venturebeat.com/technology/chinas-moonshot-ai-releases-kimi-k3-the-largest-open-source-model-ever-rivaling-top-u-s-systems)
---
### Model Updates
**Kimi K3: Moonshot AI**
Moonshot AI released Kimi K3, a 2.8-trillion-parameter model with a 1-million-token context window and always-on reasoning. It scored 1,687 on GDPval-AA v2 and 1,527 on AA-Briefcase while using 21% fewer output tokens than its predecessor. Pricing sits at $3/$15 per million tokens with automatic context caching. Builders should try its long-horizon single-agent BrowseComp workflow this week.

**GPT-5.6 Sol: OpenAI**
OpenAI announced GPT-5.6 Sol reached a new state of the art in cybersecurity on “The Last Ones” cyber range. The model now powers Codex Security for finding, validating, and fixing real-world vulnerabilities. It is already integrated into the Codex Security plugin workflow. Source: [x.com](https://x.com/OpenAI/status/2078243667081617826)

**Inkling: Thinking Machines Lab**
Mira Murati’s Thinking Machines Lab released Inkling, an Apache-2.0 multimodal MoE model with 975B total parameters (41B active) trained on 45 trillion tokens of text, images, audio, and video. A smaller 276B (12B active) variant is in testing. It is positioned as a strong base for fine-tuning via the Tinker platform rather than a raw frontier leader. Source: [simonwillison.net](https://simonwillison.net/2026/Jul/16/inkling/#atom-everything)

**ZUNA1.1: Zyphra**
Zyphra released ZUNA1.1, a 380M masked diffusion autoencoder for scalp EEG under Apache 2.0. It accepts variable-length inputs from 0.5 to 30 seconds (versus the original fixed five seconds) while holding or improving NMSE across arbitrary channel layouts. Source: [marktechpost.com](https://www.marktechpost.com/2026/07/17/zyphra-releases-zuna1-1-an-apache-2-0-eeg-foundation-model-with-variable-length-inputs-from-0-5-to-30-seconds/)

**Error Diffusion: Sakana AI**
Sakana AI introduced Error Diffusion, a backpropagation-free training method for dual-stream excitatory/inhibitory networks that obey Dale’s principle. The approach reached 96.7% on MNIST and 61.7% on CIFAR-10 and scales to reinforcement learning via modulo error routing. Source: [marktechpost.com](https://www.marktechpost.com/2026/07/17/sakana-ais-error-diffusion-trains-dale-compliant-dual-stream-networks-reaching-96-7-mnist-and-61-7-cifar-10-without-backpropagation/)
---
### Agent & Tool Developments
**VulnHunter: Capital One**
Capital One open-sourced VulnHunter, an agentic security tool that performs attacker-first forward analysis from APIs and file uploads, then runs a falsification engine to discard false positives before surfacing findings with proposed fixes. It currently runs on Claude Opus 4.8 inside Claude Code and is released under Apache 2.0. The three-stage workflow (forward analysis → falsification → remediation) was validated across thousands of internal repositories. Source: [venturebeat.com](https://venturebeat.com/technology/capital-one-releases-vulnhunter-an-open-source-ai-tool-that-finds-software-flaws-before-hackers-do)

**CrabTrap: Brex**
Brex released CrabTrap, an open-source HTTP/HTTPS proxy that intercepts all agent network traffic and uses an LLM-as-a-judge (only on the long tail, <3% of requests) plus deterministic rules to enforce policy. It is framework- and API-agnostic; users simply set HTTP_PROXY. The policy builder bootstraps from observed traffic rather than hand-written rules and includes an eval system that replays thousands of requests in minutes. Source: [venturebeat.com](https://venturebeat.com/orchestration/brex-built-its-ai-agent-policy-by-watching-what-agents-actually-do-not-by-writing-rules-first)

**Always-On Memory Agent: Google Cloud**
Google Cloud shipped the Always-On Memory Agent, a reference implementation on Google ADK and Gemini 3.1 Flash-Lite that replaces vector databases and embeddings with continuous LLM-driven consolidation into SQLite. An orchestrator routes between Ingest, Consolidate, and Query sub-agents that maintain structured memory 24/7 without RAG. Source: [marktechpost.com](https://www.marktechpost.com/2026/07/18/google-clouds-always-on-memory-agent-replaces-rag-and-embeddings-with-continuous-llm-consolidation-on-gemini-3-1-flash-lite/)

**Agent Architecture Rebuilds: Intuit**
Intuit rebuilt its production agent system twice in four months, moving from specialist agents to a central orchestrator and then to a skills-and-tools architecture after natural-language handoffs caused compounding errors. The second rebuild took 60 days; evals became the primary measurement mechanism and a human handoff feature is now in 1% production testing. Source: [venturebeat.com](https://venturebeat.com/orchestration/intuit-scrapped-its-own-ai-agent-architecture-twice-in-four-months-at-vb-transform-2026-its-ai-vp-called-that-the-fast-path)

**Infrastructure Panel: LinkedIn, Walmart, Zendesk**
LinkedIn, Walmart, and Zendesk reported that legacy infrastructure—not models—is the primary bottleneck when moving agents to production. LinkedIn pre-provisions container pools and pushes LLMs to the leaves of deterministic workflows; Walmart added governance to deduplicate citizen-developer agents; Zendesk emphasized investing in data pipelines over simply handing 20 billion conversations to large context windows. Source: [venturebeat.com](https://venturebeat.com/data/agents-think-in-milliseconds-legacy-infrastructure-doesnt-linkedin-walmart-and-zendesk-shared-how-they-closed-the-gap-at-vb-transform-2026)
---
### Practical & Community
**Claude Code web session fixes: Simon Willison**
Simon Willison highlighted ongoing regressions in Claude Code on the web that block cloning public GitHub repos into /tmp from existing sessions. He is requesting an automated test suite to prevent future breakage of this core functionality. Source: [x.com](https://x.com/simonw/status/2078343997119172705)

**Firefox in WebAssembly: Puter**
Puter compiled Firefox to WebAssembly so the full browser runs inside another browser, with all traffic proxied over WebSocket using the Wisp protocol. The project used roughly $25,000 of Claude Opus and Fable tokens under a Max subscription and supports end-to-end encryption.

**grok-build open source: xAI**
xAI open-sourced the entire Grok Build codebase (844k lines of Rust) under Apache 2.0 after earlier data-upload concerns. The repo includes the main system prompt, subagent prompt, a self-contained Mermaid terminal renderer, and tool implementations ported from Codex and OpenCode.

**Cars24 + OpenAI agents: OpenAI**
Cars24 uses OpenAI-powered voice and chat agents to handle over 1 million monthly conversation minutes, recover 12% of lost leads, and extend agentic workflows across internal teams. Source: [openai.com](https://openai.com/index/cars24)
---
### Under the Hood: Agent Identity and Credential Sharing
Everyone treats agent identity as a simple “give each agent its own key” checkbox. In practice it is a three-layer enforcement problem that most production systems still solve with borrowed human or service-account credentials. The first layer is issuance: creating a scoped, revocable identity at agent spawn time instead of reusing a shared API key. The second layer is runtime mediation: every outbound call must carry that identity so policy engines can evaluate it before the request reaches the target API. The third layer is attribution: logging which identity performed which action so post-incident forensics can isolate the blast radius. When these layers are missing, a single compromised agent can act with the full permissions of every other agent sharing its credential, which is exactly the pattern seen in 69% of the surveyed enterprises. The practical tradeoff is latency versus safety—adding a network proxy or sidecar for identity enforcement adds measurable overhead but collapses the blast radius from “entire fleet” to “single agent.” Most teams discover the gap only after the first incident; the fix that actually moves the needle is treating non-human identity as infrastructure rather than an application-level afterthought.
---
### Things to Try This Week
- Test Kimi K3 on long-horizon information-seeking tasks using its 1M context window directly instead of multi-agent workarounds.
- Deploy VulnHunter on a non-production codebase to see the attacker-first forward analysis plus falsification engine in action.
- Point CrabTrap at an existing agent harness and let it bootstrap policy from a few days of real traffic.
- Run the Always-On Memory Agent reference implementation on a small persistent task to compare continuous consolidation against traditional RAG.
---
### On the Horizon
- Kimi K3 full weights scheduled for July 27.
- Intuit plans to scale its human-in-the-loop handoff feature beyond the current 1% of customers in the coming weeks.
- Brex is accepting community contributions to CrabTrap for SSO, RBAC, and escalation workflows.
- OpenAI continues internal work on GPT-Red to improve multi-turn and image-based attack coverage.