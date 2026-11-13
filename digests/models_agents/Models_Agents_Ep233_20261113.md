# Models & Agents
> **Gemini 4 Hydrogen ships at $1.50/$7.50 per million tokens and powers the free tier plus Google Search.**

**What You Need to Know:** Google released Gemini 4 Hydrogen, the lowest-cost member of the Gemini 4 family, positioned for everyday coding and agent execution while Carbon and Argon handle deeper reasoning. Hydrogen currently offers only a 25% discount versus its siblings but will deliver a 75% discount after December 1 when Carbon and Argon double in price; it also underperforms on pelican generation tasks relative to the more expensive variants. Builders should test Hydrogen in multi-model workflows and watch the December 1 pricing shift.
---
### Top Story
Google launched Gemini 4 Hydrogen, the lowest-cost model in the Gemini 4 family, priced at $1.50 per million input tokens and $7.50 per million output tokens across its full 1-million-token context window. The model targets everyday coding, agentic workflows, and execution tasks, while Carbon and Argon remain the frontier options for deep architectural judgment. Hydrogen surpasses Argon on the Artificial Analysis Intelligence Index at its default high thinking level (51 versus 50) and reaches 54 at the highest xhigh setting, often completing tasks faster than peers in its class. It becomes the new free-tier model and the engine behind AI features in Google Search, with an Orchestrator tool in Google Antigravity that dynamically switches between Carbon and Hydrogen to cut quota use by 24% and finish 19% faster on Terminal-Bench 4.0. After December 1, Carbon and Argon double in price while Hydrogen stays flat, shifting its relative discount from 25% to 75%. Hydrogen is also the model that will power paid Google AI Pro and Ultra subscribers in Google Antigravity. Source: [blog.google](https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-gemini-4-hydrogen/) Source: [simonwillison.net](https://simonwillison.net/2026/Nov/12/llm-gemini/)

### Model Updates
**llama.cpp bumps version to 1.0.0: ggml-org/llama.cpp**
The project reached version 1.0.0 via a pull request from maintainer ggerganov. No additional announcement accompanied the bump at the time of the Reddit post. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1xv3cyt/llamacpp_bump_version_to_100_by_ggerganov_pull/)

**Artificial Analysis updates Qwen 3.8 Flash Next score to 29: r/LocalLLaMA**
The updated score places the model between GPT-6 Luna Max at 28 and Claude Haiku 5.5 High at 30. It sits closer to the larger Qwen 3.8 max variant (34) than to the 27B model (20). Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1xuxzfs/artificial_analysis_updated_qwen_38_flash_next/)

**Ernie 5.5 Flash Preview launches at 280B total parameters with 14B active: r/LocalLLaMA**
The model posts strong results on an aggregate "Agentic Coding" index built from 12 coding benchmarks. The index weights Terminal-Bench v4.0 at 16%, DeepSWE v1.1 at 15%, and FrontierCode 2.0 at 11%. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1xune1i/new_model_ernie_55_flash_preview_hits_strongly_at/)

