# Models & Agents — Weekly Recap
> **Looking back at 6 episodes from 2026-05-18 to 2026-05-24 — the stories that mattered, what we learned, and what to watch next.**
---
### This Week's Top Stories

1. **From Ep 52 (2026-05-18): What You Need to Know:**
   **What You Need to Know:** NVIDIA released a full 4-bit pretraining stack (NVFP4) that was validated on a 12B Mamba-Transformer trained for 10 trillion tokens. The approach combines selective BF16 layers, Hadamard transforms, and stochastic rounding to stay within 0.04 points of an FP8 baseline on MMLU-Pro. Builders training long-horizon models on limited hardware should watch how this scales beyond the 12B proof-of-concept.
---
### Top Story
NVIDIA introduced a complete 4-bit pretraining methodology built around the NVFP4 microscaling format. The stack uses selective BF16 layers for critical weights, 16×16 Random Hadamard Transforms on gradients, 2D weight scaling, and stochastic rounding. It was validated on a 12B hybrid Mamba-Transformer trained across 10 trillion tokens—the longest publicly reported 4-bit pretraining run to date. Downstream accuracy stayed within 0.04 points of the FP8 baseline (62.58% vs 62.62% on MMLU-Pro). Teams running extended pretraining on constrained GPU fl

2. **From Ep 53 (2026-05-19): What You Need to Know:**
   **What You Need to Know:** Anthropic acquired StainlessAPI, the platform behind every Anthropic SDK since the API's earliest days, to accelerate SDK and MCP server development. Alibaba previewed new Qwen models that currently rank as the top Chinese entries on the LMSYS Arena. Enterprise teams now have clearer guidance on moving agentic platforms from pilot to production, while researchers released concrete scaling laws for skill libraries in agent systems.
---
### Top Story
Anthropic announced it is acquiring StainlessAPI, the SDK and MCP server platform that has powered every Anthropic SDK since the API launched. The move gives Anthropic direct control over the tooling developers use to integrate Claude models, including support for the Model Context Protocol that many agent frameworks now rely on. StainlessAPI previously operated as an independent service used across multiple labs, so the acquisition centralizes expertise that previously sat outside Anthropic's walls. Developers bui

3. **From Ep 54 (2026-05-20): What You Need to Know:**
   **What You Need to Know:** Google released Gemini 3.5 Flash today, claiming it outperforms the prior 3.1 Pro on coding and agentic work, runs 4x faster than other frontier models, and delivers up to 800 tokens/sec inside Antigravity. Alibaba simultaneously shipped Qwen3.5-LiveTranslate-Flash for low-latency multimodal translation across 60 languages. Developers should test both models this week for agent pipelines and real-time voice/video workflows.
---
### Top Story
Google introduced Gemini 3.5 Flash at I/O 2026 as a faster, lower-cost model optimized for AI agents and coding workloads. It reportedly beats the previous 3.1 Pro on those benchmarks while running four times faster than competing frontier models and at roughly half the cost. Early users inside Antigravity are seeing 12x speedups and 800 tokens per second. The model is already available in the Gemini App and Antigravity, with a full Pro variant promised soon. Builders working on agentic systems or high-volume coding tools

4. **From Ep 55 (2026-05-21): What You Need to Know:**
   **What You Need to Know:** OpenAI announced that one of its general-purpose models solved the planar unit distance problem posed by Paul Erdős in 1946, marking the first time AI has autonomously resolved a prominent open math question. At the same time, new enterprise agent platforms from Resolve AI and Kore.ai emphasize multi-agent verification and declarative agent languages to move beyond brittle pilots. Builders should watch how general reasoning gains translate into reliable agent behavior in production.
---
### Top Story
OpenAI revealed that a general-purpose reasoning model discovered an entirely new family of constructions that outperform the square-grid patterns long assumed to be optimal for the planar unit distance problem. The result came from a model not specialized for math, showing it could maintain long chains of reasoning across distant concepts and surface previously unexplored paths. This capability directly supports the company's view that the same systems will soon

5. **From Ep 56 (2026-05-22): What You Need to Know:**
   **What You Need to Know:** OpenAI shipped several Codex updates today including secure computer use on locked Macs, Goal mode for hours-long autonomous work, and advanced annotation tools. Microsoft released Fara1.5, a family of browser agents that beat OpenAI Operator and Gemini 2.5 on web tasks. Developers should watch how these agent capabilities integrate into existing workflows this week.
---
### Top Story
OpenAI announced new Codex features today including secure Mac computer use, Goal mode, and advanced annotation. Codex can now control apps on a locked Mac from your phone with the screen off, while Goal mode lets users set objectives that run for hours or days across the app, IDE extension, and CLI. Advanced annotation mode allows direct visual edits to web pages during feedback sessions. These changes make Codex significantly more hands-off compared to previous interactive coding tools. Builders working on automation or remote workflows should test Goal mode immediately to see

6. **From Ep 57 (2026-05-23): What You Need to Know:**
   **What You Need to Know:** OpenAI rolled out Goal mode, Appshots, and advanced annotation in Codex across app, IDE, and CLI. Anthropic reported finding over 10,000 high-severity vulnerabilities through Project Glasswing using Claude models. Multiple new open-source releases focus on faster inference and smaller footprints for consumer hardware.
---
### Top Story
OpenAI announced Goal mode, Appshots for screen context, and advanced annotation capabilities for Codex. Goal mode lets users set objectives that the system pursues for hours or days with reduced intervention, available in the app, IDE extension, and CLI. Appshots pull live screen content directly into the agent session, while the annotation mode supports direct visual feedback on web pages. These updates shift Codex from reactive chat toward longer-running, context-rich agent workflows. Builders working on coding automation or multi-step development tasks should test the new modes this week to see how hands-off execution perfo
---
## Recap framing for the host

This is a Sunday weekly recap. The host should weave the stories above into a single coherent narrative — not a list of news items. Group related threads, call out the most consequential development of the week, draw forward connections ("what to watch next week"), and end with one practical takeaway listeners can use. Keep the same voice and pacing as a daily episode.