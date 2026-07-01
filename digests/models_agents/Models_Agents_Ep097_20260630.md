# Models & Agents
> **Meituan just open-sourced a 1.6T MoE coding agent that ran the top OpenRouter leaderboard for two months while training entirely on Chinese ASICs.**

**What You Need to Know:** LongCat-2.0 delivers 59.5 on SWE-bench Pro (above GPT-5.5) with a 1M context window and zero-cost cache hits under an MIT license. Builders now have a commercially usable near-frontier agent model they can run or fine-tune without US GPU dependencies. Watch how quickly other labs adopt the LongCat Sparse Attention technique for their own long-context agents.
---
### Top Story
Meituan released LongCat-2.0, the 1.6-trillion-parameter MoE model previously known as Owl Alpha on OpenRouter. It activates 33-56B parameters per token, supports a native 1M-token context via LongCat Sparse Attention, and was trained on over 50,000 domestic Chinese ASICs. The model scored 59.5 on SWE-bench Pro, 70.8 on Terminal-Bench 2.1, and 77.3 on SWE-bench Multilingual while posting 10.1 trillion tokens processed during its anonymous run. It ships under a permissive MIT license with free context-cache hits and a limited-time $0.30/$1.20 per million token API promo. Enterprises can now run or modify a production-grade agentic coding model locally without recurring Western API costs or export restrictions. The next signal to watch is whether other Chinese labs follow with similar ASIC-trained releases and whether Western labs respond with their own open 1M-context agents. Source: [venturebeat.com](https://venturebeat.com/technology/meituan-open-sources-longcat-2-0-the-1-6t-near-frontier-agentic-coding-model-thats-been-leading-openrouter-trained-entirely-on-chinese-chips)
---
### Model Updates
**InternScience Agents-A1: r/LocalLLaMA**
A 35B MoE model called Agents-A1 appeared on Hugging Face with claims of frontier-level agentic performance. The accompanying tech report (arXiv:2606.30616) details its architecture but no public benchmarks have been independently verified yet. LocalLLaMA users are already asking for confirmation runs on standard agent harnesses. Builders working on multi-agent systems should test the weights this week to see whether the reported numbers hold under real tool-use workloads. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1ujhk93/internscienceagentsa1_hugging_face/)

**BERTomelo Portuguese encoder: cs.CL arXiv**
BERTomelo is a new monolingual Portuguese encoder built on the ModernBERT architecture with a 1,024-token context window and FlashAttention optimizations. It was trained on 106 million Portuguese documents and outperforms prior Portuguese encoders on STS and NER while remaining lighter than large multilingual models. The Base and Large checkpoints are released publicly. Teams building Portuguese-language retrieval or classification systems now have a drop-in ModernBERT-scale option without paying multilingual overhead. Source: [arxiv.org](https://arxiv.org/abs/2606.28999)
---
### Agent & Tool Developments
**Attemory retrieval hints for SWE-QA: r/LocalLLaMA**
A developer replaced online repository exploration with offline semantic search hints from Attemory before feeding Claude Code. On 720 paired SWE-QA samples across 15 repos the approach cut total tokens 43.8% while the official five-dimension judge score stayed statistically flat (83.39 vs 83.17). The method differs from FastContext by using prefill-only retrieval instead of a second trained explorer agent. Anyone running coding agents on large codebases can index once and reuse the same hint layer across many tasks without extra decode cost. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1uji3q9/notes_on_microsofts_fastcontext_and_a_small_sweqa/)

**SEATauBench multilingual agent eval: cs.CL arXiv**
SEATauBench adapts TauBench to five Southeast Asian languages and tests agents under progressively localized conditions. English-only agent scores transfer reasonably when only conversation language changes, but quality collapses once tool specs and task domains are also localized. The benchmark and adaptation pipeline are released on GitHub for anyone building reliable agents in linguistically diverse regions.
---
### Practical & Community
**Tesla V100 16GB local inference setup: r/LocalLLaMA**
A detailed guide shows single and dual NVLink V100-SXM2-16GB cards running Gemma 4 26B at ~100 tok/s in TCC mode and scaling to 8-16 concurrent agents at 150-175 aggregate tok/s under realistic 24k prompt loads. The write-up covers driver window (R570-R580), PSU transient requirements, and NVLink P2P measured at 33 GB/s. Builders wanting cheap offline coding agents now have concrete numbers and prebuilt binaries for a 32GB dual-card desktop rig. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1ujhtl9/tesla_v100_16gb_local_llms_single_and_dual_nvlink/)

**LongCat-2.0 on OpenRouter and Hugging Face: VentureBeat**
The model is now available under the same MIT license on GitHub and Hugging Face with the same aggressive context-cache pricing. Developers can immediately swap it into existing Claude Code or OpenClaw workflows for agentic coding tasks without new infrastructure.
---
### Under the Hood: Turn-Averaged Sparse Autoencoders
Everyone talks about sparse autoencoders as if they simply extract clean features from token activations. In practice the standard per-token approach scales linearly with context length, so a 100k-token transcript quickly becomes unusable for attribution graphs or manual inspection. Turn-averaged SAEs instead reconstruct the average activation across an entire Human or Assistant turn, collapsing the feature count to a fixed budget regardless of length. The resulting features are judged more complete by LLMs for describing high-level turn characteristics and make downstream attribution graphs far simpler to build. The tradeoff is loss of token-level granularity; the method works best when the goal is turn-level interpretability rather than pinpointing exactly which token triggered a behavior. Teams doing long-context analysis should reach for turn-averaged SAEs when context exceeds roughly 8k tokens and fall back to per-token SAEs only for short, high-precision debugging.
---
### Things to Try This Week
- Run LongCat-2.0 through its OpenRouter endpoint on a multi-file coding task to test the 1M context and free cache-hit pricing.
- Index a private repo with Attemory, add the retrieval hint layer, and measure token savings on your own SWE-style tasks.
- Set up the dual V100 rig following the linked guide if you need cheap offline agent concurrency without new hardware purchases.
- Download the SEATauBench adaptation scripts and run a quick localization test on any agent you maintain for non-English markets.
---
### On the Horizon
- More Chinese labs are expected to release ASIC-trained open models following Meituan’s playbook.
- Independent verification runs of Agents-A1 should appear on LocalLLaMA within days.
- Additional long-context interpretability techniques building on turn-averaged SAEs are likely in the next batch of arXiv interpretability papers.