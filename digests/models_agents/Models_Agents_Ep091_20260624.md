# Models & Agents
> **Claude now joins teams as a persistent, org-wide Slack entity—the third major shift in LLM interaction after websites and desktop apps.**

**What You Need to Know:** DFlash delivers up to 15x throughput on NVIDIA Blackwell by drafting whole token blocks in parallel instead of autoregressive token-by-token generation. Qwen released two new AgentWorld MoE models trained to simulate tool, terminal, and GUI environments rather than chat directly. OpenAI opened applications for DevDay 2026 in San Francisco on September 29, with the keynote livestreamed.
---
### Top Story
UC San Diego's DFlash replaces standard speculative decoding with a lightweight block diffusion model that drafts entire token blocks in one forward pass. It conditions on target model hidden features via KV injection and ships with 20 checkpoints plus support for SGLang, vLLM, and TensorRT-LLM. The approach reports up to 6.08x lossless speedup on Qwen3-8B and NVIDIA-measured peaks of 15x throughput on Blackwell hardware at fixed interactivity. Builders working on high-throughput inference pipelines can now test the integration without custom drafting logic. Watch for community benchmarks on other model families and whether the block-diffusion drafting generalizes beyond the reported setups. Source: [marktechpost.com](https://www.marktechpost.com/2026/06/24/dflash-speculative-decoding-drafts-whole-token-blocks-in-parallel-for-up-to-15x-higher-throughput-on-nvidia-blackwell/)
---
### Model Updates
**Qwen-AgentWorld-35B-A3B: Source r/LocalLLaMA**
Qwen released a 35B-parameter MoE with only ~3B active parameters per token, trained to predict environment responses after agent actions across MCP, terminal, SWE, Android, web, and OS GUI domains. It functions as a language world model for simulating the observation side of agent loops rather than a chat model. The release includes a Hugging Face checkpoint and is positioned for offline evaluation, synthetic trajectory generation, and sandbox testing. Builders can use it to generate training data or validate tool-use workflows without repeatedly calling real environments. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1ue5149/qwenagentworld35ba3b_a_3bactive_moe_trained_to/)

**Unlimited-OCR 3.3B: Source r/LocalLLaMA**
Baidu open-sourced Unlimited-OCR, a 3.3B multilingual model under MIT license that performs one-shot full-document parsing on single images, multi-page documents, and PDFs. It supports 32K output length and offers base and gundam image modes for different layouts, with inference available via Transformers or SGLang with OpenAI-compatible streaming. The model targets deeper document understanding beyond cropped-region OCR. Teams handling long PDFs or mixed-language archives should test it this week against current pipelines. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1ue51uk/unlimitedocr_is_now_on_modelscope_a_33b/)

**Qwen-AgentWorld-397B-A17B: Source r/LocalLLaMA**
A larger sibling to the 35B model appeared on Hugging Face and the Qwen blog, maintaining the same environment-simulation training objective across agent interaction domains. Early discussion centers on its potential for higher-fidelity trajectory synthesis at scale. No detailed benchmarks were released with the announcement. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1ue56em/qwenagentworld397ba17b/)

