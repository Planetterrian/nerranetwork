# Models & Agents
> **Real-time voice agents just got cheaper and more capable—OpenAI split its Realtime API into specialized models with lower latency.**

**What You Need to Know:** OpenAI released GPT-Realtime-2.1 and a mini reasoning variant optimized for voice, cutting p95 latency by at least 25% via better caching. Tencent open-sourced Hy3, a 295B MoE with 21B active parameters and 256K context that hits 78.0 on SWE-Bench Verified. Anthropic published new interpretability work showing Claude has developed mechanisms for conscious access, paired with an interactive Neuronpedia demo on open-weight models. Builders should watch how these affect agent reliability in voice and long-context workflows this week.
---
### Top Story
OpenAI added GPT-Realtime-2.1 and GPT-Realtime-2.1-mini to its API for low-latency voice agents. The mini variant is a reasoning model priced like the prior gpt-realtime-mini, while both benefit from improved caching that reduces p95 latency by at least 25%. The updates target agentic voice use cases and support WebRTC connections. Developers can now run more responsive voice loops without jumping to higher-cost tiers. Watch for how the split models affect tool-calling stability in production voice agents. Source: [marktechpost.com](https://www.marktechpost.com/2026/07/06/openai-gpt-realtime-2-1-mini-reasoning-realtime-api/)
---
### Model Updates
**Tencent Releases Hy3: An Open 295B Mixture-of-Experts (MoE) Model with 21B Active Parameters and 256K Context: MarkTechPost**
Tencent’s Hy team released Hy3 under Apache 2.0, activating 21B parameters per token with a 256K context window aimed at reasoning and agentic tasks. It reports 78.0 on SWE-Bench Verified alongside lower hallucination rates. The model is free to try on OpenRouter through July 21. Builders working on long-context agent workflows should test it against Qwen3.6-27B this week to see where the extra capacity helps. Source: [marktechpost.com](https://www.marktechpost.com/2026/07/06/tencent-releases-hy3-open-295b-moe-model/)

**nvidia/Nemotron-Labs-Audex-30B-A3B · Hugging Face: r/LocalLLaMA**
NVIDIA released Nemotron-Labs-Audex-30B-A3B, a unified audio-text LLM built on the 30B MoE Nemotron-Cascade-2 backbone with 3B active parameters. It adds discrete audio tokens and an audio encoder while preserving text reasoning and agentic performance. The model supports thinking and instruct modes plus 1M-token context. Teams doing speech-to-speech or audio-augmented agents can pull the checkpoint from Hugging Face and compare it directly to the text-only version. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1upnm8x/nvidianemotronlabsaudex30ba3b_hugging_face/)

**Partnered with Neuronpedia for interactive demo of methods on open-weights models: [@AnthropicAI](https://x.com/AnthropicAI) (X)**
Anthropic partnered with Neuronpedia to release an interactive demo of its interpretability methods running on open-weight models at https://www.neuronpedia.org/jlens. The work accompanies a paper exploring how Claude develops mechanisms for conscious access. Researchers can now inspect similar circuits in models they host themselves. Source: [x.com](https://x.com/AnthropicAI/status/2074185390060110138)
---
### Agent & Tool Developments
**Koder: browser UI based harness for coding and computer use: r/LocalLLaMA**
Koder is a new Go-based coding and computer-use harness released after 1,300 commits, focused on local Linux setups with llama.cpp and models like Qwen 3.6 27B Q8. It supports skills, MCP, visual models, milestone planning, multi-chat orchestration, and an embedded file browser. The single binary runs offline or with any OpenAI-compatible endpoint. Users report strong results on reverse engineering and OpenSCAD loops but note Gemma 4 performs poorly with the current setup. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1upqbqz/koder_browser_ui_based_harness_for_coding_and/)
---
### Practical & Community
**Trained a 117M parameters Silia model on an H100 in 5 hours.: r/LocalLLaMA**
A 117M-parameter Silia architecture model was trained from scratch on an H100 in five hours using the synth-100M dataset and the Muon optimizer. The model and code are available on Hugging Face and GitHub, with an inference script that runs via uv. It remains severely under-trained on only 82M tokens, so expect further scaling experiments from the community. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1upqmjt/trained_a_117m_parameters_silia_model_on_an_h100/)

**Qwen3.6-27B: NVFP4/FP8 agent loops vs flawless BF16. Config or quant issue?: r/LocalLLaMA**
Users report that Qwen3.6-27B in NVFP4 and FP8 quantization on Blackwell hardware with vLLM 0.24.0 exhibits mid-task halting and repetitive failure loops in thinking mode, while the BF16 version runs reliably. The issues appear less frequent in FP8 than NVFP4. Teams running agentic workloads should benchmark quantized checkpoints against BF16 before deploying. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1uplzs7/qwen3627b_nvfp4fp8_agent_loops_vs_flawless_bf16/)
---
### Under the Hood: Mixture-of-Experts Routing Tradeoffs
Everyone talks about MoE as a simple “activate fewer parameters, get free speed” trick. In practice the router must decide which experts to wake for every token, and that decision sits at the center of the efficiency story. A lightweight router network scores every expert and typically keeps the top-k; the cost of that scoring grows linearly with total expert count, so labs add auxiliary load-balancing losses during training to stop the router from always picking the same few experts. When the router is well-tuned, inference only loads the active experts into memory, which is why a 295B MoE can run at roughly the speed of a 30B dense model. The hidden cost appears at training time: every token still computes router logits across all experts, and poor routing can leave some experts under-trained, creating quality cliffs on out-of-domain data. The practical rule of thumb is to watch expert utilization histograms—if any expert sits below 1-2% activation you are wasting parameters and should either increase the load-balancing coefficient or reduce total experts. Teams choosing between dense and MoE should therefore measure both tokens-per-second at inference and the variance in expert activation during their target workload rather than trusting headline parameter counts.
---
### Things to Try This Week
- Try GPT-Realtime-2.1-mini through the OpenAI API for voice agent prototypes—lower latency and the new pricing make longer sessions practical.
- Pull Tencent’s Hy3 from OpenRouter before July 21 and run it on SWE-Bench-style tasks to see how the 21B active parameters compare with Qwen3.6-27B.
- Test Koder on a local Linux machine with your preferred coding model—its milestone planner and file-browser integration are worth evaluating for offline agent loops.
- Run the Neuronpedia J-space demo on an open-weight model you already host to inspect attention patterns without needing Anthropic infrastructure.
---
### On the Horizon
- More quantized checkpoints for Qwen3.6-27B are expected as Blackwell adoption grows.
- Additional open MoE releases from Chinese labs are likely following Hy3’s Apache 2.0 move.
- Watch for vLLM updates addressing the NVFP4 agent-loop instability reported this week.
- Anthropic’s full paper and expert commentary on J-space will likely spur similar interpretability experiments on other families.