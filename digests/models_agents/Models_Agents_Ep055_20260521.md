# Models & Agents
> **A general-purpose reasoning model just disproved an 80-year-old math conjecture by finding better constructions than the square grids mathematicians expected.**

**What You Need to Know:** OpenAI announced that one of its general-purpose models solved the planar unit distance problem posed by Paul Erdős in 1946, marking the first time AI has autonomously resolved a prominent open math question. At the same time, new enterprise agent platforms from Resolve AI and Kore.ai emphasize multi-agent verification and declarative agent languages to move beyond brittle pilots. Builders should watch how general reasoning gains translate into reliable agent behavior in production.
---
### Top Story
OpenAI revealed that a general-purpose reasoning model discovered an entirely new family of constructions that outperform the square-grid patterns long assumed to be optimal for the planar unit distance problem. The result came from a model not specialized for math, showing it could maintain long chains of reasoning across distant concepts and surface previously unexplored paths. This capability directly supports the company's view that the same systems will soon accelerate work in biology, physics, and medicine while still requiring human judgment to choose problems and interpret outcomes. For developers, the milestone underscores that frontier models are moving past pattern matching toward verifiable discovery, which matters for anyone building agents that must justify decisions or explore novel solution spaces. Watch for follow-up papers and whether similar reasoning gains appear in coding or scientific tool-use benchmarks. Source: [x.com](https://x.com/OpenAI/status/2057176201782075690)
---
### Model Updates
**Gemini 3.5 Flash performance details: Demis Hassabis (DeepMind) (X)**
Demis Hassabis highlighted that Gemini 3.5 Flash outperforms the prior 3.1 Pro on coding and agentic tasks while running 4x faster than other frontier models and reaching 800 tokens per second in Antigravity. It also ships at less than half the cost of comparable systems, with a Pro variant still coming. Builders working on latency-sensitive agents or high-volume coding workflows should test it immediately in the Gemini app or Antigravity. Source: [x.com](https://x.com/demishassabis/status/2056904067406860545)

**More Gemini 3.5 Flash information: Demis Hassabis (DeepMind) (X)**
Hassabis pointed to the official Google blog post for deeper technical details on the new Flash model. The release continues Google’s push to deliver faster, cheaper inference optimized for agent workloads. Source: [x.com](https://x.com/demishassabis/status/2056904072012145102)
---
### Agent & Tool Developments
**Resolve AI multi-agent investigation system: VentureBeat**
Resolve AI expanded its platform with a coordinated team of specialized agents that pursue multiple hypotheses in parallel, cross-verify conclusions, and build full causal chains for production incidents. The new architecture reportedly doubles root-cause accuracy on internal benchmarks and includes always-on background agents plus a shared workspace for human-agent collaboration. Engineering teams can integrate it via REST API or MCP server and pay only for actual troubleshooting work. Source: [venturebeat.com](https://venturebeat.com/technology/resolve-ai-says-the-ai-coding-boom-is-breaking-production-systems-it-wants-to-fix-that)

**Kore.ai Artemis agent platform: VentureBeat**
Kore.ai launched the Artemis edition of its Agent Platform, centered on a YAML-based Agent Blueprint Language and an AI architect called Arch that translates natural-language requirements into deployable, governed multi-agent systems. The platform uses a Dual-Brain Architecture that pairs LLM reasoning with deterministic business-rule execution and supports 175 models across clouds and on-premises. Existing customers are already planning migrations while new deployments start on the updated stack. Source: [venturebeat.com](https://venturebeat.com/technology/kore-ai-launches-artemis-ai-agent-platform-expands-challenge-to-microsoft-and-salesforce)

**Rippletide decision context graphs: VentureBeat**
Rippletide introduced decision context graphs that give agents structured memory, time-aware reasoning, and explicit decision logic so they become non-regressive and can compound validated action sequences over time. The approach encodes applicability rules and temporal validity directly rather than relying on the model to infer them, addressing a core failure mode in enterprise RAG-based agents. Source: [venturebeat.com](https://venturebeat.com/orchestration/enterprise-ai-agents-keep-failing-because-they-forget-what-they-learned)
---
### Practical & Community
**LlamaStation v0.9: r/LocalLLaMA**
LlamaStation is a Windows GUI that launches llama-server directly with full parameter control, supporting multiple backends including official llama.cpp with MTP, TurboQuant for high-context KV cache quantization, and voice features via XTTS and faster-whisper. Users report strong results running Qwen3.6 27B at 177k context on dual RTX 3060 cards while retaining real-time VRAM monitoring and per-model profiles. The project is open source under MIT and accepts contributions for Linux/Mac ports. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tjm58w/llamastation_v09_llamacpp_gui_for_windows_with/)

**LLM planner hardware and model guide: r/LocalLLaMA**
The LLM planner site helps users match rigs to models or models to existing hardware across 60+ builds and 50+ models, citing 130+ tok/s sources and linking 150+ reviewer videos. It includes decode and prompt-processing speeds at multiple quants, power draw, and multi-region pricing with weekly updates. The tool is useful when deciding between upcoming GPUs or evaluating open-weight options against closed frontier ceilings. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tjm1uk/llm_planner_pick_a_rig_for_your/)

**Local Llama 3 web search options: r/LocalLLaMA**
A user running Llama 3 70B locally with function calling is seeking cheap or free APIs that return useful webpage chunks instead of short snippets after SearXNG and Brave Search proved insufficient. The thread surfaces practical trade-offs between context quality and cost for local agent setups. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tjmdc8/whats_the_cheapest_way_to_give_a_local_llama_3/)
---
### Under the Hood: Multi-agent verification loops
Everyone talks about multi-agent systems as if simply adding more models will automatically improve reliability. In practice, verification works through explicit hand-off protocols where one agent must cite every evidence fragment it used and another agent is tasked with attempting to disprove the proposed causal chain. This adds measurable latency—often 200–400 ms per verification round—but dramatically reduces confident but unsupported conclusions on complex incidents. The key engineering choice is deciding how many independent hypotheses to explore in parallel versus how deeply to verify each one; teams that over-verify see diminishing returns once accuracy plateaus around 85–90 % on their internal eval sets. When the cost of a wrong root cause is high, the architecture shines; when speed matters more than perfect explanations, a single well-prompted agent with strong retrieval still wins. The gotcha that bites most teams is forgetting to let agents explicitly say “I do not have enough evidence,” which turns the system back into a confident hallucinator.
---
### Things to Try This Week
- Test Gemini 3.5 Flash in the Gemini app or Antigravity for coding and agentic tasks to see the reported 4x speed and sub-half-cost gains firsthand.
- Spin up LlamaStation v0.9 if you run llama.cpp on Windows and want full parameter control plus TurboQuant high-context support without command-line overhead.
- Experiment with Resolve AI’s MCP server integration so your existing coding agents can hand off production debugging to the multi-agent investigation system.
- Explore Kore.ai’s Artemis platform on Azure if you need declarative agent definitions that combine LLM reasoning with deterministic business rules for regulated environments.
- Compare the Rippletide decision context graph approach against plain RAG when building agents that must respect time-scoped policies and avoid regression on repeated tasks.
---
### On the Horizon
- OpenAI is expected to release further details and papers on the general-purpose reasoning techniques behind the Erdős result.
- Google will continue rolling out Gemini 3.5 Flash capabilities and the promised Pro variant.
- More enterprise agent platforms are likely to announce MCP and REST interoperability as the pattern becomes standard for agent-to-agent handoff.
- Hardware vendors and open-source projects will keep shipping new backends and quantization methods aimed at 100k+ context on consumer GPUs.