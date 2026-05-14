# Models & Agents
> **Faster pre-training without changing model architecture just became practical — Nous Research's Token Superposition Training cuts wall-clock time by up to 2.5x on models from 270M to 10B.**

**What You Need to Know:** Nous Research introduced Token Superposition Training, a two-phase method that averages token embeddings early then switches back to standard prediction. Open-source builders shipped a full cinematic video pipeline that runs end-to-end on a single AMD MI300X. New agent frameworks for belief tracking, automated evaluation, and multi-machine computer control also landed today.
---
### Top Story
Nous Research released Token Superposition Training (TST), a two-phase pre-training technique that averages contiguous token embeddings into bags during the first phase before reverting to standard next-token prediction. The approach works on dense models from 270M to 3B parameters and a 10B-A1B MoE without any architecture, tokenizer, or optimizer changes. It delivers up to 2.5x wall-clock speedups at matched FLOPs while preserving downstream performance. Teams doing continued pre-training or scratch training on mid-size models can now cut training time dramatically on the same hardware. Watch for follow-up work testing whether the same bag-averaging trick scales cleanly past 10B. Source: [marktechpost.com](https://www.marktechpost.com/2026/05/13/nous-research-releases-token-superposition-training-to-speed-up-llm-pre-training-by-up-to-2-5x-across-270m-to-10b-parameter-models/)
---
### Model Updates
**SOMA: Efficient Multi-turn LLM Serving via Small Language Model: arXiv**
SOMA trains a small surrogate model on the early turns of a conversation to handle the rest of the session, using soft prompts and localized LoRA fine-tuning. It keeps response quality while slashing latency and memory compared with always concatenating full history to a large model. The method includes a simple gate for one-time switching with rollback on drift. Source: [arxiv.org](https://arxiv.org/abs/2605.11317)

**Freeze Deep, Train Shallow: Interpretable Layer Allocation for Continued Pre-Training: arXiv**
LayerTracer analysis shows deep layers are both critical for task execution and highly stable, leading to the recommendation to freeze them and train only shallow layers during continued pre-training. This strategy beats full-parameter fine-tuning on C-Eval and CMMLU while preserving original knowledge. The work gives resource-constrained teams a concrete, interpretable rule for layer allocation. Source: [arxiv.org](https://arxiv.org/abs/2605.11416)

**A Study on Hidden Layer Distillation for Large Language Model Pre-Training: arXiv**
Hidden Layer Distillation was tested at scale with Gemma3 3.4B as teacher and students up to 735M parameters on 168B tokens. It produces consistent perplexity gains over standard logit-based distillation but does not reliably improve downstream tasks. The results suggest latent signals exist but need further breakthroughs to matter in practice. Source: [arxiv.org](https://arxiv.org/abs/2605.11513)
---
### Agent & Tool Developments
**Computer-use MCP that can control multiple machines: r/LocalLLaMA**
Opendesk lets AI agents see, click, and type across multiple local machines over WiFi with no cloud or accounts required. It works with Claude, Cursor, Codex, or custom harnesses and stays fully encrypted on the local network. Mac, Linux, and Windows builds are open source. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tcpgsv/computeruse_mcp_that_can_control_multiple/)

**An Empirical Study of Automating Agent Evaluation: arXiv**
EvalAgent encodes evaluation expertise as composable skills and produces complete evaluation artifacts including metrics, code, and reports. It raises first-run success (Eval@1) from 17.5% to 65% and wins 79.5% human preference over simple prompting baselines. The accompanying AgentEvalBench and meta-evaluation framework are now available for testing. Source: [arxiv.org](https://arxiv.org/abs/2605.11378)

**Agent-BRACE: Decoupling Beliefs from Actions in Long-Horizon Tasks: arXiv**
Agent-BRACE splits an LLM agent into a belief-state model that outputs structured natural-language claims with verbalized certainty and a policy model that acts on that compact belief. It improves performance by +14.5% on Qwen2.5-3B and +5.3% on Qwen3-4B in partially observable environments while keeping context size constant. Source: [arxiv.org](https://arxiv.org/abs/2605.11436)
---
### Practical & Community
**Built an open-source one-prompt-to-cinematic-reel pipeline on a single GPU: r/LocalLLaMA**
A complete pipeline using FLUX.2 [klein], Wan2.2-I2V, Qwen3.5-35B director, ACE-Step music, and Kokoro TTS turns one English sentence into a finished 720p video with characters, music, and narration in roughly 10 minutes on an MI300X. All components are Apache 2.0 or MIT and the full code is public. The vision critic with 10 structured failure labels enables automatic retries for common artifacts. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tcsqwk/built_an_opensource_oneprompttocinematicreel/)

**Checkup2Action: A Multimodal Clinical Check-up Report Dataset: arXiv**
The new 2,000-report benchmark tests generation of patient-oriented Action Cards that include priority, recommended department, time window, and safe questions for clinicians. Experiments reveal clear trade-offs between coverage, correctness, and safety alignment across general and medical LLMs. The dataset and evaluation protocol are released for further work. Source: [arxiv.org](https://arxiv.org/abs/2605.11533)
---
### Under the Hood: Layer-wise Stability in Continued Pre-Training
Everyone talks about continued pre-training as a uniform update across all parameters. In practice, layers behave very differently: deep layers execute the core task logic while remaining highly stable against disruptive changes. LayerTracer maps this by measuring where task execution actually occurs and how sensitive each layer is to new gradients. The result is a clear rule—freeze the deep stack and train only the shallow layers—which consistently beats both full fine-tuning and the opposite allocation on standard benchmarks. This works because deep representations already encode robust, general features that new data rarely needs to overwrite. The quality gain is largest on mid-size models where full updates are most expensive; above roughly 30B the relative benefit shrinks because the deep layers become even more stable. When you have limited compute and want to adapt a base model to a new domain, start by freezing everything past layer 70% and only tune the early transformer blocks. The gotcha that bites most teams is assuming uniform learning rates across depth—shallow layers need higher rates while deep layers need almost none.
---
### Things to Try This Week
- Clone the opendesk repo and pair two local machines to test cross-device computer-use agents with your existing Claude or Cursor workflow.
- Run the open cinematic pipeline on a single high-memory GPU if you have access to an MI300X or equivalent—start with the provided showcase reels before modifying the director prompts.
- Apply Token Superposition Training to your next 1B–10B pre-training run using the released two-phase schedule and compare wall-clock time against your current baseline.
- Test EvalAgent on one of your existing agent projects using the new AgentEvalBench to see whether the 65% first-run success rate holds for your specific evaluation needs.
- Experiment with Agent-BRACE-style belief claims on a long-horizon task in a partially observable environment to keep context size constant while tracking uncertainty.
---
### On the Horizon
- More labs are expected to release layer-allocation diagnostics following the LayerTracer approach for continued pre-training.
- Watch for production deployments of SOMA-style surrogate models in multi-turn agent serving stacks.
- Additional open-source computer-use MCP tools will likely appear as opendesk demonstrates the local-network pattern.
- Further agent evaluation frameworks building on EvalAgent’s skill-composition model are anticipated in the coming weeks.