**Anthropic files for initial public offering: [@AnthropicAI](https://x.com/AnthropicAI)**
The filing lists more than 11,900 customers generating at least $100K TTM revenue, a greater than 12x year-over-year increase in that cohort, and a 4x compute efficiency gain since Q1 2025. Net loss reached $23.3B, driven largely by a $21.9B non-cash charge tied to changes in the fair value of convertible notes, derivative liabilities, and SAFEs. Source: [ipo.anthropic.com](https://ipo.anthropic.com/us/)

**A100 prices fall 20-30% since earlier collapse reports: r/LocalLLaMA**
Sellers appear to be pricing more competitively to clear inventory ahead of Rubin and Blackwell GPUs that deliver 3-4x better efficiency per watt. The cards see limited use for inference outside enthusiast and small-scale rental markets. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1xuxbeb/a100_prices_down_2030_since_my_post_about_them/)

### Agent & Tool Developments
**CopilotKit Releases OpenBot 1.0: MarkTechPost**
OpenBot 1.0 is an MIT-licensed, self-hostable AI coworker workspace that lets companies bring their own agents, models, and infrastructure. Every bot action must pass a policy check and lands in an audit trail. Source: [marktechpost.com](https://www.marktechpost.com/2026/11/12/copilotkit-openbot-1-0-open-source-ai-coworker/)

**Limitless Labs CAM Agent arrives for engineers: Design News**
The tool targets computer-aided manufacturing workflows and is presented as part of a broader series on AI tools for engineers. Source: [designnews.com](https://www.designnews.com/artificial-intelligence/ai-tools-for-engineers-limitless-labs-cam-agent)

**Strata EXL3 AMD fork gains 10-20% decode speed on HIP kernels: r/LocalLLaMA**
The update adds optional local expert repacking for CPU-assisted inference and experimental MiMo V2.6 Flash support running at 25-30 tokens per second on two RX 7900 XTX cards with a 2.20 bpw MOPD quant. The 3.05 bpw EXL3 quant now reaches 87 tokens per second on two GPUs while matching roughly IQ4_K_XS quality. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1xv282p/strata_exl3_amd_updated_1520_tks_run_q4_at_q3/)

**HyperAccel to showcase LPU-based AI inference system at SC26: HPCwire**
The demonstration highlights the company's LPU hardware for inference workloads at the upcoming supercomputing conference. Source: [hpcwire.com](https://www.hpcwire.com/off-the-wire/hyperaccel-to-showcase-lpu-based-ai-inference-system-at-sc26/)

### Practical & Community
**How to make a Legora-style legal conflict detector tool using only NLI and encoder models: r/MachineLearning**
The pipeline enriches documents into hierarchical clause trees, embeds clauses, filters non-provision text, shortlists pairs above 0.5 cosine similarity, then scores with a reranker and NLI classifier to surface deviations and gaps. It completed pairwise review of Bob Iger’s 2011 and 2022 Disney agreements in under 20 seconds for the longest sampled pairs and is released under the MIT license. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1xuzv6d/how_to_make_a_legorastyle_legal_conflict_detector/)

**European open LLMs compared on languages and licenses: Pasquale Pillitteri**
The post evaluates open models from European labs across language coverage and licensing terms. Source: [pasqualepillitteri.it](https://pasqualepillitteri.it/en/news/32726/european-open-llms-compared-languages-licenses)

**RAG retrieval lost 40 points when distracting passages grew to 2.68M: Towards Data Science**
A reproducible test of BM25, embeddings, and parent documents shows retrieval performance degrades sharply as corpus size scales and demonstrates why author-written evals often overstate real-world search quality. Source: [towardsdatascience.com](https://towardsdatascience.com/rag-retrieval-lost-40-points-when-distracting-passages-grew-to-268m/)

**LLMON: An LLM-Native Markup Language now in Granite 4.1 3B and 8B: Hugging Face Blog**
IBM released experimental granite-4.1-3b-LLMON-preview and granite-4.1-8b-LLMON-preview models trained to consume and generate LLMON-marked text that explicitly tags instructions, data, and requirements. The approach reduces indirect prompt injection success rates to near zero on some benchmarks while preserving general capability relative to standard Granite 4.1 Instruct models. Source: [huggingface.co](https://huggingface.co/blog/ibm-granite/llmon-an-llm-native-markup-language-now-in-granite)

**I need feedback on this architecture for amodal raster-to-vector using a hybrid approach: r/MachineLearning**
The maintainer of Inkvec proposes a 1D CNN over closed outlines for node placement combined with a small network predicting full silhouettes as signed distance fields to handle hidden shapes. The project remains untrained and seeks prior work on amodal infilling and artist-style node conditioning. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1xutg9v/i_need_feedback_on_this_architecture_for_amodal/)

### Also Today
**An AI agent pitched a story to CBC Quebec. We replied to see what would happen: Yahoo News Canada** Source: [ca.news.yahoo.com](https://ca.news.yahoo.com/ai-agent-pitched-story-cbc-090000547.html)

**When AI agents become enterprise users, the infrastructure equation changes: ET CIO** Source: [cio.economictimes.indiatimes.com](https://cio.economictimes.indiatimes.com/news/brand-solution/when-ai-agents-become-enterprise-users-the-infrastructure-equation-changes/135793163)

**The AI Agents Can’t Find Anyone to Help Yet: Gizmodo** Source: [gizmodo.com](https://gizmodo.com/the-ai-agents-cant-find-anyone-to-help-yet-2000839258)

**Used datacenter/workstation GPU prices on eBay this week, ranked by $/GB of VRAM: r/LocalLLaMA** Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1xur9ud/used_datacenterworkstation_gpu_prices_on_ebay/)

**Gemma 3 builds a linearly decodable spatial map from text, but its answers never read it: r/MachineLearning** Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1xuqs9d/gemma_3_builds_a_linearly_decodable_spatial_map/)

**What if NeurIPS, ICML, and ICLR capped accepted papers at 1,000 each: r/MachineLearning** Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1xugl6c/what_if_neurips_icml_and_iclr_capped_accepted/)

**CVPR 2027 Author enrollment form: r/MachineLearning** Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1xue879/cvpr_2027_author_enrollment_form_d/)

**Creating author burdens to reduce paper submissions is STUPID: r/MachineLearning** Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1xul9u7/creating_author_burdens_to_reduce_paper/)
---

### Things to Try This Week
- Test Gemini 4 Hydrogen in Google AI Studio or the Gemini API for everyday coding tasks to see how its speed and 1M context compare with Claude Haiku 5.5 or GPT-6 Luna at current pricing.
- Clone the legal conflict detector cookbook and swap in your own NLI or reranker models to run clause-level pairwise review on contract pairs without quadratic generative calls.
- Try the Strata EXL3 AMD fork on RDNA3 hardware with the 3.05 bpw EXL3 quant to measure whether the 10-20% decode gains hold on your workload versus standard GGUF.
- Experiment with LLMON-tagged prompts on the new Granite 4.1 preview models to separate instructions from retrieved data and measure injection resistance on your own test cases.
- Run the open-source amodal raster-to-vector prototype on overlapping SVG logos to evaluate how well the signed-distance-field approach recovers hidden shapes before training your own small network.

### On the Horizon
- Carbon and Argon token prices double on December 1, shifting Hydrogen’s relative discount to 75%.
- HyperAccel will demonstrate its LPU inference system at SC26 later this month.
- CVPR 2027 requires a separate author enrollment form by the abstract deadline in addition to an OpenReview profile.
- European open-model comparisons continue to track new releases across language coverage and licensing terms.