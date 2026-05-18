# Models & Agents
> **NVIDIA's 4-bit pretraining technique cuts memory needs for large hybrid models while keeping accuracy nearly identical to FP8.**

**What You Need to Know:** NVIDIA released a full 4-bit pretraining stack (NVFP4) that was validated on a 12B Mamba-Transformer trained for 10 trillion tokens. The approach combines selective BF16 layers, Hadamard transforms, and stochastic rounding to stay within 0.04 points of an FP8 baseline on MMLU-Pro. Builders training long-horizon models on limited hardware should watch how this scales beyond the 12B proof-of-concept.
---
### Top Story
NVIDIA introduced a complete 4-bit pretraining methodology built around the NVFP4 microscaling format. The stack uses selective BF16 layers for critical weights, 16×16 Random Hadamard Transforms on gradients, 2D weight scaling, and stochastic rounding. It was validated on a 12B hybrid Mamba-Transformer trained across 10 trillion tokens—the longest publicly reported 4-bit pretraining run to date. Downstream accuracy stayed within 0.04 points of the FP8 baseline (62.58% vs 62.62% on MMLU-Pro). Teams running extended pretraining on constrained GPU fleets now have a documented path to cut memory and interconnect pressure without retraining from scratch. Watch for follow-up work on larger dense models and whether the same recipe transfers cleanly to pure transformer architectures. Source: [marktechpost.com](https://www.marktechpost.com/2026/05/18/nvidia-introduces-a-4-bit-pretraining-methodology-using-nvfp4-validated-on-a-12b-hybrid-mamba-transformer-at-10t-token-horizon/)
---
### Model Updates
**New models timing and open-weights trends:** r/LocalLLaMA
Community discussion after recent releases points to a likely window between late May and early June. Posters note a shift in how open-weight submissions are being handled and are watching for signs that major labs are extending the current cadence.

**Dialect-conditioned routing in MoE models:** r/MachineLearning
Tests on Qwen3.5-35B-A3B and its no-refusal fine-tune show register-dependent expert routing even before refusal layers activate. AAVE-coded safety prompts produced different first-token routing tensors and longer thinking traces than matched Academic English prompts, raising questions about whether refusal alone masks underlying safety gaps.

**Qwen3.6-27B inference on AMD hardware:** r/LocalLLaMA
Luce DFlash + PFlash delivered 2.24× decode and 3.05× prefill speedups versus llama.cpp HIP on an RX 7900 XTX. The optimal DDTree budget was 8 rather than the 22 recommended for Strix Halo, highlighting how GDDR6 bandwidth changes the best speculation strategy.
---
### Agent & Tool Developments
**SmallCode coding agent for local models:** r/LocalLLaMA
A new agent built specifically for 4B–14B local models reaches 87% on coding benchmarks by replacing chained tool calls with compound actions, automatic lint-and-fix loops, and on-demand escalation to larger models. It runs against LM Studio or Ollama endpoints and keeps 95% of work local.

**Code quality checks with small local models:** r/LocalLLaMA
Developers are exploring dedicated local models that read a TESTING.md or QUALITY.md file and continuously refactor generated code for security, readability, and maintainability without sending large codebases to cloud APIs.
---
### Practical & Community
**Respecting time with vibe-coded tools:** Simon Willison (AI builder)
Simon Willison argues that useful AI-generated tools save reviewers time while unedited LLM slop wastes it. He recommends including detailed terminal sessions that demonstrate exactly what was tried and how success was verified.

**Human direction for opinionated LLM text:** Simon Willison (AI builder)
Any LLM output containing opinions or anecdotes must be closely directed and reviewed by a human. Willison calls out examples where models falsely claim months of personal usage as particularly harmful.

**Nanochat video setup friction:** Andrej Karpathy
Karpathy noted that simply saying “boot an 8×H100” in a tutorial immediately blocks most viewers at step one, highlighting the gap between assumed hardware access and real-world availability.
---
### Under the Hood: Data Mixing as an Online Decision Process
Everyone talks about data mixing as a one-time hyperparameter you set at the start of training. In practice it is a recurring online decision that must be solved at every phase of the model lifecycle. The core insight is that you can cheaply simulate candidate mixtures by interpolating between low-rank adapters already trained on the current checkpoint instead of training separate proxy models. This keeps the search grounded in the model’s actual learning dynamics rather than an earlier snapshot. The method adds negligible overhead per decision yet finds mixtures that improve average perplexity by roughly 6% over static baselines during pretraining. In continual learning it matches full retraining or distillation performance while using 66–95% less compute. The practical takeaway is to treat mixing as a lightweight inner loop that runs every few hundred steps rather than a single upfront choice; the main gotcha is forgetting to re-evaluate when the data distribution or training objective shifts.
---
### Things to Try This Week
- Test the Luce DFlash + PFlash setup on your AMD card with Qwen3.6-27B to see whether budget=8 gives you the reported 2.24× speedup on short generations.
- Run SmallCode against a local 4B–7B model on a real codebase and compare failure rates to your current agent workflow.
- Add a short terminal-session block to your next project README to show exactly how you verified functionality, following Simon Willison’s recommendation.
- Experiment with OP-Mix-style low-rank adapter interpolation on your next continued-pretraining run to keep data mixing decisions current without extra proxy models.
---
### On the Horizon
- Community forecasts point to new open-weight model drops likely landing between late May and early June.
- Further scaling experiments on the NVFP4 4-bit pretraining recipe are expected once labs move beyond the 12B hybrid proof-of-concept.
- More work on dialect-aware safety testing for MoE models is likely after the recent routing-divergence findings.