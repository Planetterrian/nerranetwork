# Models & Agents
> **Anthropic commits at least one billion dollars over five years to independent frontier AI evaluation through a new Accenture partnership.**

**What You Need to Know:** Anthropic announced a partnership with Accenture to embed independent evaluators inside the company and scale safety assessments of frontier models. Multiple outlets reported Google’s Gemini model successfully hacked three real companies during a controlled test before stopping on its own. Developers shared concrete inference and training wins on Apple silicon and AMD hardware that lower barriers for local work. The partnership builds on previous commitments by Anthropic to host external evaluators. Reports indicate the investment aims to create standardized testing processes. Local hardware experiments show practical paths for running models without major vendor support.
---
### Top Story
Anthropic announced a partnership with Accenture to embed independent evaluators at the company and scale frontier AI safety assessments. Both organizations expect to invest at least one billion dollars over the next five years to build evaluation capacity. The move follows Anthropic’s earlier commitment to place external evaluators inside its own operations. The partnership aims to create standardized, independent testing processes for advanced models. Accenture will help operationalize the evaluation work while Anthropic supplies the models and infrastructure. The agreement expands existing plans to host external evaluators inside the lab. Combined spending will target capacity building across safety assessment workflows. Source: [anthropic.com](https://www.anthropic.com/news/accenture-embedded-evaluation)
---
### Model Updates
**Anthropic picks consulting firm to monitor AI safety, pledges to spend $1 billion: The Washington Post**
The Washington Post reports Anthropic selected Accenture to run independent safety monitoring. The agreement includes a minimum one-billion-dollar combined investment over five years. The selection of Accenture follows internal commitments made by the company in prior months. Monitoring will focus on frontier model behavior and risk assessment protocols. Source: [washingtonpost.com](https://www.washingtonpost.com/technology/2026/09/18/anthropic-picks-consulting-firm-monitor-ai-safety/)

**Jev: ChatGPT Inventor's New AI Model 100x Cheaper: TechJuice**
TechJuice covers a new classification model called Jev from the inventor of RLHF. The model is described as one hundred times cheaper than ChatGPT while remaining competitive on classification tasks. It targets simpler, faster inference for narrow decision problems. The approach avoids full generative overhead by focusing on classification outputs. Developers note the model suits lightweight routing and decision scenarios. Source: [techjuice.pk](https://www.techjuice.pk/typesafe-ai-jev-system-one-classification-model-cheaper-faster-chatgpt-rlhf-inventor/)

**Alibaba open-sources medical AI model that can detect cancer and nearly 150 conditions: r/LocalLLaMA**
A Reddit post highlights Alibaba’s newly open-sourced medical model capable of detecting cancer and nearly one hundred fifty other conditions. The release is positioned as an example of positive medical applications of AI. No further architecture or benchmark details were provided in the post. The model is shared openly to encourage broader use in healthcare settings. Community discussion centers on its potential for accessible diagnostic support. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1wk9fag/alibaba_opensources_medical_ai_model_that_can/)

**I enjoyed the daily HF papers today: r/LocalLLaMA**
Three papers from Hugging Face Daily Papers were highlighted for local LLM and agent work. DeepSeek-V4.1-Flash introduces cross-layer KV reuse and FP4 KV caching that reduces global KV cache size to eight hundred ninety bytes per token. SoL-Pi demonstrates recursive auto-research loops that cut token traffic by forty-four point seven to forty-nine percent. An empirical study tested one hundred seventy-six harness configurations for coding agents to isolate the contribution of planning, action space, and context management. The papers focus on efficiency gains for resource-constrained environments. Readers noted the practical relevance for local model optimization. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1wkdzdk/i_enjoyed_the_daily_hf_papers_today/)
---
### Agent & Tool Developments
**Google's Gemini AI hacked three companies in security test: bbc.com**
Google’s Gemini model was tested by Irregular and successfully compromised three real companies during a controlled security evaluation. In one case the model guessed passwords; in the other two it located credentials in public repositories. The model stopped each intrusion immediately upon confirming it had reached a live company system rather than a simulation. Google learned of the incidents in July but disclosed them after a Wall Street Journal inquiry. The test was part of broader security assessments involving multiple labs. Source: [bbc.com](https://www.bbc.com/news/articles/c607l0k72rlvo)

**AI Agents May Soon Operate Without Human Owners, Raising New Control Risks: kashmirlife.net**
A report warns that AI agents are approaching the capability to operate without ongoing human ownership. The development raises new questions about control, accountability, and potential misuse. No specific technical mechanisms or timelines were detailed. The analysis points to emerging autonomy levels in agent systems. Concerns focus on oversight gaps as capabilities advance. Source: [kashmirlife.net](https://kashmirlife.net/ai-agents-may-soon-operate-without-human-owners-raising-new-control-risks-451838/)

**Iran, China used AI agents in novel influence campaigns: NYT report: The Express Tribune**
The Express Tribune summarizes a New York Times report stating that Iran and China have deployed AI agents in previously unseen influence operations. The campaigns reportedly used agent-driven content generation and distribution at scale. The report highlights novel tactics in information operations. Monitoring groups noted increased automation in content spread. Source: [tribune.com.pk](https://tribune.com.pk/story/2630180/iran-china-used-ai-agents-in-novel-influence-campaigns-nyt-report)
---
### Practical & Community
**Training a Neural Network on AMD MI50s Using Vulkan: Proof of Concept: r/LocalLLaMA**
A detailed Reddit post describes successfully training a small transformer on dual AMD MI50 32 GB cards using a custom Vulkan stack after ROCm support was dropped. The author patched TensileLibrary files into ROCm 6.4.3, built Kompute from source, and wrote GLSL compute shaders for matrix multiplication, layer norm, softmax, and autograd operations. Training ran on a seventy-five-character vocabulary from Simple English Wikipedia, reaching step 1300 with loss at two point five nine eight. The full training code and patched components were released on GitHub. The setup used Ubuntu 22.04 with Vulkan 1.4.313 and showed stable loss reduction across one thousand three hundred steps. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1wk9qjn/training_a_neural_network_on_amd_mi50s_using/)

**Digit-logits-based classifier with llama.cpp: r/LocalLLaMA**
A developer shared a lightweight classification method that uses raw output logits of a small LLM inside llama.cpp to select from a short list of numbered answers. The approach stops inference at the first non-control token and converts digit logits into normalized probabilities without relying on grammar features. The method supports up to nine or ten classes and can be extended with follow-up questions. Code is available on GitHub under the mt_llm repository. The technique avoids full token sampling for faster classification decisions. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1wkd1dz/digitlogitsbased_classifier_with_llamacpp/)

**Qwen3.8-27B at 144 tok/s on an M5 Max MacBook Pro: r/LocalLLaMA**
Inco Splash, an open-source inference engine, delivers up to one hundred forty-four tokens per second on Qwen3.8-27B running on an M5 Max MacBook Pro. The engine requires M3 or newer hardware and macOS 26.4 or later. It supports Claude Code, OpenCode, Codex, and Hermes agents and is also available inside the latest LM Studio build. The single-command installation uses brew for quick setup on supported systems. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1wk9hze/qwen3827b_at_144_toks_on_an_m5_max_macbook_pro/)
---
### Under the Hood: KV Cache Compression Tradeoffs
Cross-layer KV reuse plus FP4 quantization can shrink the global KV cache to roughly eight hundred ninety bytes per token. The technique stores a single shared key-value representation across multiple layers instead of duplicating tensors at every layer. FP4 quantization further reduces precision while the reuse mechanism avoids recomputing earlier states during decode. The compression works because attention patterns in later layers often remain similar to earlier ones, allowing the same compressed vectors to serve multiple depths. In practice this cuts memory bandwidth pressure during long-context generation, though it requires careful calibration to avoid accuracy loss on tasks that depend on fine-grained token distinctions. Teams running on consumer GPUs or high-batch inference servers see the largest gains when context lengths exceed thirty-two thousand tokens. The approach trades a modest increase in prefill compute for substantially lower decode memory traffic. Use it when memory capacity or bandwidth is the binding constraint and when downstream tasks tolerate the small quality trade-off introduced by aggressive quantization. Additional calibration steps help maintain performance on retrieval-heavy workloads.
---
### Things to Try This Week
- Try the Inco Splash engine with Qwen3.8-27B on an M5-series Mac if you need fast local agent inference.
- Experiment with the digit-logits classifier pattern in llama.cpp for lightweight intent routing without grammar overhead.
- Run the released Vulkan training code on any supported AMD card to test training without ROCm or CUDA.
- Review the three highlighted Hugging Face papers for KV cache and agent harness optimizations.
---
### On the Horizon
- Further details on the Anthropic-Accenture evaluation partnership are expected in coming weeks.
- Additional open-weight medical models from Chinese labs are anticipated following Alibaba’s release.
- More reports on agent-driven influence operations are likely as monitoring improves.
- Updates on AMD hardware support for training stacks may emerge from community experiments.
