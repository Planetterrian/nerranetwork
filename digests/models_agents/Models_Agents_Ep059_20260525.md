# Models & Agents
> **Datasette's new slash-key jump menu now launches agent conversations directly from your databases.**

**What You Need to Know:** Simon Willison shipped Datasette 1.0a30 with a keyboard-driven "jump to" menu that plugins can extend, plus a datasette-agent plugin that adds a conversation starter form. NuExtract3, a new 4B vision-language model, arrived on Hugging Face for structured extraction and Markdown conversion from documents. Builders should watch how these small, targeted releases lower the friction for mixing data exploration with agent workflows this week.
---
### Top Story
Datasette 1.0a30 introduces a "jump to" menu triggered by the "/" keyboard shortcut that lets users type to reach databases, tables, or canned queries. The release includes plugin hooks so extensions can inject additional content into the menu and its empty state. The datasette-agent plugin uses this hook to surface a form that starts a new agent conversation, with a live demo available at agent.datasette.io after GitHub sign-in. More implementation details appear on the Datasette blog. The change turns a data exploration tool into a lightweight launchpad for agent sessions without leaving the interface. Teams already running Datasette can upgrade to 1.0a30 and test the plugin immediately to see whether the new entry point changes how they prototype agent-plus-data workflows. Source: [x.com](https://x.com/simonw/status/2058704797612785849)
---
### Model Updates
**NuExtract3: r/LocalLLaMA**
NuExtract3 is a 4B vision-language model released on Hugging Face that handles both structured JSON extraction from text or images and high-quality image-to-Markdown conversion. It accepts text, images, or mixed inputs and supports multilingual documents plus separate reasoning and non-reasoning modes. GGUF, NVFP4, MLX, and vLLM quantized versions are already available. Builders working on document pipelines, OCR, or RAG preprocessing should test it on receipts, invoices, and tables this week to see whether the unified extraction-plus-Markdown path reduces their current multi-stage setup. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tn3tci/numindnuextract3_hugging_face/)

**Qwen 3.6 benchmarks: r/LocalLLaMA**
Qwen 3.6 27B and 35B BF16 models were benchmarked on a 2× RTX PRO 6000 setup using the latest stable vLLM backend. At 64 concurrency the 27B model reached 1600 tokens/s generation without MTP and 1800 tokens/s with MTP-2 enabled; the 35B model hit 2700 tokens/s at 64 concurrency and 3500 tokens/s at 128 concurrency with 30,000 tokens/s prompt processing. These numbers come from a personal project and give concrete throughput expectations for mid-size Qwen variants on dual professional GPUs. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tn0t7u/qwen_36_benchmarks_on_2x_rtx_pro_6000/)

**MiniCPM-V 4.6 on Orange Pi AIPro: r/LocalLLaMA**
A custom C++ inference engine was written from scratch to run MiniCPM-V 4.6 natively on the Ascend 310B NPU inside the $149 Orange Pi AIPro board. The engine bypasses torch_npu entirely on the hot path, using custom AscendC kernels for cube matmul, lm_head chunking, and vectorized causal-conv1d to reach 5.90 tokens/s FP16 after incremental optimizations. Python is used only for cold-path tokenization and image preprocessing. Anyone targeting edge VLM deployment on this hardware now has an open-source starting point at github.com/lvyufeng/minicpm-v-4.6-orangepi. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tmy4g9/wrote_a_custom_c_engine_for_minicpmv_46_on_orange/)

**Cider W8A8 quantization: r/LocalLLaMA**
Mininglamp AI released Cider, a small SDK that adds W8A8 activation quantization on top of MLX for Apple Silicon. On an M5 Pro the change reduced prefill time for a 4B VLM from 2.839 s to 2.519 s at 4516-token context while decode speed stayed essentially flat. Per-channel INT8 TensorOps require M5 or newer; M4 falls back to the regular path. The repo includes accuracy numbers on Wikitext2 for Qwen3-8B and Llama3-8B showing modest perplexity impact. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tn2p61/we_added_w8a8_activation_quantization_to_mlx/)
---
### Agent & Tool Developments
**Computer-use sandbox framework: r/LocalLLaMA**
A developer released ai-sandbox-manager, an LXC-based VM template system that gives agents full sudo access, GPU passthrough, and browser automation while isolating them from the host. The setup supports multiple concurrent sessions, persistent .env files, and hooks to block dangerous git operations. It was built and tested on DGX Spark hardware where standard Docker GPU passthrough is difficult. The repo is at github.com/fieryWaters/ai-sandbox-manager and includes cua for computer-use support on Linux. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tn3i55/i_built_a_computer_use_sandbox_framework_for/)

**MCP tutorial repo: r/LocalLLaMA**
A new repo called MCP from Scratch walks through building a Model Context Protocol server and client in plain Node.js, then adds local GGUF inference via node-llama-cpp and a custom plan-act-observe agent loop. The later modules demonstrate MCP sampling and tool use with a local model, plus an optional LangChain path. The project is intentionally minimal and aimed at developers who want to understand the protocol mechanics rather than use a high-level SDK. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tn1jjy/i_made_a_localfirst_mcp_tutorial_repo_with/)
---
### Practical & Community
**llama.cpp checkpoint fix: r/LocalLLaMA**
A pull request to ggml-org/llama.cpp improves checkpoint creation so that agentic coding sessions no longer force full prompt re-processing after context-rewriting tools modify history. The change targets the common pattern where an agent produces 20k+ tokens of code and the next short user message triggers expensive reprocessing of 70k-token contexts. Early users report noticeably more responsive agentic coding loops after adopting the patch. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tn0jyp/server_fix_checkpoints_creation_by_jacekpoplawski/)
---
### Under the Hood: Activation Quantization Realities
Everyone talks about activation quantization as if it is a simple "turn on INT8" switch that always delivers free speed. In practice it requires custom kernels that only compile on newer silicon and trades small accuracy losses for prefill gains that appear mainly at longer contexts. The Cider implementation registers Metal primitives so the per-channel W8A8 path runs 1.84× faster than W8A16 at M=4096, yet decode speed barely moves because memory bandwidth remains the limiter. On M4 hardware the same code silently falls back, showing that the technique is gated by hardware TensorOp support rather than software availability. Perplexity impact stays under 0.2 points on 8B models when using per-channel scaling, but per-group scaling tightens the bound further when precision matters more than the 300 ms prefill saving. The gotcha that bites most teams is assuming the speedup will appear on every workload; short-context chat sees almost none of the benefit while long-document RAG preprocessing sees the full win. Use it when your pipeline is prefill-heavy and you control the deployment hardware; otherwise stick with weight-only quantization until the next silicon generation lands.
---
### Things to Try This Week
- Install the datasette-agent plugin on Datasette 1.0a30 and test the "/" jump menu to launch agent conversations directly from your tables.
- Pull NuExtract3 from Hugging Face and run it on a batch of scanned invoices to compare its structured JSON output against your current OCR-plus-prompt pipeline.
- Clone the ai-sandbox-manager repo if you need a persistent, GPU-enabled sandbox for computer-use agents that survives host reboots.
- Try Cider on an M5 Mac with any MLX model to measure prefill improvement on your longest context workloads before deciding on wider adoption.
---
### On the Horizon
- More plugin authors are expected to extend the Datasette jump menu now that the hook is public.
- Additional quantized versions and fine-tunes of NuExtract3 are likely to appear on Hugging Face within days.
- The llama.cpp checkpoint PR is under active review and may land in the next stable release.
- Edge VLM experiments on Ascend hardware will probably produce more custom-kernel repos following the MiniCPM-V example.