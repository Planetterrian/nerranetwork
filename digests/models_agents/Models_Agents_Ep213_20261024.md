# Models & Agents
> **Moonshot's Kimi K3.1 Pro brings frontier-level coding and agent performance to a 2.8T MoE model with open weights due November 4.**

**What You Need to Know:** Moonshot released Kimi K3.1 Pro, a 2.8T-parameter MoE model with 104B active parameters and 1M context that reaches near-frontier results on coding and agent benchmarks while promising open weights on November 4. NVIDIA released Nemotron 3.5 Bolt E4B, an 8B/4B-effective small model post-trained from Gemma 4 E4B for local voice agents, game characters, and robots on 4GB VRAM hardware. Kyutai released CADRE, a family of causal diffusion video autoencoders that enable 20 fps world models with under 230 ms reaction latency on a single H100.
---
### Top Story
Moonshot released Kimi K3.1 Pro, a multimodal 2.8T-parameter MoE model with 104B active parameters and a 1M-token context window. The model is a post-trained version of Kimi K3 that applies large-scale joint RL across hundreds of domains after optimizing the RL framework, long-context inference, sandbox infrastructure, and rollout scheduling. It reports 65.7% on Terminal-Bench 4.0, 51.7 on SWE-Marathon, and 64.4 on OfficeQA Pro v2 while matching or exceeding Claude Opus 5.5 and GPT-6 Astra on several coding and finance tasks. API access is live today with a Highspeed variant that generates 2–3× faster at twice the price; full weights are scheduled for release on November 4. Pricing stands at $2 per million input tokens and $10 per million output tokens, matching GPT-6.1 Sol and half the cost of Claude Opus 5.5. Artificial Analysis scored the model at 55, ahead of Claude Fable 5.1, GPT-6 Astra, and Gemini 4 Argon. Moonshot also shipped Kimi Hosted Agents, a managed harness offering 24/7 execution for long-running multi-agent work. Builders working on long-horizon coding agents or financial modeling should test the standard and Highspeed endpoints now while the open weights are still weeks away. Source: [latent.space](https://latent.space/p/ainews-kimi-31/)
---
### Model Updates
**NVIDIA Releases Nemotron 3.5 Bolt E4B 4GB: An Open Small Language Model for Local Voice Agents, Game Characters and Robots: MarkTechPost**
NVIDIA released Nemotron 3.5 Bolt E4B, an 8B-total / 4B-effective model post-trained from Gemma 4 E4B using only RLVR and RLHF. It targets local voice assistants, game NPCs, and robot interfaces on RTX, Jetson, and Spark hardware with a 64K context window. The Q4_K_M build uses 3.1–4.3 GB VRAM and tops 15 of 21 benchmarks against Gemma 4 E4B and Qwen3.5-4B, including 84.8 on IHEval. The research team skipped supervised fine-tuning because it improved tool calling but hurt conversational quality and verbosity; instead they ran every training sample in both reasoning and non-reasoning modes while keeping a 2:1 ratio of non-reasoning to reasoning samples and applying length penalties inside the GenRM environment. The release ships a DFlash drafter for speculative decoding along with public datasets and the full training recipe. A Reachy Mini robot demo on Jetson Orin Nano pairs the model with Cosmos 3 Edge for vision while Bolt handles speech replies and tool calls. Source: [marktechpost.com](https://www.marktechpost.com/2026/10/23/nvidia-nemotron-3-5-bolt-e4b-4gb/)

**Kyutai CADRE: Video Autoencoders That Cut World Model Lag Below 230 ms: MarkTechPost**
Kyutai released CADRE, a family of seven open causal diffusion video autoencoders for interactive world models. Models built on CADRE run at 20 fps on one H100 and react in under 230 ms. Source: [marktechpost.com](https://www.marktechpost.com/2026/10/23/kyutai-cadre-video-autoencoders-interactive-world-models/)

**Deepseek's latest AI model is smarter than ever, but its low running costs come at a price — uses only one-quarter of the HBM and one-eighth of SSD storage but still battles hallucinations in agentic workloads: Tom's Hardware**
DeepSeek released a new open-weight model that uses one-quarter the HBM and one-eighth the SSD storage of prior versions while maintaining higher intelligence. The model shows increased hallucination rates in agentic workloads compared with proprietary frontier systems. Source: [tomshardware.com](https://www.tomshardware.com/tech-industry/artificial-intelligence/deepseeks-latest-ai-model-is-smarter-than-ever-but-its-low-running-costs-come-at-a-price-open-weight-model-is-fit-for-agentic-workloads-but-is-more-prone-to-hallucination-than-proprietary-competitors)
---
### Agent & Tool Developments
**Ramp builds AI agent harness Laminar in six weeks for internal use: TechGig**
Ramp built and deployed Laminar, an internal AI agent harness, in six weeks to manage its own agent workflows. The harness supports multi-agent collaboration and long-running execution. Source: [techgig.com](https://techgig.com/news/ai/ramp-builds-ai-agent-harness-laminar-in-six-weeks-for-internal-use/135137662)

**Anthropic targets Muse and Dots with new AI agent, Claude Duet: Computerworld**
Anthropic released Claude Duet, a new agent aimed at competing with Muse and Dots on agentic tasks. The agent focuses on multi-step tool use and planning. Source: [computerworld.com](https://www.computerworld.com/article/4239880/anthropic-challenges-muse-and-dots-with-its-new-ai-agent-claude-duet.html)

**Researchers Discover Autonomous AI Agents Inventing Novel Games When Left Idle Without Tasks: OODA Loop**
Researchers observed autonomous AI agents spontaneously inventing novel games when given no explicit tasks. The behavior emerged in sandbox environments without human-specified goals. Source: [oodaloop.com](https://oodaloop.com/briefs/technology/researchers-discover-autonomous-ai-agents-inventing-novel-games-when-left-idle-without-tasks/)
---
### Practical & Community
**Purdue University Northwest Provides First-Year Students Google Gemini Licenses to Support Artificial Intelligence Literacy: Purdue University Northwest**
Purdue University Northwest is giving all first-year students Google Gemini licenses for the 2026-27 year as part of an AI literacy pilot that will become a graduation requirement. The program runs through Purdue’s partnership with Google Public Sector and serves as a pilot for an AI competency requirement that Purdue West Lafayette already introduced for its incoming fall 2026 class. Chancellor Kenneth C. Holford noted that preparing students for an AI-driven workforce is a top priority and that graduates must understand how to use these tools effectively, ethically, and responsibly. Source: [pnw.edu](https://www.pnw.edu/purdue-university-northwest-provides-first-year-students-google-gemini-licenses-to-support-artificial-intelligence-literacy/)

**More notes on Kimi K3.1 open weights model: Simon Willison (AI builder)**
Simon Willison tested Kimi K3.1 Pro via the Moonshot API at three reasoning levels and shared output examples alongside pricing of $2/$10 per million tokens. The model scored 55 on Artificial Analysis, ahead of Claude Fable 5.1, GPT-6 Astra, and Gemini 4 Argon. He added the llm openai endpoint command to LLM 0.32 in August to run prompts against any OpenAI-compatible endpoint while saving reasoning traces to separate files. Source: [simonwillison.net](https://simonwillison.net/2026/Oct/23/kimi-k31-pro/)

**Quick Study: Simon Willison (2026-10-23)**
Simon Willison released a Quick Study prompt that uses Sobel edge detection and a canvas element to rapidly paint versions of uploaded photos inside Claude Opus 5.5. The artifact requires no external libraries beyond Google Fonts and builds on an earlier experiment that simulated watercolor illustration with P5.js. Source: [simonwillison.net](https://simonwillison.net/2026/Oct/23/quick-study-painter/)
---
### Also Today
**OpenAI Finds Brotli Vulnerability in Red-Teaming Exercise: [@OpenAI](https://x.com/OpenAI) (X)**: OpenAI discovered an unauthenticated remote code execution flaw in the Brotli compression library during red-teaming and disclosed it, leading to patches in Node.js, Bun, Envoy, and a new Brotli release. Source: [x.com](https://x.com/OpenAI/status/2113766354386084338)

**OpenAI to Train AI Models Without Internet After Cyber Incidents: Bloomberg.com**: OpenAI will train frontier models in fully offline environments following recent cyber incidents. Source: [blogger.com](https://www.blogger.com/news/articles/2026-10-23/openai-to-train-ai-models-without-internet-after-cyber-incidents)

**BBVA and NVIDIA explore AI agent security: The Paypers**: BBVA and NVIDIA are jointly exploring security architectures for AI agents. Source: [thepaypers.com](https://thepaypers.com/fraud-and-fincrime/news/bbva-teams-up-with-nvidia-to-explore-ai-agent-security-architecture)

**Agencies Urge AI Agent Access Limits, Weigh Human Oversight: MeriTalk**: U.S. agencies are recommending strict access limits and human oversight requirements for AI agents. Source: [meritalk.com](https://www.meritalk.com/articles/agencies-urge-ai-agent-access-limits-weigh-human-oversight/)
---
### Under the Hood: Frontend-Backend Tool Calling for Full-Duplex Speech Models
Pure end-to-end speech-to-speech models lack discrete tokens for structured tool calls, so most production voice agents still split the work. A frontend duplex speech-to-text model listens and emits a delegation token when it detects a tool need, then streams the ASR transcript to a separate text LLM backend that actually executes the function call. Tool results return through a lightweight prefill-and-repeat path that the frontend synthesizes into spoken audio without breaking the natural turn-taking rhythm. The split adds roughly 50–100 ms of coordination latency but preserves full interruption handling and lets teams swap in any text LLM for tool logic. Full-duplex benchmarks show the architecture reaching 92–97 % tool-call recall while keeping end-to-end audio latency under 800 ms on current hardware. A cascaded streaming pipeline using Deepgram for STT, vLLM-served LLMs with function calling, and ElevenLabs for TTS measured 755 ms time-to-first-audio in best-case tests. The modular design also supports Monte Carlo sampling for Shapley-value analysis across hundreds of agent-tool configurations on benchmarks such as MMAU and MMAR. Teams should adopt the frontend-backend pattern whenever the agent must call external APIs or maintain compliance logs; pure end-to-end models remain preferable only for simple conversational voice where no external state is required.
---
### Things to Try This Week
- Try the Kimi K3.1 Pro Highspeed API endpoint for long-horizon coding tasks where 2–3× faster generation at double price is acceptable.
- Download and quantize Nemotron 3.5 Bolt E4B to Q4_K_M and run it locally on an RTX 4060 or Jetson Orin Nano for voice-agent prototypes that fit in 4 GB VRAM.
- Test Kyutai CADRE autoencoders if you are building interactive world models that need sub-230 ms visual reactivity on a single H100.
- Run the Quick Study canvas prompt inside Claude Opus 5.5 to explore rapid image-to-painting workflows without external libraries.
---
### On the Horizon
- Kimi K3.1 Pro full open weights scheduled for release on November 4, 2026.
- Continued rollout of offline training environments at major labs following OpenAI’s recent policy shift.
- More agent harnesses and security frameworks expected as enterprises test production multi-agent systems.
- Additional small-model releases targeting 4 GB VRAM hardware for on-device agents and robots.
