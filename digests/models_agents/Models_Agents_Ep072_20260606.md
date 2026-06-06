# Models & Agents
> **Microsoft just gained the freedom to build its own frontier models after a contract change with OpenAI, and the first MAI family is already shipping.**

**What You Need to Know:** Microsoft announced seven in-house MAI models spanning reasoning, code, image, transcription, and voice, trained from scratch on licensed data without distillation. A major open-weight release wave also landed this week across LLMs, VLMs, TTS, and world models. Builders should watch how quickly the MAI models reach competitive performance on agentic and coding tasks now that Microsoft can iterate independently.
---
### Top Story
Microsoft revealed that a contract change roughly six months ago removed prior restrictions, allowing its AI Superintelligence Team to pursue superintelligence with its own researchers, data, and custom silicon. The company shipped its first substantial in-house model family under the MAI brand, including the 35B-active-parameter MAI-Thinking-1 reasoning model and specialized models for code, image generation, transcription across 43 languages, and multilingual voice. All models were trained from scratch on commercially licensed data without relying on outputs from other labs. They are available through Microsoft Foundry with support for third-party weight tuning on platforms such as OpenRouter, Fireworks, and Baseten. Enterprise customers can already use Frontier Tuning to customize the models on their own workflows inside governed environments. The move signals Microsoft is building a vertically integrated stack alongside its continued OpenAI partnership rather than replacing it. Source: [venturebeat.com](https://venturebeat.com/technology/microsoft-ai-chief-says-company-was-set-free-from-openai-to-pursue-superintelligence)
---
### Model Updates
**Anthropic Science Blog — [@AnthropicAI](https://x.com/AnthropicAI)**
Anthropic released new research showing Claude Opus 4.7 matches or exceeds dedicated NMR spectroscopy software on molecular structure interpretation tasks. The work focuses on helping chemists manipulate molecules by first understanding their structure through NMR data. Builders working on scientific tooling can now test whether Opus 4.7 can replace or augment existing NMR analysis pipelines without custom fine-tuning. Source: [x.com](https://x.com/AnthropicAI/status/2062979607448682731)

**DeepSeek V4 Flash — r/LocalLLaMA**
DeepSeek V4 Flash is now runnable via an early llama.cpp PR, with users reporting strong intelligence for its size, native FP4-FP8 hybrid quantization that holds up well under quantization, and efficient context scaling that uses less KV cache. The model is being positioned as a contender for the 80-140GB local inference space. Early testers created custom 3-bit quants to match the original tensor layout and noted reliable correctness despite slow speeds and missing GPU/FA support. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tyb3np/deepseek_v4_flash_is_amazing_wip_llamacpp_pr_24162/)

**Gemma 4 family updates — r/LocalLLaMA**
Google shipped Gemma 4 12B as a fully open dense any-to-any model supporting text, image, audio, and video with 256k context and coverage of 140+ languages. Quantization-aware training (QAT) variants of the Gemma 4 family are showing speed and VRAM gains on AMD hardware with no measurable quality loss versus standard quants on tested prompts. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tyd1zc/big_week_for_open_ai_with_25_notable_openweight/)

**NVIDIA Nemotron 3 Ultra — r/LocalLLaMA**
NVIDIA released Nemotron 3 Ultra, a 550B hybrid Mamba-MoE model with 55B active parameters, 1M context, and reported MMLU of 89.1. An NVFP4 variant claims roughly 5x throughput on Blackwell hardware and is described as the first openly weighted 550B hybrid Mamba-Transformer. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tyd1zc/big_week_for_open_ai_with_25_notable_openweight/)
---
### Agent & Tool Developments
**Qwen3.7-Plus — the-decoder.com**
Alibaba positioned Qwen3.7-Plus as a multimodal model explicitly built to function as a full autonomous agent rather than a chat interface. The release emphasizes agentic capabilities across modalities. Developers exploring agent frameworks should test whether the model’s native agent behaviors reduce the need for heavy scaffolding compared with prior Qwen releases. Source: [Google News](https://news.google.com/rss/articles/CBMirwFBVV95cUxNekZTazZ0VHB5NTVPYVdDSG9lY2hVSFo4dlVSZ1ZnclpjTUhIZ205Wmo3cDIzLUpYSTZPWFlvdG5DNHVpa0dFX25NUlNmc3YwTmZ3bU15bThKQ3JWbzVEM1RIajJJZWphanNtbUE3VmJsYUd5VHVUajR6S3RncElySjFwTWZMZ0lxYllORzkxWFdpNmVMb1REMDBQNjJxeU9ZbktmUDdvUzI0YndrakYw?oc=5)

**dots.tts 2B — r/LocalLLaMA**
RedNote open-sourced dots.tts, a 2B-parameter continuous (no codec) TTS model under Apache 2.0 that performs direct text-to-speech at 48 kHz with zero-shot voice cloning. The architecture skips the traditional phoneme pipeline entirely. Teams building local voice agents now have a fully open, continuous alternative to codec-based TTS stacks. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1txwbge/dotstts_2b_sota_tts_from_rednote/)

