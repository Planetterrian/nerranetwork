# Models & Agents
> **OpenAI just added goal mode and screen-aware context to Codex, letting agents work autonomously for hours on real tasks.**

**What You Need to Know:** OpenAI rolled out Goal mode, Appshots, and advanced annotation in Codex across app, IDE, and CLI. Anthropic reported finding over 10,000 high-severity vulnerabilities through Project Glasswing using Claude models. Multiple new open-source releases focus on faster inference and smaller footprints for consumer hardware.
---
### Top Story
OpenAI announced Goal mode, Appshots for screen context, and advanced annotation capabilities for Codex. Goal mode lets users set objectives that the system pursues for hours or days with reduced intervention, available in the app, IDE extension, and CLI. Appshots pull live screen content directly into the agent session, while the annotation mode supports direct visual feedback on web pages. These updates shift Codex from reactive chat toward longer-running, context-rich agent workflows. Builders working on coding automation or multi-step development tasks should test the new modes this week to see how hands-off execution performs on their projects. Watch for further agentic refinements as OpenAI solicits user suggestions for next week’s updates. Source: [x.com](https://x.com/OpenAI/status/2057617860986593680)
---
### Model Updates
**Supra-50M Released: Source r/LocalLLaMA**
SupraLabs released Supra-50M, a 50M-parameter Llama-style model trained from scratch on 20 billion tokens of fineweb-edu data. It reports 76.3% on BLiMP, 77.2% on SciQ, and 52.2% on ARC-Easy despite its size. Both base and instruct versions are available on Hugging Face with a custom BPE tokenizer. The release kicks off SupraLabs’ scaling roadmap that includes 124M and 350M variants. Try the instruct version for lightweight educational or reasoning tasks where larger models are overkill.

**LongCat-Video-Avatar 1.5: Source r/LocalLLaMA**
Meituan open-sourced LongCat-Video-Avatar 1.5, an audio-driven human video generation framework built on the LongCat-Video base. It adds Whisper-Large audio encoding, supports AT2V/ATI2V and video continuation, and achieves 8-step inference via DMD2 distillation. The model handles realistic and animated styles plus multi-person scenes while maintaining identity consistency. Weights are MIT-licensed. Test it for avatar or lip-sync video projects that need production stability without heavy fine-tuning.

**G4-MeroMero-26B-A4B Uncensored: Source r/LocalLLaMA**
A new uncensored fine-tune of gemma-4-26B-A4B-it was released with KLD of 0.0152 and only 12 refusals out of 100 test cases. Both Safetensors and GGUF versions are available, positioned as a faster, lower-VRAM alternative to the 31B MeroMero variant. The author notes the 31B remains stronger overall but acknowledges demand for the smaller size. Download from llmfan46 on Hugging Face if you need reduced refusal behavior on the 26B-A4B base.

**Qwen3.6 27B Pure Quant on 16 GB: Source r/LocalLLaMA**
A pure Q4_K_M GGUF of Qwen3.6-27B fits in 15.1–15.4 GB VRAM and delivers 40 tok/s generation on an RTX 5060 Ti when using MTP. The non-MTP version reaches higher prompt processing speeds. Perplexity stays within 0.17 of BF16. Builders targeting consumer 16 GB cards can now run this model locally with the latest llama.cpp and the linked pure quant files.

**BeeLlama v0.2.0 DFlash Update: Source r/LocalLLaMA**
BeeLlama 0.2.0 introduces DFlash for major speedups on single RTX 3090 hardware, reaching 163.9 tok/s median on Qwen 3.6 27B (4.4× baseline) and 177.8 tok/s on Gemma 4 31B (4.93× baseline). Prompt processing remains near baseline while acceptance rates stay usable. The update adds full Gemma 4 31B vision support and stricter draft validation. Try the quick-start configs if you want speculative decoding gains without changing your target model.
---
### Agent & Tool Developments
**Spice Decision Layer: Source r/MachineLearning**
Spice is a new open-source runtime that sits above execution agents and handles perception, simulation, structured decision-making, and reflection before dispatching tasks. It targets the gap where current agents excel at execution but lack context-aware prioritization. The GitHub repo includes a core loop diagram and supports delegation to tools like Claude Code or Codex. Fork the repository to experiment with adding an explicit decision layer to your agent stacks.

**GBrain Memory Layer Tutorial: Source MarkTechPost**
A step-by-step guide shows how to install and run GBrain v0.38.2.0, the markdown-first knowledge graph originally built by Garry Tan for his own OpenClaw and Hermes deployments. It wires itself via regex inference rather than LLM calls and connects to Claude Code through MCP. The tutorial covers building a brain repo and running hybrid search in about 20 minutes. Clone the repo and follow the terminal commands if you need persistent memory across agent sessions.
---
### Practical & Community
**Qwen3.6-35B-A3B on 8 GB 3070 Ti: Source r/LocalLLaMA**
A user achieved 30+ tok/s with 262k context on an 8 GB 3070 Ti using Q4_K_XL quants of the 35B-A3B MoE model. Only ~3.5B active parameters need to stay in VRAM. Linux Server yielded a 25% boost over Windows 11 due to lower memory overhead. The detailed llama-server configs and KV cache settings are worth copying if you run MoE models on limited hardware.

**Blackwell PDL Performance: Source r/LocalLLaMA**
Llama.cpp added Programmatic Dependent Launch support for Blackwell GPUs (CC >= 90). Enabling it via the -DGGML_CUDA_PDL=ON build flag delivered 5–9% token generation gains with negligible prefill impact. The feature is off by default. Builders on RTX 50-series cards should rebuild with the flag to capture the free inference boost.

**ByteShape Qwen3.6-35B-A3B Quant: Source r/LocalLLaMA**
ByteShape’s CPU-5 quant (18.3 GB) ran 30% faster on token generation than Unsloth UD-IQ4_XS while partially offloaded on a 6 GB laptop GPU. Prompt processing was slightly slower. The author notes the need for independent quality comparisons. Test the linked GGUF if you prioritize generation speed on low-VRAM laptops.
---
### Under the Hood: Pure Quantization for Consumer GPUs
Everyone talks about quantization as a simple “make it smaller” knob. In practice it is a set of deliberate trade-offs between bit-width, calibration data, and hardware mapping that determine whether a model stays usable. Pure quantization methods skip imatrix calibration and instead apply uniform or near-uniform scaling across weights, which reduces preprocessing time and sometimes improves throughput on CPUs during offload. The cost appears in slightly higher perplexity—typically 0.05–0.17 above imatrix equivalents on the same model size. For MoE architectures the savings compound because only active experts are loaded; dropping from 4.5 bpw to 4.22 bpw can free enough VRAM to keep an extra expert resident and raise cache hit rates. The practical decision rule is straightforward: use pure quants when generation speed on partial offload matters more than squeezing every last point of benchmark quality, and fall back to imatrix when you have the calibration budget and need maximum fidelity on long-context tasks.
---
### Things to Try This Week
- Test OpenAI Codex Goal mode on a multi-hour refactoring task to see how the hands-off execution performs compared with manual prompting.
- Run the new Qwen3.6-27B pure Q4_K_M GGUF on any 16 GB card and compare token generation against your current 7B–13B daily driver.
- Install BeeLlama v0.2.0 with DFlash on a 3090 and benchmark it against plain llama.cpp on the same Qwen 27B or Gemma 31B target.
- Follow the GBrain tutorial to add a self-wiring markdown memory layer to an existing Claude Code or Codex workflow.
- Try the LongCat-Video-Avatar 1.5 demo on a short audio-driven avatar clip to evaluate the new Whisper-Large lip sync quality.
---
### On the Horizon
- SupraLabs plans to release 124M and 350M models continuing the current scaling series.
- Further Codex refinements are expected after OpenAI collects user suggestions this week.
- More ik_llama.cpp-compatible quants for 16 GB cards are likely as the project gains adoption.
- Additional DFlash-style speculative decoding implementations may appear for other inference engines.