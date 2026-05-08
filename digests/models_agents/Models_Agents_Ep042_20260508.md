# Models & Agents
> **OpenAI ships three specialized realtime audio models for voice agents, translation, and transcription.**

**What You Need to Know:** OpenAI released GPT-Realtime-2, GPT-Realtime-Translate, and GPT-Realtime-Whisper through the Realtime API, targeting live voice reasoning, 70+ language translation, and streaming transcription. This builds directly on earlier voice mode limitations that Simon Willison noted still feel dated. Watch how developers integrate these into agent workflows this week.
---
### Top Story
OpenAI released three purpose-built audio models—GPT-Realtime-2, GPT-Realtime-Translate, and GPT-Realtime-Whisper—into the Realtime API. GPT-Realtime-2 focuses on reasoning agents with live voice, GPT-Realtime-Translate handles speech-to-speech across more than 70 languages, and GPT-Realtime-Whisper delivers streaming transcription. These sit alongside existing Realtime API endpoints rather than replacing the base GPT models, giving developers granular control over audio pipelines without routing everything through a single generalist model. Teams building voice agents or real-time customer tools can now mix reasoning, translation, and transcription in one session. The release arrives while broader ChatGPT voice upgrades remain in preview, so early API users will likely see the biggest near-term gains. Expect rapid experimentation around multi-language agent conversations and background audio handling. Source: [marktechpost.com](https://www.marktechpost.com/2026/05/08/openai-releases-three-realtime-audio-models-gpt-realtime-2-gpt-realtime-translate-and-gpt-realtime-whisper-in-the-realtime-api/)
---
### Model Updates
**Gemini 3.1 Flash Lite moves out of preview: Simon Willison (AI builder)**
The non-preview gemini-3.1-flash-lite appears functionally identical to the March preview version, with unchanged pricing. It gives developers a stable, low-cost option for lighter workloads without waiting for further labeling changes. Source: [x.com](https://x.com/simonw/status/2052471470325121260)

**Sam Altman notes generational voice preferences for AI: Sam Altman (OpenAI)**
Younger users lean toward voice interaction while older users prefer typing, with middle-aged users split. This observation hints at interface design choices for future ChatGPT voice features that remain in testing.
---
### Agent & Tool Developments
**Codex gains native Chrome extension with background tabs: [@OpenAI](https://x.com/OpenAI) (X)**
The new Chrome extension lets Codex run directly in the browser on macOS and Windows, handling logged-in sites, parallel background tabs, and tasks like dashboard checks or CRM updates without hijacking the foreground window. It intelligently routes between plugins, Chrome sessions, and other tools depending on the step. Install it today from the Codex app outside the EU and UK, with wider rollout planned soon. Source: [x.com](https://x.com/OpenAI/status/2052480800004956323)

**Anthropic donates Petri alignment tool to Meridian Labs: [@AnthropicAI](https://x.com/AnthropicAI) (X)**
Anthropic open-sourced and transferred its Petri alignment testing framework to Meridian Labs, releasing a major update that boosts test adaptability, realism, and depth. Researchers can now run the improved suite independently while Anthropic shifts focus elsewhere. Source: [x.com](https://x.com/AnthropicAI/status/2052494460966019137)
---
### Practical & Community
**AWS enables USDC micropayments for AI agents via Coinbase and Stripe: Blockonomi**
AWS partnered with Coinbase and Stripe so AI agents can execute cryptocurrency payments using USDC. Developers building autonomous agents on AWS can now add on-chain settlement without custom payment infrastructure. Source: [Google News](https://news.google.com/rss/articles/CBMipwFBVV95cUxNZnNYZU1LdDQ2UzdGdEhqaGJfT2RWOUotLXRTVDF4QTNiR2RXeGlzazJac0pPUW12QXpfVkx0S2NDamUzTUd4ZzN1U0xmc2h2WjlRNFgzUTZqaFhscHlucGpYSEU4b0dYa3VHZzlMck50TTg2NE90MU5mZ180eVpJS0w3aGZ2WnJxSDhCUjhZLWdUNWJRUG9La0JXOFJoU3lJaHlRLU5zZw?oc=5)

**STAM optimizer promises more stable training than AdamW: r/LocalLLaMA**
Token AI published “Stable Training with Adaptive Momentum,” introducing STAM and its lighter STAMLite variant that dynamically adjusts beta1 based on gradient noise. STAMLite cuts optimizer state memory roughly in half versus AdamW while matching or exceeding accuracy on several long-horizon benchmarks, making it worth testing for teams training from scratch on limited GPUs. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1t6yra2/a_new_generation_of_ai_models_and_one_of_the_most/)

**MedQA fine-tuning demo runs on AMD ROCm without CUDA: Hugging Face - Blog**
A step-by-step guide shows how to fine-tune a clinical QA model on AMD hardware using ROCm. Practitioners locked into non-NVIDIA stacks now have a concrete path for domain-specific medical models. Source: [huggingface.co](https://huggingface.co/blog/lablab-ai-amd-developer-hackathon/medqa)
---
### Under the Hood: Adaptive Momentum in LLM Optimizers
Everyone treats the choice of optimizer as a simple hyperparameter swap. In practice, Adam-family methods bake in a fixed momentum decay that can drag stale gradient information forward for thousands of steps. STAM measures the residual between current gradient and running momentum at each update; when the gap spikes, it lowers beta1 on the fly so the optimizer does not keep pushing in an outdated direction. This adaptive schedule adds a small amount of per-step arithmetic but removes the need for the second full momentum buffer that AdamW keeps around, cutting optimizer state from roughly 2× model size down to 1× in the Lite variant. The quality benefit shows up most clearly on long, non-stationary training runs where data distribution shifts; above roughly 70 B parameters the relative gain shrinks because gradient noise averages out anyway. Most teams should default to STAMLite when GPU memory is the bottleneck and fall back to AdamW only if they already have heavy regularization pipelines tuned around its exact momentum behavior. The gotcha is that early training can look noisier until the adaptive schedule stabilizes, so learning-rate schedules may need a slightly longer warmup.
---
### Things to Try This Week
- Install the Codex Chrome extension and test browser flows like dashboard monitoring or CRM updates that previously required manual tab switching.
- Experiment with the new Realtime API audio models for a voice agent that mixes reasoning and translation in one session.
- Swap STAMLite into a small training run and compare memory usage and convergence against your current AdamW setup.
- Run the updated Petri tests on a misaligned model to see how the donated tool’s realism improvements affect auditing workflows.
- Fine-tune a clinical QA model on ROCm hardware following the new Hugging Face walkthrough if you lack NVIDIA GPUs.
---
### On the Horizon
- Codex EU and UK support expected in the coming weeks.
- NLAs on additional open models arriving via the Neuronpedia partnership.
- Further ChatGPT voice mode upgrades still pending after the realtime API drops.
- Continued expansion of AWS agent payment tooling with additional stablecoin integrations.