# Models & Agents
> **AI agents now deliver 26 minutes of autonomous work per session, shifting the build-vs-buy math for developers who need more than search snippets.**

**What You Need to Know:** A Harvard and Perplexity study quantifies the autonomy gap between full agents and search assistants. Gemma 4 26B and 31B variants show surprising code-understanding strength in local tests, with QAT quantization results challenging earlier assumptions. New tools for chaining Hugging Face Spaces and running agents on Jetson hardware give builders concrete options to test this week.
---
### Top Story
A matched-pair study from Harvard and Perplexity compared autonomous agents against search assistants on identical tasks. Agents completed 26 minutes of independent work per session versus 33 seconds for search, with broader scope and lower cost per outcome. The evaluation used real user sessions rather than synthetic benchmarks, highlighting gains in multi-step reasoning and tool chaining. Builders working on research or data-gathering workflows can now prototype agent loops that replace multiple search-and-summarize steps. Watch for follow-up work on failure modes when tasks require external verification or long context retention. Source: [marktechpost.com](https://www.marktechpost.com/2026/06/08/a-new-study-from-harvard-and-perplexity-finds-ai-agents-perform-26-minutes-of-autonomous-work-per-session-vs-33-seconds-for-search/)
---
### Model Updates
**Gemma 4 26B A4B IT QAT Comparison: r/LocalLLaMA**
Gemma 4 26B A4B IT models were tested in MLX 4-bit, 6-bit, and 8-bit QAT variants on MMLU_PRO and HumanEval using an M5 Pro MacBook. The 6-bit non-QAT version reached 58% MMLU_PRO and 98% HumanEval, outperforming the QAT 8-bit model on both. The QAT version showed no statistically significant edge over standard 4-bit quantization in these runs. Builders testing code understanding should compare Q6 against QAT 8-bit on their own datasets before switching. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1u0ubbo/gemma_4_26b_a4b_it_qat_comparison/)

**Gemma 4 31B Code Competence: r/LocalLLaMA**
Gemma 4 31B outperformed both Qwen 3.6 27B/35B and Opus 4.7 at explaining and refactoring messy academic codebases with niche variable names. It tracked cross-file dependencies more reliably than Qwen models, which often attempted unauthorized directory changes. The 31B variant handled 65K context while maintaining coherent multi-part edits. Researchers maintaining legacy research code should test Gemma 4 31B before defaulting to larger closed models. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1u0yzts/gemma_4_31bs_competence_surprised_me/)

**Gemma 4 4-bit QAT vs Standard Quants: r/LocalLLaMA**
Users are actively seeking head-to-head numbers between Unsloth Gemma 4 4-bit QAT and standard 8-bit PTQ on the same base weights. Early anecdotal reports suggest QAT preserves more accuracy at 4-bit than expected, but controlled benchmarks remain sparse. Anyone running local code or math workloads should publish their own MMLU_PRO or SciCode results to close the gap. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1u0vltz/anyone_seen_benchmarks_comparing_gemma_4_4bit_qat/)
---
### Agent & Tool Developments
**How an Agent Built a 3D Paris Gallery by Chaining Two Hugging Face Spaces: Hugging Face - Blog**
An agent successfully chained two separate Hugging Face Spaces to generate and assemble a navigable 3D Paris gallery without custom orchestration code. The workflow demonstrates current limits of zero-shot multi-Space composition using only public endpoints. Developers experimenting with visual agents can replicate the pattern today by exposing their own Spaces as callable tools. Source: [huggingface.co](https://huggingface.co/blog/mishig/spaces-agents-md)

**Jetson Orin NX Build for Hermes Agent + Benchmarking: r/LocalLLaMA**
A modified Jetson Orin NX running Gemma 4 26B A4B UD Q2_K_XL achieved 14.65 tok/s at 8K context and 10.21 tok/s at 60K context while supporting multiple tool calls. The build required a custom heatsink and case to stay under 40W while hitting 65K context targets. Local agent builders needing silent, low-power inference should review the exact quant and cooling choices. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1u11wvo/jetson_orin_nx_build_for_hermes_agent_benchmarking/)

**Still a VERY lightweight open web-search tool for smaller local LLMs - now with SearXNG support: r/LocalLLaMA**
TinySearch v0.2.0 switched its default backend to SearXNG, capping output at 8K tokens for smaller local models used with MCP agents. The tool crawls, chunks, and reranks results before returning a compact context blob. Users running Qwen 3.5-9B or similar with Cline or Roo should test the SearXNG option to reduce prompt bloat. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1u106rc/still_a_very_lightweight_open_websearch_tool_for/)
---
### Practical & Community
**NVIDIA cuTile Python Tutorial: Building Tiled GPU Kernels for Vector Addition, Matrix Addition, and Matrix Multiplication in Colab: MarkTechPost**
The tutorial walks through cuTile setup in Colab, implementing tiled kernels for vector addition, matrix addition, and matrix multiplication with PyTorch fallbacks. It includes driver checks, correctness validation, and median runtime benchmarks at each stage. Anyone moving matrix workloads to custom CUDA-style Python kernels should follow the Colab notebook. Source: [marktechpost.com](https://www.marktechpost.com/2026/06/09/nvidia-cutile-python-tutorial-building-tiled-gpu-kernels-for-vector-addition-matrix-addition-and-matrix-multiplication-in-colab/)

**New Science Blog: Why has AI advanced faster in coding than in biology?: [@AnthropicAI](https://x.com/AnthropicAI)**
Anthropic’s new post examines why agent tooling progressed faster in code than biology, citing pre-car-era database designs that hinder agent navigation. It calls for new infrastructure that treats bio databases as first-class agent environments. Researchers building biology agents should read the full piece before designing retrieval layers. Source: [x.com](https://x.com/AnthropicAI/status/2064054837294354677)
---
### Under the Hood: Tiled GPU Kernel Programming
Everyone treats high-level frameworks like PyTorch as sufficient for matrix work. In practice, tiling decisions determine whether a kernel stays memory-bound or becomes compute-bound on modern GPUs. cuTile exposes explicit tile sizes so developers can match L2 cache lines and register pressure to the specific operation. For vector addition the overhead of tiling is small, but matrix multiplication sees clear wins once tile dimensions align with warp scheduling. The tradeoff appears in launch latency and the need to keep fallback paths for unsupported shapes. Teams should profile both tiled and untiled versions on their target batch sizes before committing to custom kernels.
---
### Things to Try This Week
- Test Gemma 4 31B on a messy academic codebase you maintain — compare dependency tracking against your current model.
- Chain two public Hugging Face Spaces following the Paris gallery example if you need quick visual agent prototypes.
- Run TinySearch v0.2.0 with your local SearXNG instance against Qwen 3.5-9B to measure context reduction on research queries.
- Follow the cuTile Colab notebook and benchmark tiled matrix multiplication against PyTorch on your own GPU shapes.
---
### On the Horizon
- More Gemma 4 QAT versus standard quant comparisons expected as Unsloth and MLX users publish larger test suites.
- Additional agent chaining examples on Hugging Face Spaces likely as the pattern spreads.
- Further local hardware builds for Hermes-style agents on Jetson and similar edge platforms.