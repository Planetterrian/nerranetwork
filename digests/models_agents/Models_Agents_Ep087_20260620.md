# Models & Agents
> **Virtuals just wired Leyten’s distributed GPU engine into its agent network to run GLM-5.2 at scale.**

**What You Need to Know:** Virtuals’ integration lets agents tap GLM-5.2 across a distributed GPU fabric. A major security report details active exploits against Langflow and related frameworks. Builders should audit any self-hosted agent tooling this week.
---
### Top Story
Virtuals integrates Leyten’s distributed GPU inference engine to run GLM-5.2 across its AI agent network. The move brings fast inference for the new GLM model directly into an existing agent orchestration layer. Leyten’s engine handles the distributed execution so agents can call the model without managing individual GPU clusters. Teams already running Virtuals agents gain immediate access to GLM-5.2 without new infrastructure. Watch for similar integrations from other agent platforms as GLM-5.2 availability spreads beyond the initial custom-silicon providers. Source: [Google News](https://news.google.com/rss/articles/CBMidkFVX3lxTE1MQXloSTlsdjIzTDViUkY2dGdMZy1fS3kwVEcxTWFIV2paQUVxUFZYZDdPd24zb1BzVmFPNTc4NVd0UTFrYzdCeUkxUFhOdVRudXpEMWE3QTc3Wm1RWGVqSzFWZ3FZZlhEd3pWS0dQYkV0MTgxTUE?oc=5)
---
### Model Updates
**VibeThinker-3B: A 3B Dense Reasoning Model Built on Qwen2.5-Coder-3B With the Spectrum-to-Signal Post-Training Pipeline: MarkTechPost**
VibeThinker-3B is a 3B-parameter dense model derived from Qwen2.5-Coder-3B via the Spectrum-to-Signal post-training pipeline. It reaches parity with DeepSeek V3.2 and Kimi K2.5 on verifiable reasoning benchmarks. The MIT license allows commercial use and fine-tuning. Builders working on code or math reasoning tasks should test it against larger models to see where the 3B size still delivers acceptable accuracy at lower cost. Source: [marktechpost.com](https://www.marktechpost.com/2026/06/19/vibethinker-3b-a-3b-dense-reasoning-model-built-on-qwen2-5-coder-3b-with-the-spectrum-to-signal-post-training-pipeline/)

**Studying FLUX in diffusers library was hard, so I built a smaller open-source version [P]: r/MachineLearning**
minFLUX provides a minimal PyTorch reimplementation of both FLUX.1 and FLUX.2 with explicit VAE and transformer components. The repo includes line-by-line mappings to the Hugging Face diffusers library plus complete training and inference loops using flow matching and Euler ODE steps. FLUX.2 improves transformer blocks, modulation, FFN, VAE normalization, and position IDs over the first version. Anyone studying modern diffusion architectures can clone the repo and run the provided loops locally without navigating the full diffusers abstractions. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1ub1db3/studying_flux_in_diffusers_library_was_hard_so_i/)

**DVD-JEPA: an open-source, fully-reproducible JEPA world model [P]: r/MachineLearning**
DVD-JEPA demonstrates a minimal Joint-Embedding Predictive Architecture on a simple bouncing-logo video task. A context encoder, EMA target encoder, and latent predictor learn 32-dimensional representations without labels or a decoder during training. Adding an optional decoder allows the model to “dream” correct future frames for roughly 20 steps before drift appears. The project runs entirely in the browser via a 40-line JavaScript reimplementation of the trained MLPs. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1uatlzx/dvdjepa_an_opensource_fullyreproducible_jepa/)

