# Models & Agents
> **Local builders can now treat markdown skill files as optimizable parameters with automated validation gates instead of manual tweaking.**

**What You Need to Know:** A new paper formalizes SkillOpt, using frontier models to propose bounded edits to markdown skills and accepting only those that improve a held-out validation set. Qwen3.5 and Qwen3.6 receive new uncensored and diffusion variants with detailed training notes for consumer hardware. Practical local setups gain concrete guidance on llama.cpp server flags, Intel NPU ASR, and MacBook stability tweaks. Builders should watch how validation-gated skill optimization and KV cache techniques change agent reliability this week.
---
### Top Story
SkillOpt turns ad-hoc markdown skill files into trainable parameters by using a frontier model to propose bounded add/delete/replace edits, then gating every change against a held-out validation set that only accepts strict improvements. Best skills converge after just 1–4 accepted edits out of many proposals, with an edit budget of 4–8 working best; removing the cap collapses performance. A skill optimized on Codex transferred to Claude Code with zero modification and gained +59.7 on SpreadsheetBench, while GPT-4.1 nano with an optimized skill roughly matched frontier performance on procedural tasks. The approach requires an auto-grader with clear correct answers, so it works for code and spreadsheets but breaks for open-ended work. Builders working on agentic code or spreadsheet tasks can now treat skills as first-class optimizable artifacts rather than static prompts. Watch for follow-up work that relaxes the auto-grader requirement. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1to1mey/skillopt_treats_markdown_skill_files_as_trainable/)
---
### Model Updates
**Qwen3.5 35B A3B uncensored heretic Native MTP Preserved: r/LocalLLaMA**
llmfan46 released Qwen3.5-35B-A3B-uncensored-heretic-v2-Native-MTP-Preserved in Safetensors, GGUF, NVFP4, and GPTQ-Int4 formats with all 785 MTPs preserved. The 35B and 27B variants show KL divergences of 0.0487 and 0.0308 respectively with accuracy losses of only 0.40% and 0.35%. The author notes Qwen3.5 targets general-purpose use while Qwen3.6 focuses on agentic and coding tasks, and Qwen3.5 tolerates higher KL divergence during abliteration without large quality drops. Builders wanting an uncensored general-purpose model with preserved thinking tokens should test the q4 or q6 GGUF variants this week. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tnzalm/qwen35_35b_a3b_uncensored_heretic_native_mtp/)

**Raon-Speech 9B SpeechLM: cs.CL arXiv**
Raon-Speech transforms a pre-trained LLM into a SpeechLM via speech-module alignment, end-to-end pre-training with knowledge distillation, and multi-task preference optimization on 1.38M hours of English and Korean data. It tops eight similarly sized audio foundation models across 42 English and Korean speech and text benchmarks while retaining strong text QA performance. Raon-SpeechChat adds full-duplex conversation via continual training on 119K hours of dialogue data. Teams needing bilingual speech understanding and generation should evaluate the open-sourced checkpoints. Source: [arxiv.org](https://arxiv.org/abs/2605.23912)

**talkie-1930-13b support in llama.cpp: r/LocalLLaMA**
A new pull request adds support for talkie-1930-13b-it, a 13B instruction-tuned model trained only on pre-1931 English text and further aligned with online DPO. The model enables historical role-play without modern knowledge contamination. Reference code and the Hugging Face repo are linked in the PR. Developers building vintage-language or time-period simulation agents now have a ready-to-run 13B option in llama.cpp. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tnyd13/model_add_support_for_talkie193013b_by/)

**Shard KV cache compression: r/LocalLLaMA**
Shard delivers a drop-in Hugging Face cache that reduces Llama-3.1-8B KV memory by ~10× at 8K context and 11× at 32K with no measurable degradation on NIAH or LongBench. It applies PCA plus int4 quantization to K (after undoing RoPE) and Hadamard rotation plus vector quantization to V, allowing attention to run directly on compressed keys. The repo is at krish1905/shard. Teams running long-context local inference should benchmark Shard against their current KV setup this week. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tnvo7r/shard_getting_to_10_kv_cache_compression/)
---
### Agent & Tool Developments
**Local LLM prompt injection testing habits: r/LocalLLaMA**
A detailed thread asks how local users test prompt injection and jailbreak resistance before wiring models to tools, files, RAG, shell commands, or browser automation. The discussion highlights that most current setups emphasize quantization, context length, and tokens-per-second while giving less attention to isolating tool access or logging calls. Builders moving local models into agentic workflows should adopt the read-only default and tool-call logging patterns raised in the thread. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1to25y5/are_local_llm_users_testing_prompt_injection/)

