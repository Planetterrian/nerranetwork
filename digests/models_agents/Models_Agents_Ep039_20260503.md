# Models & Agents
> **Mistral AI launches a 128B model with remote agents and strong coding performance.**

**What You Need to Know:** Mistral AI released Mistral Medium 3.5 alongside remote agents in Vibe for async cloud coding sessions and an agentic Work mode in Le Chat. The launch focuses on practical developer tools for building more autonomous coding workflows. Watch how these capabilities integrate into existing agent stacks this week.
---
### Top Story
Mistral AI has released Mistral Medium 3.5, a new 128B flagship model, together with Remote Agents in Vibe that support async cloud-based coding sessions. The model includes an agentic Work mode in Le Chat designed for structured developer interactions. This combination targets teams building AI agents that need reliable coding assistance without constant human oversight. Developers can now run longer autonomous sessions on cloud infrastructure while maintaining control through the platform's interface. The release marks a step toward more production-ready agent tooling from Mistral. Expect community experiments with the remote agent features to surface practical integration patterns soon. Source: [marktechpost.com](https://www.marktechpost.com/2026/05/02/mistral-ai-launches-remote-agents-in-vibe-and-mistral-medium-3-5-with-77-6-swe-bench-verified-score/)
---
### Model Updates
**DeepSeek V4 Leads Chinese Models in New Evaluation**  
The CAISI report identifies DeepSeek V4 as the strongest model currently available in China. It still trails leading US systems by roughly eight months according to the evaluation. The findings provide a snapshot of regional progress in open model development. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1t29wx0/caisi_releases_evaluation_report_deepseek_v4/)

**Qwen3.6-27B and Coder-Next Show Closely Matched Results**  
Extensive side-by-side testing on high-end GPUs found the two models perform similarly across many tasks. Coder-Next delivered better cost efficiency on bounded document tasks while the 27B variant handled certain research-style queries more effectively. The comparison highlights how different architectural choices trade off consistency against efficiency. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1t2ab5y/qwen3627b_vs_codernext/)

**Qwen 3.6 and Gemma 4 Reveal Distinct Vision Strengths**  
Local tests on M1 Max hardware showed Gemma 4 following formatting instructions more reliably for tasks like bounding boxes and Western cultural content. Qwen 3.6 performed better on video tracking and Asian context recognition but required strict 2 FPS preprocessing for video inputs. The results underscore how training data geography affects real-world behavior. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1t1te8y/qwen_36_wins_the_benchmarks_but_gemma_4_wins/)

**Ten Local Image Generation Models Compared on Mac**  
Tests across models from SD 1.5 through Flux dev, Qwen-Image, and Gemini evaluated photorealism, text rendering, and cultural accuracy on M1 Max hardware. Qwen-Image Lightning offered a strong speed-quality balance while Flux led in photorealism. Cultural biases appeared more tied to training data origins than model scale. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1t27cf0/local_image_generation_on_mac_10_models_compared/)
---
### Agent & Tool Developments
**Multi-Agent AI Workflow for Biological Network Modeling**  
The guide walks through constructing a multi-agent system that coordinates tasks across protein interactions, metabolism, and cell signaling simulations. Agents handle specialized sub-problems in a modular way that supports complex scientific workflows. Developers working in bioinformatics can adapt the pattern for other domain-specific orchestration needs. Source: [marktechpost.com](https://www.marktechpost.com/2026/05/02/build-a-multi-agent-ai-workflow-for-biological-network-modeling-protein-interactions-metabolism-and-cell-signaling-simulation/)

**FPGA Approaches for Speculative Decoding**  
Community discussion examines building FPGAs for models in the 20-30M parameter range with quantization and pairing them with speculative decoding using fast smaller models. The approach aims to deliver high token throughput at lower hardware cost. Questions remain around scaling beyond current limits and integration with existing inference stacks. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1t2asav/fpgas_for_speculative_decoding/)

**Fast Memory Mechanism on Frozen Small Transformers**  
A toy experiment demonstrates how a frozen Pythia-70M model can use forward-derived correction vectors for one-shot symbolic recall without any weight updates. The setup separates conflicting context meanings through learned retrieval geometry. It offers a lightweight path toward in-context adaptation that avoids full fine-tuning. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1t23wug/toy_experiment_frozen_pythia70m_can_use_a/)
---
### Practical & Community
**Complete Transformer Built in Pure C++17**  
A developer implemented a full GPT-style decoder-only transformer from scratch using only the C++17 standard library, including hand-written tensor operations, attention, and analytical backpropagation. The project trains on CPU with no external dependencies and includes an OpenMP-accelerated version. The repo provides a clear reference for understanding every layer of a transformer without framework abstractions. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1t1x9jv/i_built_a_transformer_in_c17_from_scratch_no/)

**SAE Fine-Tune of Qwen 3.5 Released on Hugging Face**  
The Qwen/SAE-Res-Qwen3.5-27B-W80K-L0_100 model provides a ready-to-use sparse autoencoder variant for vector-based steering experiments. It opens immediate access to mechanistic interpretability techniques on a 27B-scale model. Users can load it directly for research into activation steering and feature extraction. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1t22s9l/qwensaeresqwen3527bw80kl0_100_hugging_face/)

**Python Agent Connecting Qwen to LM Studio**  
A user built a Python agent via Claude that links Qwen 3.6 35B running in LM Studio to generate structured output for a 2025 tax return form. The agent reads input fields and produces a template without stopping until completion. It demonstrates quick agent scaffolding for domain-specific document generation tasks.
---
### Under the Hood: Tokenization Drift
Everyone talks about model outputs as if they flow directly from weights and prompt semantics, but the first step of turning text into token IDs often creates hidden variability. Tokenization maps strings to a fixed vocabulary of IDs, so even small formatting differences like extra spaces, line breaks, or punctuation produce different sequences. These ID changes shift the initial embedding vectors that enter the transformer, which then alters attention patterns and can send generation down entirely different paths. In RAG pipelines this shows up as inconsistent answers when the same query retrieves documents with minor formatting variations from different sources. The engineering tradeoff is that strict input normalization reduces drift but adds preprocessing latency and can occasionally remove useful signals present in the original formatting. Production teams typically insert canonical formatting early in the data pipeline to keep behavior predictable. The practical takeaway is to always test critical applications against varied input styles rather than assuming semantic equivalence guarantees identical tokenization.
---
### Things to Try This Week
- Test Mistral Medium 3.5 through Le Chat's Work mode on a multi-step coding task to evaluate the new remote agent capabilities.
- Run local vision comparisons between Qwen 3.6 and Gemma 4 using vLLM on your own image or video dataset to identify which model better matches your domain.
- Set up the multi-agent biological workflow on a small simulation problem to practice modular agent orchestration.
- Clone the C++ transformer repo and run the CPU training example to see every component of a model implemented without frameworks.
- Load the new SAE Qwen variant from Hugging Face and experiment with steering on a few test prompts.
---
### On the Horizon
- More real-world comparisons of vision models as local hardware and inference engines continue to improve.
- Additional hardware explorations around FPGAs and speculative decoding for cost-effective local inference.
- New fine-tuned and steering-focused releases on Hugging Face targeting popular base models.
- Expanded guides for multi-agent systems in specialized domains like scientific computing.