**An open handbook on LLM inference at scale (GPU internals, KV cache, batching, vLLM/SGLang/TensorRT-LLM) [P]: r/MachineLearning**
The handbook walks through GPU execution and memory hierarchy internals that determine inference throughput. New chapters cover why GPUs sit idle during generation and where memory bottlenecks actually occur, complete with Mermaid diagrams. The project remains a living document open to issues and PRs. Practitioners running production inference can review the latest chapter on GPU internals to refine their mental model of batching and KV cache behavior. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1uavduv/an_open_handbook_on_llm_inference_at_scale_gpu/)
---
### Agent & Tool Developments
**Virtuals integrates Leyten's distributed GPU inference engine to run GLM-5.2 across its AI agent network: Crypto Briefing**
Virtuals now routes GLM-5.2 calls through Leyten’s distributed engine so agents can execute without managing individual GPU nodes. The integration targets the same model Simon Willison flagged as desirable on fast custom silicon. Existing Virtuals users gain access immediately. Watch whether other agent platforms follow with similar distributed backends. Source: [Google News](https://news.google.com/rss/articles/CBMidkFVX3lxTE1MQXloSTlsdjIzTDViUkY2dGdMZy1fS3kwVEcxTWFIV2paQUVxUFZYZDdPd24zb1BzVmFPNTc4NVd0UTFrYzdCeUkxUFhOdVRudXpEMWE3QTc3Wm1RWGVqSzFWZ3FZZlhEd3pWS0dQYkV0MTgxTUE?oc=5)

**Sui Introduces Seal MPC for AI Agents on Mainnet: Cryptonews.net**
Sui deployed Seal MPC on mainnet to give AI agents secure multi-party computation capabilities. The feature lets agents perform joint computations without exposing private inputs. Teams building agent workflows that require shared secret handling now have a production-ready on-chain option. Source: [Google News](https://news.google.com/rss/articles/CBMiWkFVX3lxTE5DLVg3M3BNUXhwTDlYS3NjY0lEdjM5anA1YWtVdFltUWUzQmdXQ0VpWjVPYnF4VFhQSVRzUmU3dDAzYWVnT2l4YlBiR2plVWdRb1lHVlRDYXVvQQ?oc=5)

**NVIDIA AI Introduce SpatialClaw: A Training-Free Agent That Treats Code as the Action Interface for Spatial Reasoning: MarkTechPost**
SpatialClaw is a training-free agent that writes and executes Python inside a persistent kernel to solve 3D spatial reasoning tasks. It composes existing perception tools through code rather than learned policies. The approach removes the need for additional training while still handling complex spatial queries. Developers working on robotics or 3D scene understanding can experiment with the code-as-action pattern today. Source: [marktechpost.com](https://www.marktechpost.com/2026/06/19/nvidia-ai-introduce-spatialclaw-a-training-free-agent-that-treats-code-as-the-action-interface-for-spatial-reasoning/)

**Atomic Mail Releases Email Service That Lets AI Agents Register Their Own Inboxes With No Human Involvement: 24-7 Press Release Newswire**
Atomic Mail now allows agents to create and manage their own email inboxes autonomously. No human account creation step is required. The service targets agent workflows that need persistent, independent email identities. Source: [Google News](https://news.google.com/rss/articles/CBMi8wFBVV95cUxQOTdOd3RFZm85M0xFaWtYR1RRR2dMdHJSUjA3WUZkTnA3eFMxSFJpVXFtNEVzZ1YxdXVESGlIeUdpcVJVaE1CcFU1RXU3cmNRODNxTjhwUl93TXF3OThrdE1sWDg5b2hVaXFCemM2QWQ3QV9zUmN6RHNKbDlvUGpmMEg5UE15a0tOR2QzYXJpN2JjRlRxNGVNVm9vOE1BRF8xWncwTWY5ZF9kenczMHZqZGdaYlhqNF8tMElCelVUU0ZrMi1fZTl4QVJmQzM5cEZpNUtvWUZEVDZkVFZMdGE0bTZUYTdqQVJNcXpJZzVnbXNQSWs?oc=5)
---
### Practical & Community
**Claude Artifacts reimagined for Datasette with JSON API: Simon Willison (AI builder) (X)**
Datasette Apps gives developers the interactive artifact experience but backed by a full relational database and JSON API. HTML+JS applications can read and write structured data directly instead of relying on local storage. The project blog post includes live demo details and uv one-liners for local testing. Source: [x.com](https://x.com/simonw/status/2067759963322404896)

**Hi Reddit, I posted my Build Your Own LLM workshop to Youtube teaching ML, LLM and math intuition [P]: r/MachineLearning**
The recorded workshop covers the full LLM stack from perceptrons through pre-training, instruction tuning, and RL, using slides, Excel examples, and PyTorch code. No prior ML background is assumed beyond comfort with code. Slides and exercises are available for self-paced study. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1uazlnd/hi_reddit_i_posted_my_build_your_own_llm_workshop/)

**Yandex Open-Sources YaFF: A Zero-Copy Wire Format for Protobuf With Near-Struct Read Speed: MarkTechPost**
YaFF keeps the original .proto files unchanged while offering four memory layouts that let Protobuf data be read at near-struct speeds. The Flat layout achieves 1.2× the speed of a raw C++ struct in benchmarks. Production advertising systems have reported 10–20% CPU savings after adoption. Source: [marktechpost.com](https://www.marktechpost.com/2026/06/20/yandex-open-sources-yaff-a-zero-copy-wire-format-for-protobuf-with-near-struct-read-speed/)

**How to Build a Forecasting Pipeline with TimeCopilot Using Foundation Models and Automated Anomaly Detection: MarkTechPost**
TimeCopilot provides an end-to-end workflow that combines statistical, foundation, and GPU-accelerated models with rolling cross-validation and probabilistic forecasts. An optional LLM agent can select models and explain predictions. The tutorial uses real airline passenger data plus synthetic series with injected anomalies. Source: [marktechpost.com](https://www.marktechpost.com/2026/06/20/how-to-build-a-forecasting-pipeline-with-timecopilot-using-foundation-models-and-automated-anomaly-detection/)
---
### Under the Hood: Flow Matching in Diffusion Models
Everyone talks about flow matching as if it simply replaces the usual noise-prediction objective. In practice it reparameterizes the generative process as learning a velocity field that transports noise to data along straight paths in probability space. The core insight is that the model predicts the instantaneous direction of the probability flow rather than the score or noise; this removes the need for the variance-preserving schedule that dominated earlier diffusion formulations. Because the paths are straight, the ODE solver can take larger steps during inference, cutting the number of function evaluations needed for high-quality samples. The tradeoff appears in training: the velocity target must be estimated from paired noise-data points, which can increase gradient variance compared with the simpler noise-prediction loss used in standard diffusion. In the minFLUX implementation the training loop therefore encodes images with the VAE, computes the flow-matching velocity, and regresses against an MSE on that velocity. When to choose flow matching over classic diffusion therefore depends on whether your inference budget is dominated by solver steps or by training stability; the former favors flow matching, while the latter may still prefer the older formulation.
---
### Things to Try This Week
- Try Virtuals + Leyten integration if you already run agents that need fast GLM-5.2 access without managing GPUs yourself.
- Clone the minFLUX repo and run its training and inference loops to study FLUX internals without the full diffusers complexity.
- Test VibeThinker-3B on code or math tasks where you want DeepSeek-level reasoning at 3B scale and MIT-license terms.
- Walk through the Datasette Apps demo and uv one-liners to see how a relational backend changes what HTML+JS artifacts can do.
---
### On the Horizon
- More agent platforms are expected to announce distributed inference backends for GLM-5.2 following the Virtuals integration.
- Patches for LangGraph, Langflow, and LangChain-core are already available; teams should verify upgrades before the next wave of reported exploits.
- Yandex’s YaFF format may appear in additional Protobuf-heavy pipelines as the 10–20% CPU savings become more widely measured.
- Further open-source JEPA-style world models are likely after DVD-JEPA demonstrated a minimal, browser-runnable implementation.