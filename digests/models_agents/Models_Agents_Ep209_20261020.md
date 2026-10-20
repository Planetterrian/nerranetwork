# Models & Agents
> **Devin now commits 89% of Cognition’s own code while the company hits a $1bn annualised revenue run-rate at a $48bn valuation.**

**What You Need to Know:** Cognition’s Devin coding agent has moved from research demo to production reality, handling end-to-end engineering tasks at Goldman Sachs, Mercedes-Benz and Nubank. Exa released a faster, cheaper search API that tops its own benchmarks against Perplexity and Brave. Multiple hardware and local-inference projects surfaced today showing builders are actively optimising for MoE models and multi-engine workflows on consumer and used-server gear.
---
### Top Story
Cognition reported that Devin, its autonomous software-engineering agent, now commits 89% of the code its own engineers commit. The San Francisco lab crossed US$1bn in annualised revenue run-rate on 25 September 2026, up from US$492m in May, after raising more than US$2bn at a US$48bn valuation. Devin performs full-cycle tasks—planning, coding, testing and committing—while humans review output; it currently sits between junior and mid-level engineer capability according to CEO Scott Wu. Enterprise customers include Goldman Sachs, Mercedes-Benz, GE Aerospace and Nubank; Infosys, Cognizant and AWS have signed distribution deals. Legacy modernisation is a standout use case, with Devin analysing more than 200,000 lines of COBOL for Mercedes-Benz and Nubank reporting 8–12× efficiency gains on large migrations. The July 2025 acquisition of Windsurf added an agentic IDE that pairs the autonomous agent with a daily developer environment. Source: [aimagazine.com](https://aimagazine.com/news/cognition-what-is-the-devin-ai-coding-agent)
---
### Model Updates
**Exa 3.0 Search API Tops Perplexity, Brave and Parallel on 8 Benchmarks: MarkTechPost**
Exa released Exa 3.0, an upgrade to its web-search API for AI agents that adds a larger embedding model and a cheaper “lite” search type priced at $4 per 1,000 requests. Dynamic Highlights, now generally available, selects tokens across results rather than page-by-page and uses 95% fewer tokens than full-page text while improving answer quality. The company claims the new version leads Perplexity, Brave and Parallel on all eight of its self-run benchmarks, with the largest margin on BrowseComp (91.8%) and ATLAS (42.0%). Exa runs its own crawler and independent index covering more than 2 trillion URLs; no self-hosted option exists. Lite supports query, result count, highlights, text, categories, domain and date filters plus location and moderation. Source: [marktechpost.com](https://www.marktechpost.com/2026/10/20/exa-3-0-search-api-lite/)

**Inception Releases Mercury 3 Diffusion LLM at 1,068 Tokens per Second: MarkTechPost**
Inception released Mercury 3, a diffusion language model that writes answers in parallel rather than token-by-token and reaches 1,068 tokens per second on NVIDIA GPUs with a 1M-token context window. On the company’s own benchmark table the model leads GPT-6 Luna and Claude Haiku 5.5 on 8 of 12 tests at medium settings, posting its largest gains on instruction following and agentic coding. Mercury 3 is more than 40× larger than Mercury 1; average quality across standard benchmarks rose roughly 3× across those generations while speed stayed above 1,000 tokens per second. The model is served only through Inception’s NVIDIA GPU API; no open weights or quantized builds are available. Source: [marktechpost.com](https://www.marktechpost.com/2026/10/19/inception-mercury-3-diffusion-llm/)

**migtissera/Tess-4.5-27B (Qwen finetune): r/LocalLLaMA**
Tess-4.5-27B is a Qwen3.8-27B fine-tune that reaches the same benchmark scores with 25% fewer tokens overall and 32–43% fewer tokens on the hardest subsets (CLI-40 and data extraction). The model was released by the author of Synthia; GGUF weights are available on Hugging Face. Fewer tokens translate directly into faster answers and longer sessions before the context window fills, compounding with draft-head acceleration on local GPUs. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1xadfm7/migtisseratess4527b_qwen_finetune/)
---
### Agent & Tool Developments
**Closing the agent governance gap: CIO**
Enterprises now face the problem of tracking and securing their own proliferating AI agents rather than only defending against external rogue agents. Most organisations lack basic visibility: according to Anthropic, 82% have discovered unregistered agents on their networks and 57% already run agents on multi-stage workflows. Agent creation is frictionless—one API call or “vibe coding” by any employee—so vendor, platform-native and home-grown agents compound the sprawl. Security teams need a single record per agent that captures onboarding owner, access privileges, behaviour and cross-platform capabilities; an over-provisioned email agent with 50 attached tools is cited as an example worth investigating. Source: [cio.com](https://www.cio.com/article/4237146/closing-the-agent-governance-gap.html)

**SandboxAQ Expands Switch to Track AI Agent Costs, Performance and Security: HPCwire**
SandboxAQ expanded its Switch platform to monitor AI-agent spend, performance metrics and security posture in a single view. The update targets the same visibility gap described in enterprise governance discussions, giving security and finance teams unified telemetry across every platform an agent runs on. Source: [hpcwire.com](https://www.hpcwire.com/aiwire/2026/10/19/sandboxaq-expands-switch-to-track-ai-agent-costs-performance-and-security/)

**AI agents are forcing a rethink of digital identity, cybersecurity experts warn: THINK Digital Partners**
Cybersecurity experts argue that autonomous agents require new digital-identity frameworks because traditional human-centric controls no longer suffice when agents act independently across systems. The piece highlights the same internal-agent risk surface that CIO and SandboxAQ coverage address. Source: [thinkdigitalpartners.com](https://www.thinkdigitalpartners.com/news/2026/10/20/ai-agents-are-forcing-a-rethink-of-digital-identity-cybersecurity-experts-warn/)
---
### Practical & Community
**Old server machine with 2x 3060 12GB for MoE models, anything I’m missing?: r/LocalLLaMA**
A builder plans to buy a used HP Z640 with dual E5-2680 v4 CPUs and 64 GB ECC RAM for €550, then add two RTX 3060 12 GB cards to run Qwen 3.8 Flash Next on Strata plus llama.cpp, PyTorch CV training, RL in PyBullet, LoRA fine-tuning and MiniMax H3 video generation. Questions focus on dual-socket PCIe layout, power-limit adapters for the 3060s, whether the included Quadro M6000 24 GB is useful under CUDA 12, and chassis thermals that reached 86 °C during MemTest. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1xamrvy/old_server_machine_with_2x_3060_12gb_for_moe/)

**I got tired of Apple's configurator, so I built one for local AI: r/LocalLLaMA**
A developer released modelfit.io, a real-time Mac configurator that shows which LLMs fit in memory and estimated inference speed for every Apple silicon configuration, using a model fitted on actual llama-bench runs. Apple list prices update daily; the tool helps buyers choose between M4, M5 Pro and other SKUs for local workloads. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1xagmpd/i_got_tired_of_apples_configurator_so_i_built_one/)

**HermesConsole: A demo showing off VoiceManager, my low latency streaming STT / TTS server. MIT, client docs, and python client.: r/LocalLLaMA**
VoiceManager provides low-latency streaming speech-to-speech over a single WebSocket with barge-in support, session memory and tool-call integration; HermesConsole is a Kotlin reference client styled after Star Trek LCARS. The stack uses Nemotron and Breeze TTS 2 and is released under MIT with client-integration docs and a Python client. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1xag5bj/hermesconsole_a_demo_showing_off_voicemanager_my/)

**Budget upgrade for a 31B model? Dual GPUs over PCIe x1 or another approach?: r/LocalLLaMA**
A user running Gemma 4 31B Q5_K_M at ~2.3 t/s on a single RTX 3060 12 GB seeks 15+ t/s at 16 k context and is evaluating an RTX 5060 Ti 16 GB on a PCIe 3.0 x1 riser plus layer splitting, or a cheap dual Tesla P100 X79/X99 build. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1xagsfh/budget_upgrade_for_a_31b_model_dual_gpus_over/)
---
### Also Today
**AI Agent Cuts Centalion’s Trade Finance Amendment Time 80%: PYMNTS.com** Source: [pymnts.com](https://www.pymnts.com/news/artificial-intelligence/2026/ai-agent-cuts-centalions-trade-finance-amendment-time-80/)

**Cognizant and Google Cloud Expand Partnership to Scale Enterprise AI Agents: HPCwire** Source: [hpcwire.com](https://www.hpcwire.com/aiwire/2026/10/19/cognizant-and-google-cloud-expand-partnership-to-scale-enterprise-ai-agents/)

**Security firm finds China-linked AI agent behind Japan cyberattacks: The Straits Times** Source: [straitstimes.com](https://www.straitstimes.com/asia/east-asia/security-firm-finds-china-linked-ai-agent-behind-japan-cyberattacks)

**AI agents are changing the manager's job. Accountability hasn't caught up: IT Brief Australia** Source: [itbrief.com.au](https://itbrief.com.au/story/ai-agents-are-changing-the-manager-s-job-accountability-hasn-t-caught-up)

**New AI model detects hidden diseases in routine CT scans: News-Medical** Source: [news-medical.net](https://www.news-medical.net/news/20261020/New-AI-model-detects-hidden-diseases-in-routine-CT-scans.aspx)

**Documents Reveal Military Plan for Agentic AI That Hacks U.S. Adversaries: Gizmodo** Source: [gizmodo.com](https://gizmodo.com/documents-reveal-military-plan-for-agentic-ai-that-hacks-u-s-adversaries-2000827957)
---
### Under the Hood: llms.txt Curation Layer
Web pages are built for human readers, so they wrap useful content inside navigation, scripts and ads that agents must strip away at token cost. The llms.txt proposal places a single curated Markdown file at the site root that gathers expert-level summaries and links to key pages, eliminating that parsing step. Because context windows remain finite, every saved token matters; a clean Markdown map lets an agent decide relevance before fetching full pages. The v2 revision added standard link relations—rel="alternate" type="text/markdown" and rel="describedby"—so agents can discover the curated file without guessing URLs. Adoption is already visible: OpenAI, Anthropic and Gemini publish their own developer docs this way, and documentation platforms generate the file automatically. The practical tradeoff is maintenance overhead versus retrieval quality; sites that keep the file current see agents reach the right information faster, while stale files simply become another outdated asset. Teams should publish one when they already maintain high-quality Markdown documentation and want coding agents or retrieval systems to consume it reliably.
---
### Things to Try This Week
- Try Exa 3.0 Lite at $4 per 1,000 requests if your agents need cheaper search with Dynamic Highlights instead of full-page text.
- Check modelfit.io when configuring a new Mac for local inference—it shows real llama-bench-derived speed estimates for every Apple silicon SKU.
- Compare Mercury 3’s 1,068 tokens-per-second diffusion output against your current autoregressive model on instruction-following or agentic-coding tasks.
- Run VoiceManager with the HermesConsole Kotlin client if you need low-latency streaming speech-to-speech with barge-in for local agents.
- Test Tess-4.5-27B GGUF weights on your MoE or dense setup to see whether the 25% token reduction improves session length on hard CLI or extraction workloads.
---
### On the Horizon
- OpenAI continues expanding low-resource language support (COBOL, Fortran, Visual Basic) for legacy modernisation customers.
- Microsoft Foundry is adding scheduled agents and smarter tool-use features alongside GPT-6 model integration.
- Vultr is rolling out further agentic-AI infrastructure upgrades on its platform.
- More documentation platforms are expected to auto-generate llms.txt files following the v2 link-relation standard.
