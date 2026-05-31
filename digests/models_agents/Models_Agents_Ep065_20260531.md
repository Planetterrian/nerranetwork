# Models & Agents — Weekly Recap
> **Looking back at 6 episodes from 2026-05-25 to 2026-05-31 — the stories that mattered, what we learned, and what to watch next.**
---
### This Week's Top Stories

1. **From Ep 59 (2026-05-25): Datasette's new slash-key jump menu now launches agent conversations directly from your databases.**
   **What You Need to Know:** Simon Willison shipped Datasette 1.0a30 with a keyboard-driven "jump to" menu that plugins can extend, plus a datasette-agent plugin that adds a conversation starter form. NuExtract3, a new 4B vision-language model, arrived on Hugging Face for structured extraction and Markdown conversion from documents. Builders should watch how these small, targeted releases lower the friction for mixing data exploration with agent workflows this week.
---
### Top Story
Datasette 1.0a30 introduces a "jump to" menu triggered by the "/" keyboard shortcut that lets users type to reach databases, tables, or canned queries. The release includes plugin hooks so extensions can inject additional content into the menu and its empty state. The datasette-agent plugin uses this hook to surface a form that starts a new agent conversation, with a live demo available at agent.datasette.io after GitHub sign-in. More implementation details appear on the Datasette blog. The change turns a da

2. **From Ep 60 (2026-05-26): What You Need to Know:**
   **What You Need to Know:** A new paper formalizes SkillOpt, using frontier models to propose bounded edits to markdown skills and accepting only those that improve a held-out validation set. Qwen3.5 and Qwen3.6 receive new uncensored and diffusion variants with detailed training notes for consumer hardware. Practical local setups gain concrete guidance on llama.cpp server flags, Intel NPU ASR, and MacBook stability tweaks. Builders should watch how validation-gated skill optimization and KV cache techniques change agent reliability this week.
---
### Top Story
SkillOpt turns ad-hoc markdown skill files into trainable parameters by using a frontier model to propose bounded add/delete/replace edits, then gating every change against a held-out validation set that only accepts strict improvements. Best skills converge after just 1–4 accepted edits out of many proposals, with an edit budget of 4–8 working best; removing the cap collapses performance. A skill optimized on Codex transferred t

3. **From Ep 61 (2026-05-27): What You Need to Know:**
   **What You Need to Know:** Anthropic released a detailed engineering post on how they contain Claude agents through evolving access controls and sandbox limits. EAGLE 3.1 fixes attention drift in speculative decoding for more stable production inference. Several new agent frameworks and training methods for reasoning agents also dropped today.
---
### Top Story
Anthropic published a new engineering blog post detailing their approach to sandboxing AI agents. The post explains that permissions must evolve alongside agent capabilities, with sandboxing used to limit the scope of potentially destructive actions in their products. This provides practical guidance on containing agents as they gain more autonomy rather than relying on static rules. Builders working with tool-using agents can apply these patterns to reduce risk when granting file system, network, or code execution access. The approach emphasizes starting with narrow permissions and expanding them only as the agent's demonstrate

4. **From Ep 62 (2026-05-28): What You Need to Know:**
   **What You Need to Know:** CoreWeave launched a unified agentic platform that closes the training-to-inference gap for continuous autonomous improvement. Perplexity open-sourced a Unigram tokenizer that cuts reranker latency 5x versus Hugging Face. Multiple teams showed practical Qwen3.6-35B-A3B inference on single consumer GPUs with strong context handling. Builders should watch how these infrastructure and tooling shifts affect agent deployment costs this week.
---
### Top Story
CoreWeave launched a unified agentic AI platform that enables continuous autonomous agent improvement by closing the training-to-inference gap. The system supports self-improvement loops where agents can iterate on their own outputs without requiring full retraining cycles. It targets production workloads where agents need to adapt in real time rather than waiting for scheduled fine-tuning runs. Teams building long-running autonomous systems can now test tighter feedback loops between inference results and mo

