# Models & Agents
> **Codex just landed on your phone — OpenAI’s coding agent now runs natively on iOS and Android with Windows sync coming soon.**

**What You Need to Know:** OpenAI rolled out a preview of Codex in the ChatGPT mobile apps today, letting developers work with the agent from anywhere. Anthropic released both a new US-China AI leadership paper and a $200M Gates Foundation partnership for global health and education. Local builders are pushing DeepSeek V4 Pro and multi-agent setups to new performance levels on consumer hardware.
---
### Top Story
OpenAI began rolling out Codex as a native preview on iOS and Android in all supported regions. The mobile version supports full agent workflows with phone-to-Windows desktop connection arriving shortly. This moves Codex from desktop-bound tool to always-available coding partner, matching the reach of consumer chat apps. Developers can now trigger complex code tasks while commuting or traveling without switching devices. Watch for expanded Windows integration and potential API exposure for custom mobile tools. Source: [openai.com](https://openai.com/index/work-with-codex-from-anywhere/)
---
### Model Updates
**Supertone Supertonic v3: Source MarkTechPost**
Supertone shipped the third generation of its on-device TTS engine with support for 31 languages, expression tags, and fewer reading failures. The inference contract stays unchanged for existing integrations while language coverage jumps 6×. Builders working on multilingual voice agents gain a drop-in upgrade that runs locally without extra latency.

**VectraYX-Nano: Source arXiv**
A new 42M-parameter Spanish cybersecurity model trained from scratch with native MCP tool calling. It uses a curriculum pipeline on a 170M-token Spanish corpus and ships as an 81 MB GGUF that runs sub-second on commodity hardware. Early adopters get the first Spanish-native cybersecurity LLM with end-to-end tool use.

**Physics-R1: Source arXiv**
A new visual physics reasoning model cold-started from Qwen3-VL-8B-Thinking using audited olympiad data. It lifts performance +18.3 pp on held-out olympiad problems and +15.7 pp on physics reasoning benchmarks over the base 8B model. The release includes cleaned corpora and a reproducible GSPO+DAPO recipe.
---
### Agent & Tool Developments
**WSPN W Agent: Source PR Newswire**
WSPN launched a stablecoin payment skill designed specifically for the AI agent economy. The agent can execute payments autonomously while maintaining compliance hooks. Developers building agentic commerce flows can integrate it as a ready-made payment primitive.

**MediaTek Dimensity Platform: Source Pandaily**
MediaTek positioned its Dimensity chips as the hardware foundation for smartphone AI agents. The platform targets on-device agent inference with optimized NPU support. Mobile developers should test current agent workloads on Dimensity devices to benchmark power and latency.

**Amazon Shopping Agent: Source AD HOC NEWS**
Amazon deployed an AI agent that can shop on behalf of users, backed by its growing satellite constellation for global connectivity. The agent handles end-to-end purchase flows. Retail and logistics teams should monitor how this changes agent-to-commerce integration patterns.
---
### Practical & Community
**Multi-Agent Qwen Setup: Source r/LocalLLaMA**
A builder demonstrated four parallel Qwen3.6 35B sub-agents orchestrated by DeepSeek on dual RTX 3090s. Local reviewers plus a cloud final pass keep API spend under $20/month. The full opencode.json config is shared for anyone replicating the pattern.

**DeepSeek V4 Pro Local Optimization: Source r/LocalLLaMA**
A user achieved 45+ tokens/s prompt processing on DeepSeek V4 Pro using ktransformers with Epyc + RTX PRO 6000 hardware. Context scaling to 32k showed stable throughput with ~100W GPU draw. The setup runs original model files with no conversion required.

**China Modded GPUs: Source r/LocalLLaMA**
Community discussion is growing around 48 GB 4090-class cards sourced from China. Builders are seeking reliable benchmarks, BIOS quirks, and long-term stability data. Anyone considering these cards should join the shared research effort before purchase.
---
### Under the Hood: Speculative Decoding Attack Surfaces
Everyone talks about speculative decoding as a simple speed boost you just turn on. In practice it rests on a fragile agreement between drafter and target model distributions. When that agreement slips even slightly, the average accepted length τ collapses and the promised 2× speedup disappears. Mistletoe-style attacks exploit exactly this gap by nudging the drafter with null-space projected gradients that preserve output semantics while tanking acceptance rates. The engineering tradeoff is stark: you gain throughput only while the drafter stays close to the target, yet any defense that hardens acceptance also adds verification latency. Most teams hit the wall when they scale context beyond 8k tokens, where drift between drafter and target grows fastest. The practical rule is to keep your drafter within one training epoch of the target and monitor τ in production; once it drops below 1.8, fall back to standard decoding rather than forcing the speculative path.
---
### Things to Try This Week
- Install the Codex preview on iOS or Android and test a multi-file refactor task while away from your desk.
- Run the new Supertonic v3 TTS locally on a multilingual voice agent project to compare reading stability against your current engine.
- Replicate the four-sub-agent Qwen setup using the shared opencode.json if you have dual 3090-class GPUs.
- Download the VectraYX-Nano GGUF and test its MCP tool-calling on a Spanish cybersecurity workflow.
- Benchmark your current agent stack against the MarkTechPost SWE-bench and Terminal-Bench numbers for Claude Code and GPT-5.5.
---
### On the Horizon
- OpenAI is expected to expand Codex Windows phone sync and expose more mobile agent APIs in the coming weeks.
- Anthropic’s US-China paper will likely spark follow-on policy discussions at upcoming AI governance events.
- More local builders are preparing 64k+ context tests for MTP models following the recent DeepSeek V4 Pro results.
- Hardware vendors are watching MediaTek’s Dimensity agent push for clues on next-generation mobile NPUs.