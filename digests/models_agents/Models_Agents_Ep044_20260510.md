# Models & Agents — Weekly Recap
> **Looking back at 4 episodes from 2026-05-04 to 2026-05-10 — the stories that mattered, what we learned, and what to watch next.**
---
### This Week's Top Stories

1. **From Ep 40 (2026-05-05): OpenAI gives 8,000 developers a month of 10x Codex rate limits after the GPT-5.5 party sold out.**
   **What You Need to Know:** OpenAI turned its oversubscribed GPT-5.5 developer party into a broad rate-limit giveaway that runs through June 5, giving thousands of builders dramatically more room to experiment with its coding agent. DeepSeek V4 Pro just tied recent GPT-5.2 performance on a 30-day persistent-memory food-truck benchmark while running roughly 17× cheaper. Meanwhile, a ggml port of Microsoft’s VibeVoice brings CPU/CUDA/Metal TTS and long-form ASR with diarization to a single binary with no Python at inference time.
---
### Top Story
OpenAI began emailing more than 8,000 developers who applied for its invite-only “GPT-5.5 on 5/5” party with an immediate 10× increase in Codex rate limits on their personal ChatGPT accounts, valid through June 5. The move applies to everyone who signed up—accepted, waitlisted, or rejected—after demand overwhelmed the original venue capacity. Codex itself reportedly handled registration and even suggested the May 5 date and format for the low-ke

2. **From Ep 41 (2026-05-06): What You Need to Know:**
   **What You Need to Know:** OpenAI is pushing GPT-5.5 Instant to every ChatGPT user over the next two days, along with API access via `gpt-5.5-chat-latest` and improved memory/personalization for Plus/Pro plans. Anthropic published new research on Model Spec Midtraining showing how pre-training on detailed constitutions improves safety generalization in agentic settings. Google released MTP Drafters that deliver up to 3x faster Gemma 4 inference without quality loss, while a detailed community benchmark explores practical quantization tradeoffs for Qwen 3.6 27B.
---
### Top Story
OpenAI is rolling out GPT-5.5 Instant as the default model for all ChatGPT users over the next two days, with the same model available in the API as `gpt-5.5-chat-latest`. The lighter variant brings measurable gains in factuality (especially medicine, law, and finance), image analysis, STEM question answering, and knowing when to trigger web search. It also ships with improved memory that pulls context from sav

3. **From Ep 42 (2026-05-08): What You Need to Know:**
   **What You Need to Know:** OpenAI released GPT-Realtime-2, GPT-Realtime-Translate, and GPT-Realtime-Whisper through the Realtime API, targeting live voice reasoning, 70+ language translation, and streaming transcription. This builds directly on earlier voice mode limitations that Simon Willison noted still feel dated. Watch how developers integrate these into agent workflows this week.
---
### Top Story
OpenAI released three purpose-built audio models—GPT-Realtime-2, GPT-Realtime-Translate, and GPT-Realtime-Whisper—into the Realtime API. GPT-Realtime-2 focuses on reasoning agents with live voice, GPT-Realtime-Translate handles speech-to-speech across more than 70 languages, and GPT-Realtime-Whisper delivers streaming transcription. These sit alongside existing Realtime API endpoints rather than replacing the base GPT models, giving developers granular control over audio pipelines without routing everything through a single generalist model. Teams building voice agents or real-time cust

4. **From Ep 43 (2026-05-09): What You Need to Know:**
   **What You Need to Know:** DeepSeek released the complete V4 technical paper detailing FP4 QAT, anticipatory routing for training stability, and generative reward modeling. Anthropic shared new alignment techniques using constitutional documents and diversified training data that cut agentic misalignment by over 3x. OpenAI published updates on automated detection systems to prevent CoT grading during RL. Caliby, a new embedded vector database, launched with strong disk performance for agent memory use cases.
---
### Top Story
DeepSeek dropped the full V4 paper this week, expanding the April preview with detailed sections on FP4 quantization-aware training applied directly in late-stage training for its trillion-parameter MoE. The approach quantizes expert weights to FP4—the primary GPU memory consumer—while keeping the QK path in the CSA indexer on FP4 activations, delivering a 2x speedup on the QK selector at 99.7% recall. Two stability mechanisms address loss spikes in large MoE trai
---
## Recap framing for the host

This is a Sunday weekly recap. The host should weave the stories above into a single coherent narrative — not a list of news items. Group related threads, call out the most consequential development of the week, draw forward connections ("what to watch next week"), and end with one practical takeaway listeners can use. Keep the same voice and pacing as a daily episode.