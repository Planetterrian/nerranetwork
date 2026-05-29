# Models & Agents
> **Anthropic's $65B Series H at $965B valuation and $47B run-rate revenue show Claude demand is scaling faster than most labs can match.**

**What You Need to Know:** Liquid AI shipped LFM2.5-8B-A1B with 128K context and 38T pre-training tokens for edge devices. A new monokernel on AMD MI300X hits 3,300 output tokens/s for small models. Researchers released RightNow-Arabic-0.5B-Turbo and Aryabhata 2, while local builders are shifting agents to HTML rendering for diagrams and structured output.
---
### Top Story
Anthropic announced a $65 billion Series H round at a $965 billion post-money valuation led by Altimeter, Dragoneer, Greenoaks, and Sequoia. The company separately disclosed that its run-rate revenue crossed $47 billion earlier this month, driven by enterprise deployments of Claude and everyday usage. This capital will expand research and inference capacity to meet demand. The round underscores how quickly production usage of frontier models is growing across industries. Builders should watch how the added resources translate into Claude availability and new capabilities in the coming months. Source: [x.com](https://x.com/AnthropicAI/status/2060061347522433422)
---
### Model Updates
**Liquid AI releases LFM2.5-8B-A1B: r/LocalLLaMA**
Liquid AI released LFM2.5-8B-A1B, an edge-focused model that expands the prior LFM2-8B-A1B with a 128K context window, 38T tokens of pre-training, and large-scale reinforcement learning. It doubles the vocabulary to improve non-Latin tokenization and supports tool chaining on entry-level laptops. The model is available on Hugging Face. Builders working on local agents should test its complex task handling versus Qwen variants of similar size. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tqqnsl/liquid_ai_releases_lfm258ba1b/)

**RightNow-Arabic-0.5B-Turbo: cs.CL updates on arXiv.org**
RightNow-Arabic-0.5B-Turbo is a 518M-parameter Arabic-specialized decoder built on Qwen2.5-0.5B by adding 27,032 Arabic tokens, continued pre-training on 504M Arabic tokens, and supervised fine-tuning plus DPO on Arabic preference pairs. It reaches 35.9% mean accuracy on Arabic COPA, HellaSwag, and MMLU benchmarks, beating other sub-1B open models and recovering 67% of a 9B model's performance at 1/18th the size. The quantized build runs at 635 tokens/s on a single H100. Developers targeting Arabic edge applications should evaluate the released GGUF variants. Source: [arxiv.org](https://arxiv.org/abs/2605.28827)

**Aryabhata 2: cs.CL updates on arXiv.org**
Aryabhata 2 is a reasoning-focused model post-trained from GPT-OSS-20B via reinforcement learning on PhysicsWallah question banks for JEE and NEET preparation. It outperforms the base model on JEE Main, JEE Advanced, NEET, AIME, and GPQA while using up to 64% fewer output tokens. The training combined prolonged RL with larger rollout groups for broader exploration. Teams building STEM tutoring agents should test its structured problem-solving efficiency. Source: [arxiv.org](https://arxiv.org/abs/2605.28829)

**Gemma4 as everyday local LLM: r/LocalLLaMA**
Users report Gemma4 26B A4B running well on M5 Pro hardware with strong generalist performance across creative writing, debugging, image classification, and tool-augmented chat. It shows more personality than Qwen3.6 35B A3B while using less memory. The model benefits from web search tools for daily workflows. Local developers should compare it directly against Qwen3.6 for non-coding tasks. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tqy2iv/shoutout_to_gemma4_as_a_conversational_assistant/)
---
### Agent & Tool Developments
**HTML as primary chat language for agents: r/LocalLLaMA**
A coding agent setup now renders responses directly as HTML in the browser, enabling inline SVGs, tables, and diagrams without markdown fallback. Switching the system prompt from markdown to HTML improved diagram quality and structure. The approach works with Qwen3.6-27B and requires only a simple prompt change plus a web UI. Teams building agent interfaces should test HTML output to reduce post-processing steps. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tqt12p/use_html_as_the_primary_chat_language_for_your/)

**Monokernel LLM inference on AMD MI300X: r/MachineLearning**
A new monokernel runs the full decode sequence as one GPU-resident program on 8x MI300X, mapping memory access to die topology and IOD groupings. It achieves up to 3,300 output tokens/s per request at batch size 1 with no quantization or speculative decoding on a 2B coding model. The team plans future support for large MoE models. Inference engineers targeting AMD hardware should review the technical deep dive for layout-aware optimizations. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1tqvuz9/building_a_monokernel_for_llm_inference_on_amd/)
---
### Practical & Community
**Probe-targeted fine-tuning for confidence calibration: r/MachineLearning**
A LoRA-based method uses hidden-state probes to teach models to verbalize their actual confidence instead of defaulting to 99%. The approach works across 7B–70B models from four families with only a few hundred examples and under 10 minutes on an M3 Ultra. Activation patching confirms the effect is causal. Researchers studying metacognition or reliable agent outputs should examine the released code and pre-print. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1tqrtkn/making_llms_tell_you_how_confident_they_really/)

**StepFun 3.7 Flash on M5 Max: r/LocalLLaMA**
Early benchmarks on an M5 Max with 128 GB show StepFun 3.7 Flash delivering usable speeds at 32K–64K context in Q4_K_S quantization. The model remains responsive below 16K context and maintains acceptable throughput at longer lengths. The post includes detailed tokens-per-second tables. Apple Silicon users should test the llama.cpp branch for their workloads. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tqqebc/stepfun_37_flash_speed_benchmark_in_m5_max/)
---
### Under the Hood: Probe-Targeted Fine-Tuning for Verbalized Confidence
Everyone talks about LLM confidence as a simple prompt fix. In practice, the model already encodes correctness signals in its hidden states at 0.76–0.88 AUROC, yet surface text stays stuck at 99% because of training dynamics. The method extracts those internal signals with linear probes, then uses the probe outputs as fine-tuning targets so the model learns to say what it already knows. This adds almost no inference cost after the short LoRA pass and works across model scales because the probe only needs to read one activation position. The quality gain is largest on mid-sized models; at 70B the softmax already carries usable signal but the argmax text still collapses. Activation patching at the exact confidence token moves the output distribution with correlation 0.976, proving the effect is causal rather than correlational. When to use this versus standard temperature scaling: apply it when you need the model to admit uncertainty on factual or multi-step tasks; skip it if your pipeline already filters low-probability tokens downstream. The gotcha that bites most teams is seed sensitivity in the shape of the confidence distribution even when discrimination stays stable.
---
### Things to Try This Week
- Test LFM2.5-8B-A1B on a local laptop for tool-chaining workflows where 128K context matters more than raw size.
- Switch an existing coding agent prompt to HTML output and measure how quickly diagram rendering improves without extra post-processing.
- Run the probe-targeted LoRA recipe on a 7B–13B model you already use for agent decision making to reduce overconfident errors.
- Benchmark StepFun 3.7 Flash against Gemma4 26B on your M-series hardware for mixed creative and coding tasks.
- Evaluate RightNow-Arabic-0.5B-Turbo if you need sub-1B Arabic performance on edge devices.
---
### On the Horizon
- More teams are expected to release small specialized models after the Arabic and STEM examples shown today.
- Additional monokernel and single-program inference work on AMD and Apple Silicon hardware is likely as memory bandwidth remains the bottleneck.
- Continued experiments with HTML and structured output formats for agents will appear as builders move away from markdown defaults.