**OpenLumara agent framework — r/LocalLLaMA**
A new modular agent called OpenLumara was released with a ~4k token default system prompt, full modularity down to core features, and built-in security controls including sandboxed shell access and HTTP black/whitelists. It is designed specifically for local models and runs efficiently on modest hardware without the token bloat of skill.md-style systems. The project is GPL2 licensed and available on GitHub. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1txxgpq/openlumara_a_different_kind_of_ai_agent_written/)
---
### Practical & Community
**micropython-wasm sandbox — Simon Willison's Weblog**
Simon Willison released micropython-wasm, an alpha PyPI package that runs MicroPython inside a WebAssembly sandbox with memory/CPU limits, controlled host function access, and no filesystem or network access by default. A CLI mode lets users try it immediately with `uvx micropython-wasm -c 'print("Hello world")'`. The package is intended for safe plugin execution inside Python applications such as Datasette. Source: [simonwillison.net](https://simonwillison.net/2026/Jun/6/micropython-in-a-sandbox/)

**Gemma 4 QAT benchmarks — r/LocalLLaMA**
Users running Gemma 4 models on an AMD 7900 XTX reported that QAT versions deliver 1.3–1.5x speedups and meaningful VRAM savings versus standard quants while preserving output quality on long-context and creative tasks. The 12B QAT variant cut generation time by 45% with identical constraint-following behavior. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1txxd7c/gemma_4_qat_benchmark_results_amd_7900_xtx_faster/)

**KV cache offload to RAM — r/LocalLLaMA**
A user running Qwen3.6 27B on an RTX 5060 Ti found that enabling `-nkvo` to keep KV cache in RAM allowed the full model to stay on GPU with f16 cache precision, trading a modest tokens-per-second drop for higher context capacity and better cache quality than quantized KV. The approach proved useful when fitting larger context windows without dropping layers. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1txpqru/maybe_kv_cache_offload_to_ram_isnt_bad/)
---
### Under the Hood: KV Cache Quantization Tradeoffs
Everyone talks about KV cache quantization as a simple “turn it on and save VRAM” toggle. In practice it is a precision-versus-throughput negotiation that depends on model architecture, context length, and downstream task. The core insight is that attention keys and values are not equally sensitive to quantization; value vectors often tolerate lower precision better than keys because they are summed rather than used for similarity lookups. Lower-bit KV formats therefore introduce small per-token errors that accumulate across long contexts, which is why some teams see reasoning degradation only after 32k–64k tokens even when perplexity looks acceptable. New methods such as KVarN attempt to close this gap by learning per-channel scales that preserve the distribution of important value dimensions, delivering q5-level KLD at roughly 4-bit storage in early llama.cpp tests. The practical tradeoff is that aggressive KV quantization can still hurt multi-step agent trajectories more than single-turn chat, because small embedding drift compounds when the model must maintain consistent state across tool calls. When you are running agents with 50k+ context or long-horizon planning, keep at least 5–6 bits on the value cache unless you have measured task-specific tolerance; for shorter chat workloads the memory win is usually worth it.
---
### Things to Try This Week
- Install micropython-wasm via uvx and test a simple sandboxed script to see whether it meets your plugin or data-transformation needs without full Python privileges.
- Run the early DeepSeek V4 Flash llama.cpp build on a model you already use for coding or reasoning and compare output stability against your current quant.
- Test Gemma 4 12B QAT versus the standard Q4_K_M quant on your longest context workflow to measure the real speed and VRAM difference on your hardware.
- Try dots.tts 2B for any local voice agent project that needs zero-shot cloning without a separate phoneme step.
---
### On the Horizon
- More labs are expected to follow RedNote’s continuous TTS approach now that a fully open, non-codec pipeline is available.
- Microsoft’s Frontier Tuning environment will likely see additional enterprise case studies as more customers test MAI models on proprietary workflows.
- Further llama.cpp and vLLM support for the new hybrid Mamba-MoE and sparse MoE models should arrive as the current PRs mature.
- Additional open-weight audio and video models are anticipated following this week’s cluster of releases.