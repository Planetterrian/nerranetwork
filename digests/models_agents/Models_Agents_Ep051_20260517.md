# Models & Agents — Weekly Recap
> **Looking back at 6 episodes from 2026-05-11 to 2026-05-17 — the stories that mattered, what we learned, and what to watch next.**
---
### This Week's Top Stories

1. **From Ep 45 (2026-05-11): What You Need to Know:**
   **What You Need to Know:** Sakana and NVIDIA released TwELL, a sparse inference approach that uses simple L1 regularization plus custom CUDA kernels to hit over 99% sparsity in LLM feed-forward layers. The result is measured 20.5% faster inference and 21.9% faster training with negligible quality loss. Local developers should watch ExLlamaV3’s latest DFlash and quantization updates, while agent builders can explore Memori for persistent memory layers.
---
### Top Story
Sakana AI and NVIDIA introduced TwELL, a technique that applies L1 regularization to induce over 99% sparsity in the feed-forward layers of large language models. They then translate that sparsity into actual throughput gains using new sparse data formats and fused CUDA kernels. The reported speedups are 20.5% for inference and 21.9% for training while downstream performance remains essentially unchanged. This matters because most current sparsity work stays theoretical; TwELL demonstrates concrete GPU-level improvements

2. **From Ep 46 (2026-05-12): What You Need to Know:**
   **What You Need to Know:** OpenAI launched Daybreak today, an initiative that combines its latest models with an agentic coding system and partner network to automate security detection and response. Sam Altman highlighted how the new ChatGPT model, personality controls, and personalization now cross a usability threshold for many users. Meanwhile, Andrej Karpathy shared practical prompting techniques for richer LLM outputs, and several new research papers benchmarked agent behavior and multimodal embeddings.
---
### Top Story
OpenAI is launching Daybreak, a cybersecurity program that integrates frontier AI models with Codex Security, its coding-focused agentic system, and a network of security partners. The effort targets developers, enterprise teams, researchers, and government defenders who need to detect, validate, and patch software vulnerabilities earlier in the development process. Daybreak automates detection, validation, and response while respecting existing security rules an

3. **From Ep 47 (2026-05-13): What You Need to Know:**
   **What You Need to Know:** Thinking Machines Lab released TML-Interaction-Small, a 276B MoE model with 12B active parameters that processes 200ms chunks of audio, video, and text in parallel streams. ReVision cuts visual token usage by ~46% for computer-use agents while lifting success rates 3 points on OSWorld and WebTailBench. Builders should test the interaction model prototype in Google AI Studio and the ReVision patch selector on their own CUA trajectories this week.
---
### Top Story
Thinking Machines Lab released a research preview of TML-Interaction-Small, a native multimodal architecture built for continuous human-AI collaboration. The 276B-parameter MoE model activates 12B parameters and ingests synchronized 200ms chunks of audio, video, and text through a multi-stream time-aligned design, removing the need for separate voice-activity detection. A real-time interaction component maintains full-duplex exchange while an asynchronous background model handles sustained reasoning 

4. **From Ep 48 (2026-05-14): What You Need to Know:**
   **What You Need to Know:** Nous Research introduced Token Superposition Training, a two-phase method that averages token embeddings early then switches back to standard prediction. Open-source builders shipped a full cinematic video pipeline that runs end-to-end on a single AMD MI300X. New agent frameworks for belief tracking, automated evaluation, and multi-machine computer control also landed today.
---
### Top Story
Nous Research released Token Superposition Training (TST), a two-phase pre-training technique that averages contiguous token embeddings into bags during the first phase before reverting to standard next-token prediction. The approach works on dense models from 270M to 3B parameters and a 10B-A1B MoE without any architecture, tokenizer, or optimizer changes. It delivers up to 2.5x wall-clock speedups at matched FLOPs while preserving downstream performance. Teams doing continued pre-training or scratch training on mid-size models can now cut training time dramatically on 

5. **From Ep 49 (2026-05-15): What You Need to Know:**
   **What You Need to Know:** OpenAI rolled out a preview of Codex in the ChatGPT mobile apps today, letting developers work with the agent from anywhere. Anthropic released both a new US-China AI leadership paper and a $200M Gates Foundation partnership for global health and education. Local builders are pushing DeepSeek V4 Pro and multi-agent setups to new performance levels on consumer hardware.
---
### Top Story
OpenAI began rolling out Codex as a native preview on iOS and Android in all supported regions. The mobile version supports full agent workflows with phone-to-Windows desktop connection arriving shortly. This moves Codex from desktop-bound tool to always-available coding partner, matching the reach of consumer chat apps. Developers can now trigger complex code tasks while commuting or traveling without switching devices. Watch for expanded Windows integration and potential API exposure for custom mobile tools. Source: [openai.com](https://openai.com/index/work-with-codex-from-

6. **From Ep 50 (2026-05-16): An agent that manages another agent just moved from research demo to production reality at Fin.**
   **What You Need to Know:** Fin (formerly Intercom) launched Fin Operator, an AI system whose sole job is configuring, debugging, and monitoring the customer-facing Fin agent. The release highlights a practical two-layer agent architecture with human approval gates and usage-based pricing. Builders should watch how support-ops workflows shift when one agent owns the operational loop for another.
---
### Top Story
Fin announced Fin Operator, an AI agent purpose-built to manage the company's customer-facing Fin agent. Operator acts as data analyst, knowledge manager, and debugger: it generates charts from conversation metrics, ingests product PDFs to update help articles, traces failed conversations to root causes in guidance rules, and proposes fixes as reviewable diffs. It runs on Claude rather than Fin's own Apex models because the tasks resemble software-engineering work more than customer-service resolution. Every change requires explicit human approval before going live, and early b
---
## Recap framing for the host

This is a Sunday weekly recap. The host should weave the stories above into a single coherent narrative — not a list of news items. Group related threads, call out the most consequential development of the week, draw forward connections ("what to watch next week"), and end with one practical takeaway listeners can use. Keep the same voice and pacing as a daily episode.