**EXPO-SQL: Source arXiv**
The new EXPO-SQL method adds clause-level rewards derived from execution results and error messages to reinforcement learning for Text-to-SQL, replacing uniform query-level rewards. It shows consistent gains over supervised fine-tuning, prompting, and prior RL baselines on standard benchmarks. Code is available at the linked GitHub repository. Source: [arxiv.org](https://arxiv.org/abs/2606.23693)
---
### Agent & Tool Developments
**Claude Tag: Source Andrej Karpathy**
Karpathy described Claude Tag as the third major LLM UI/UX paradigm: a self-contained, persistent, asynchronous entity with org-wide tools, memory, and context that integrates directly into Slack. Once engineering work for security, compute, and integrations is complete, teams can interact with it conversationally across workloads. The approach moves beyond website or desktop-app models toward inline team participation. Source: [x.com](https://x.com/karpathy/status/2069547676849557725)

**Enterprise AI coding tool: Source Andrej Karpathy**
Karpathy highlighted an enterprise-grade coding system that writes the majority of code in team settings, deeply integrated and multiplayer inside Slack. It differs from simple RAG-over-Slack or OpenClaw-style tools by functioning as a shared workspace where participants act more like managers. The product has moved past hackathon stage through internal iteration and now supports real deployments. Source: [x.com](https://x.com/karpathy/status/2069601818540392669)

**Circle USDC machine payments spec: Source 디지털투데이**
Circle published a USDC specification for a machine payments protocol aimed at AI agent transactions. The spec targets automated, machine-to-machine payments without human intermediaries. Early details focus on protocol design rather than live implementations. Source: [Google News](https://news.google.com/rss/articles/CBMixwFBVV95cUxQUm5tMzgtaFNlcWVPY3oxSGZMdzNFQWRXTDRFbGpXU3dXYUxRR2pmRXZpQXVKZndPSkljRXhOd0NXaHVLVjlKS3ZYV3BrcVFESDQ5djNKb1dCZHpPdDZOd3RiQ0NUQ3hwdGYwaGVqMnFCYVNfNmlONVVULXd3a3hPNm1ZUEQ0dERzTXZWRm13MTRqeTZ2MWtuTlQ2VHI0QkhwRy1CTmR3aUp0VVBBSGZpSGJlUHBVMTZfM0xxcENNSnZIMnE2NV9n?oc=5)
---
### Practical & Community
**OpenAI DevDay 2026: Source [@OpenAI](https://x.com/OpenAI)**
Applications are now open for the September 29 event in San Francisco, with the opening keynote available via livestream for remote attendees. The deadline is July 10. Developers planning to attend or watch should apply soon. Source: [x.com](https://x.com/OpenAI/status/2069483224158646739)

**PCIE 5.0 split testing: Source r/LocalLLaMA**
A user is experimenting with splitting a PCIe 5.0 16x slot into 2x8 using a riser to run both an RTX 5070 Ti and an RTX 4070 in one system for daytime agent workloads and evening gaming. Generation speeds remain acceptable at 16k context but slow at 128k; the post asks whether the split impacts the primary GPU. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1ue5fgm/pcie_50_16x_split_into_2x8_with_riser_cable/)

**ModTGCN: Source arXiv**
The ModTGCN paper introduces a modularity-aware graph neural network for text classification that adds a modularity-based auxiliary loss to encourage class-coherent document communities. It decouples the TextGCN graph for 2-10x faster training and reports gains on low-homophily datasets. Source: [arxiv.org](https://arxiv.org/abs/2606.23694)
---
### Under the Hood: Clause-Level Rewards in RL for Text-to-SQL
Everyone talks about reinforcement learning for Text-to-SQL as simply "add execution feedback and improve." In practice, the reward design itself determines whether the model learns to fix individual clauses or just guesses whole queries.  
Standard methods assign a single scalar reward to the entire generated SQL, so a query with one wrong WHERE clause and correct SELECT/JOIN still receives the same penalty as a completely broken query. EXPO-SQL instead parses execution errors and runs incremental clause execution to tag exactly which clauses failed.  
This produces per-clause learning signals that let the policy gradient update only the faulty parts while reinforcing correct ones. The engineering cost is extra execution traces per training example, but the paper shows this finer granularity outperforms both SFT and prior RL baselines on standard benchmarks.  
The approach works best when execution feedback is cheap and deterministic; in domains where queries are expensive or non-deterministic, the clause-level signal becomes noisy. Teams should prefer it when they already have reliable database sandboxes and want to squeeze more signal from each failed generation.
---
### Things to Try This Week
- Test DFlash integration in vLLM or TensorRT-LLM on a Blackwell instance if you run high-volume inference and want to measure the reported 6-15x throughput gains.
- Download the Qwen-AgentWorld-35B-A3B checkpoint and use it to generate synthetic trajectories for your own agent training loop instead of calling live tools every time.
- Apply for OpenAI DevDay 2026 before the July 10 deadline if you want to attend or watch the keynote on new developer tooling.
- Try Unlimited-OCR on a multi-page mixed-language PDF to compare full-document parsing speed and accuracy against your current pipeline.
---
### On the Horizon
- OpenAI DevDay 2026 keynote on September 29 with remote livestream option.
- Continued releases from the Qwen AgentWorld family as more environment-simulation checkpoints appear.
- Further community testing of DFlash across additional model families and serving frameworks.
- Potential follow-up work on clause-level RL signals in other structured generation tasks beyond Text-to-SQL.