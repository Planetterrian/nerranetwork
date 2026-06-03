# Models & Agents
> **NVIDIA's Cosmos 3 pairs an autoregressive reasoner with a diffusion generator so builders can now train agents that jointly reason about physics, generate worlds, and output actions.**

**What You Need to Know:** NVIDIA released Cosmos 3, a two-tower omnimodal world model for physical AI. H Company dropped the Holo3.1 family of Qwen 3.5-based VLMs for computer-use agents across web, desktop, and mobile. Nous Research shipped Hermes Desktop, a native GUI front end for its agent CLI, while Microsoft launched Scout, an autonomous agent for Microsoft 365 built on OpenClaw.
---
### Top Story
NVIDIA released Cosmos 3, an open omnimodal foundation model that pairs an autoregressive VLM reasoner with a diffusion generator in a two-tower Mixture-of-Transformers architecture. The model unifies physical reasoning, world generation, and action generation for physical AI applications. It targets developers building agents that must understand dynamics, simulate environments, and produce executable actions in one pipeline. Builders working on robotics, simulation, or embodied agents can now start from a single pretrained checkpoint instead of stitching separate perception and control models. Watch for fine-tuning recipes and early agent benchmarks on physical tasks in the coming weeks. Source: [marktechpost.com](https://www.marktechpost.com/2026/06/03/nvidia-releases-cosmos-3-a-two-tower-mixture-of-transformers-foundation-model-unifying-physical-reasoning-world-generation-and-action-generation/)
---
### Model Updates
**Holo3.1 35B/9B/4B/0.8B (Qwen 3.5 finetunes): H Company**
Holo3.1 is a family of vision-language models fine-tuned from the Qwen 3.5 series specifically for computer-use agents. Sizes range from 0.8B to 35B-A3B parameters with native function calling and support for web, desktop, and mobile environments. Quantized checkpoints (BF16, FP8, NVFP4, Q4 GGUF) enable local deployment. Builders should test the 9B or 4B variants first for UI grounding and mobile automation tasks where the smaller models already deliver strong results. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tvg5x5/holo31_35b9b4b08b_qwen_35_finetunes/)

**Mellum & Granite Embedding models on llama.cpp: llama.cpp contributors**
The latest llama.cpp builds now support Mellum and Granite embedding models through two merged PRs. Users can run these models with the same binary that handles their main LLMs, removing the need for separate embedding servers. The update is immediately useful for teams already on llama.cpp who want consistent quantization and KV-cache behavior across retrieval and generation. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tvfldm/mellum_granite_embedding_models_are_ready_on/)
---
### Agent & Tool Developments
**Hermes Desktop: Nous Research**
Hermes Desktop provides a native cross-platform GUI that shares the same agent core, skills, and memory as the Hermes Agent CLI v0.15.2. It adds streaming tool output without requiring a terminal. The release targets users who want the full Hermes agent experience without managing CLI sessions. Early testers should watch for how well the shared memory layer handles long-running multi-turn tasks across GUI and CLI modes. Source: [marktechpost.com](https://www.marktechpost.com/2026/06/03/nous-research-releases-hermes-desktop-a-native-cross-platform-front-end-for-hermes-agent-v0-15-2-with-streaming-tool-output/)

**Microsoft Scout: Microsoft**
Microsoft launched Scout, an autonomous AI agent built on OpenClaw that operates inside Microsoft 365. It handles multi-step workflows across Outlook, Teams, and SharePoint without constant user supervision. The agent is positioned for enterprise users who need reliable execution inside the Microsoft ecosystem rather than general web agents. Early adopters should test its sandbox constraints on sensitive mailbox and calendar operations. Source: [Google News](https://news.google.com/rss/articles/CBMivgFBVV95cUxPSDhGN2JjNWprekJfbmpnMnk1TFFkbjZnVGxWYnJ0QkYxakM4WTJER3ViTjNpUF9KUmlmYlExUndmV0RJb3k5NVE0TUl1SVNXSXlLWU04elgtT2xPbkFPZmpHT2RiUHUwMHB1QjZzaWtLSmxRZFNTSDQzNEJxdE9BSjdpOElRdGR6QkFCSXZmXzRyQUdhR0NJOEFkZWViYWFzdnZWbGZLQmxkNkR5emRQVnpJVlRKVFN0a2pSaHB3?oc=5)

**Codex plugins (public equity, sales, creative production): OpenAI**
OpenAI released three purpose-built plugins for Codex covering public equity investing, sales workflows, and creative production. Each plugin turns natural-language prompts into domain-specific Codex actions. Teams already using Codex can activate the relevant plugin to reduce prompt engineering for those verticals. The sales plugin in particular targets faster prep and smarter outreach sequences. Source: [x.com](https://x.com/OpenAI/status/2061888058459570279)
---
### Practical & Community
**llama.cpp b9455 with tensor-split on 2x3090: community tester**
A detailed benchmark shows llama.cpp build b9455 achieving 70+ tokens/s on Qwen3.6-27B-MTP with tensor-split across two RTX 3090s and MTP speculative decoding. The setup uses unified KV cache and flash attention for long contexts up to 262k tokens. Users running dual-GPU consumer hardware now have a concrete configuration to match or exceed earlier vLLM results on the same cards. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tvff62/another_shout_out_to_llamacpp_build_b9455_2x3090/)
---
### Under the Hood: Context-Free Value Vectors in Deep Attention Layers
Everyone assumes attention layers always need the full residual stream to compute value vectors. In practice, the deepest layers often perform better when they learn a context-free lookup table of token-specific values instead. The core insight is that preserving the original token embedding without mixing in surrounding context reduces noise once the model has already built rich representations in earlier layers. This Bank of Values approach stores the values as sparse parameters, eliminating repeated computation and KV-cache pressure for those layers. The quality gain is largest in the final third of the network; adding the context-dependent component back on top yields almost no extra benchmark improvement. Teams should consider switching the last 8–10 layers to this pattern when memory or latency is the binding constraint, especially on models under 1B parameters where full context mixing is expensive relative to the benefit.
---
### Things to Try This Week
- Test the 9B Holo3.1 checkpoint on a mobile automation workflow to see how native function calling changes your agent scaffolding.
- Spin up Hermes Desktop alongside the CLI version on a long-running research task to compare memory persistence across interfaces.
- Run the new Mellum embeddings through your existing llama.cpp retrieval pipeline and measure recall lift versus your current embedder.
- Activate the sales plugin in Codex on a real outreach sequence and compare token usage against your hand-crafted prompts.
---
### On the Horizon
- More organizations are expected to receive Claude Mythos Preview access through the expanded Project Glasswing program.
- Additional Cosmos 3 fine-tuning examples and agent benchmarks are anticipated from NVIDIA in the next two weeks.
- Further quantized releases for the Holo3.1 family are likely as the community tests the 0.8B and 4B variants on edge devices.