5. **From Ep 63 (2026-05-29): What You Need to Know:**
   **What You Need to Know:** Liquid AI shipped LFM2.5-8B-A1B with 128K context and 38T pre-training tokens for edge devices. A new monokernel on AMD MI300X hits 3,300 output tokens/s for small models. Researchers released RightNow-Arabic-0.5B-Turbo and Aryabhata 2, while local builders are shifting agents to HTML rendering for diagrams and structured output.
---
### Top Story
Anthropic announced a $65 billion Series H round at a $965 billion post-money valuation led by Altimeter, Dragoneer, Greenoaks, and Sequoia. The company separately disclosed that its run-rate revenue crossed $47 billion earlier this month, driven by enterprise deployments of Claude and everyday usage. This capital will expand research and inference capacity to meet demand. The round underscores how quickly production usage of frontier models is growing across industries. Builders should watch how the added resources translate into Claude availability and new capabilities in the coming months. Source: [x.com](https:/

6. **From Ep 64 (2026-05-30): Windows users can now steer Codex agents directly on their machines while stepping away.**
   **What You Need to Know:** OpenAI extended computer-use capabilities to Windows for Codex, letting the agent act on local desktops and continue tasks from the mobile app. StepFun released a 198B MoE vision-language model optimized for coding agents, while Hermes Agent added tool search to reduce MCP context bloat. Builders should test the new Windows support this week and evaluate the MeMo memory architecture for long-term knowledge updates without retraining.
---
### Top Story
OpenAI added Windows support for Codex computer use, allowing the agent to perform actions directly on Windows machines and continue tasks started from the ChatGPT mobile app. The feature enables users to start, review, and steer work remotely while the agent keeps running locally. This expands Codex beyond macOS and browser environments, giving developers a path to run autonomous coding sessions on standard Windows hardware. Early access means reliability is still limited and users should expect iteration on ed
---
## Recap framing for the host

This is a Sunday weekly recap. The host should weave the stories above into a single coherent narrative — not a list of news items. Group related threads, call out the most consequential development of the week, draw forward connections ("what to watch next week"), and end with one practical takeaway listeners can use. Keep the same voice and pacing as a daily episode.

### MODELS & AGENTS PROGRAM NARRATIVE MEMORY
Use this to give regular listeners a sense of ongoing stories and real progress (or the lack of it).
When a story touches one of these programs, include 1-2 natural sentences answering:
  - Where does today's development fit in the bigger arc for this program?
  - Does it meaningfully move any of the key open questions?
  - What should attentive listeners be watching for next?

Tracked programs (with current status and open questions):

**Frontier Models**
Current status: Closed frontier models (GPT, Claude, Gemini, Grok) trading capability and price leads.
Key open questions the show is following:
  - Next frontier release cadence
  - Capability gains vs cost trajectory

**Open-Weight Models**
Current status: Open-weight families (Llama, Mistral, Qwen, DeepSeek, Gemma) narrowing the gap with closed frontier.
Key open questions the show is following:
  - Open vs closed performance gap
  - Licensing / commercial terms

**Agents & Tool Use**
Current status: Autonomous agents, tool use, and the MCP / interoperability layer maturing.
Key open questions the show is following:
  - Reliability of long-horizon agents
  - Standardization of agent/tool protocols

**Reasoning Models**
Current status: Reasoning / 'thinking' models and test-time compute.
Key open questions the show is following:
  - Reasoning cost vs benefit
  - Benchmark gains vs real-world value

**AI Compute & Inference**
Current status: AI hardware and inference economics (NVIDIA, custom silicon, falling token costs).
Key open questions the show is following:
  - Inference cost curve
  - Compute supply constraints

**Safety & Policy**
Current status: AI safety, evaluation, and regulation.
Key open questions the show is following:
  - US/EU regulatory trajectory
  - Evaluation / safety standardization

--- End of narrative memory ---

Use the narrative status above to highlight meaningful progress or open questions across the week.