**Gartner on uniform governance for enterprise agents: CXOToday.com**
Gartner warns that applying uniform governance across all enterprise AI agents is a “death sentence” and recommends differentiated policies based on agent autonomy and risk. The report stresses that one-size-fits-all controls will slow adoption without improving safety. Enterprise teams evaluating agent platforms should review the governance segmentation guidance before standardizing policies. Source: [Google News](https://news.google.com/rss/articles/CBMinAFBVV95cUxOVk56RWpDOUJBTWVuSkN3MkMyTFNreWVWYy0xYmktY2hNRzVPWktZOVVZVTFvbk1kTVpwcTVnc0FJVWUwM2s2cWE2Rjk4NURkMURVU2E2d3BWb0doNzU2X0NEdkR4enFRQy1JV1ZpcEdMTTZiQVVFVVJvT2ZJQWg4cDdKNFVqaDVINV9kSTNraU1IempkYjhEY2ZRWjY?oc=5)

**Why most AI agents disappoint in production: InfoWorld**
The article outlines the primary production failure modes for agents and the first fixes teams should apply. It focuses on concrete engineering gaps rather than high-level strategy. Developers shipping agents should read the prioritized fix list before their next deployment review. Source: [Google News](https://news.google.com/rss/articles/CBMisgFBVV95cUxOWnI3WExiQnVWU1BsU2RaME1vdlJEUVExdTNIYUhnWk13U19JZ2wycUlpbkRyS1ZjOWdTZ3VRLVN1R0xXMVc3U0lkU21XUncyQW1YRGs3eTVWNk9YTF9CVFZVX25XVXVKMW1lUUFtWDBBcWoxeUZMN2FzRGNIZ3R4T1RJUUFNb3picFg0c1R6d2hWZWhwckYwOWhQRkxTenJsRllQZHNFZXpRVFZ1TzV2a2N3?oc=5)
---
### Practical & Community
**Intel Arrow Lake NPU for ASR: r/LocalLLaMA**
A user measured real-world ASR performance on an Intel Arrow Lake NPU versus CPU, showing 2.8–6.1× speedups and 10–21× lower energy for 10–60 s audio clips. The NPU setup also frees VRAM on a 7900XTX and beats a previous 3060 eGPU for short smart-home voice commands. The wyoming-parakeet-on-intel-npu repo is linked. Home Assistant or local voice developers should test the NPU path for always-on ASR workloads. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tnzjth/i_finally_put_my_npu_intel_arrow_lake_to_use/)

**llama.cpp server -np and -c flag interaction: r/LocalLLaMA**
The post explains how context is divided across parallel slots and asks about consequences of exceeding model max context or running two agents in parallel when VRAM allows. Practical questions cover performance, energy, and slot allocation. Anyone moving from LM Studio to llama.cpp server for multi-agent setups should review the flag interaction details. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1to1bf5/llamacpp_server_how_do_the_np_and_c_flags_interact/)

**Multimodal RLVR pipeline tutorial: MarkTechPost**
A step-by-step guide walks through loading the TuringEnterprises/Open-MM-RL dataset, building a reward function that checks exact matches, and exporting for GRPO. It covers schema inspection, domain analysis, and vision-language prompting. Developers starting multimodal reasoning projects with verifiable rewards can follow the pipeline directly. Source: [marktechpost.com](https://www.marktechpost.com/2026/05/26/design-a-complete-multimodal-rlvr-pipeline-with-open-mm-rl-vision-language-prompting-reward-scoring-and-grpo-export/)

**MacBook stability tweaks for Qwen3.6: r/LocalLLaMA**
A detailed post lists nine concrete changes—60 Hz refresh rate, GGUF over MLX, wired memory limit, preserve_thinking flag, OpenCode instead of Claude Code, and q8 KV cache minimum—that eliminated crashes and delivered 49–65 tok/s generation on a 14" M2 Max. The author shares exact fan curves and iogpu.wired_limit_m settings. Mac users struggling with long agentic sessions should apply the refresh-rate and memory-limit steps first. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tnzes2/running_on_a_macbook_and_having_issues_with/)
---
### Under the Hood: NPU Wake-Up Latency vs GPU Ramp-Up
Everyone treats NPUs as “marketing gimmicks” for LLMs, yet the real engineering story is about power-state transitions rather than raw TOPS. The core insight is that an NPU can exit deep sleep and begin useful work in a few milliseconds while a discrete GPU must ramp clocks, allocate buffers, and warm PCIe links. This difference only matters for short, bursty workloads; once the task exceeds a few seconds the GPU’s higher sustained throughput wins. In the measured ASR case the NPU delivered 4.8× lower latency and 10.7× less energy on 10-second clips precisely because it avoided the GPU’s ramp-up tax. The practical decision rule is simple: if average inference length is under ~3 seconds and you already have an NPU in the SoC, route the work there; anything longer or batch-oriented still belongs on the GPU. The gotcha most teams miss is that the NPU’s advantage disappears the moment you add a second concurrent stream, because its limited 13 TOPS cannot hide behind parallelism the way a larger GPU can.
---
### Things to Try This Week
- Test the SkillOpt edit-and-validate loop on a code or spreadsheet agent you already maintain; the 1–4 edit convergence pattern is worth reproducing.
- Run the Qwen3.5-35B-A3B-uncensored-heretic GGUF on your preferred backend and compare tool-call stability with and without preserve_thinking enabled.
- Measure your current llama.cpp server with -np and -c flags against the slot-division behavior described in the thread before scaling to multiple agents.
- Try the wyoming-parakeet-on-intel-npu setup on any Arrow Lake machine you have for short voice commands; the energy numbers are worth verifying locally.
- Apply the 60 Hz refresh-rate and wired memory limit changes on any MacBook running long-context Qwen sessions and re-measure prompt-processing time.
---
### On the Horizon
- More consumer-hardware diffusion LLM training runs are expected following the open-dllm and d3LLM code drops.
- Additional llama.cpp PRs for historical and vintage models will likely land as the talkie-1930 effort gains visibility.
- Follow-up work on validation-gated skill optimization is anticipated once more teams reproduce the auto-grader requirement.
- Expanded NPU integration examples for non-ASR workloads should appear as the Intel Arrow Lake results circulate.