# Models & Agents
> **Vercel’s UI SDK supplies agents with 50 behaviors for building accessible components across five frameworks.**

**What You Need to Know:** Vercel Labs released an Apache-2.0 beta library of 50+ UI behaviors that agents compose into components for React, Vue, Svelte, Solid, and Web Components. Agents using the bridge cut tool calls by 69% and task time by 61% on a settings task in Vercel’s tests. Builders should test the primitives on ui-sdk.dev this week to see how they reduce repetitive UI scaffolding for coding agents.
---
### Top Story
Vercel Labs released Vercel UI SDK, an Apache-2.0 beta library of 50+ UI behaviors that agents assemble into accessible components. The headless library ships primitives such as createRovingFocus, createTypeahead, createPopup, createSelection, and createReorder rather than finished components. Agents combine these behaviors with framework adapters for React 19+, Vue 3.5+, Svelte 5.33+, Solid 2 RC, and plain Web Components. In Vercel’s own test an agent completed a settings task with 69% fewer tool calls and 61% less time when using the direct UI bridge. The library includes prebuilt examples for Select, Combobox, Date Picker, Menu, Tree, and Color Picker, plus a prompt template agents can paste to learn the primitives. Behaviors are defined once with definePrimitive and rendered identically across all five adapters via createParts, so one behavior definition serves React, Vue, Svelte, Solid, and Web Components without duplication. The project ships six npm packages at version 0.1.0-beta.1 and runs in any modern browser with no GPU requirement. Source: [marktechpost.com](https://www.marktechpost.com/2026/11/13/vercel-ui-sdk-agent-ui-behaviors/)
---
### Model Updates
**I have trained a model to predict my blood sugar [P]: r/MachineLearning**
A 31,253-parameter encoder-only transformer was pretrained on 19,200 CGM-years of synthetic data from one million simulated type-1 diabetics, then LoRA-fitted to 115 days of the author’s personal CGM traces. The model predicts two hours ahead, infills missing segments, and performs backcasts while outputting blood-glucose values in Kovatchev risk space using combined DILATE, MSE, and pinball loss. It also learns to predict time-of-day from past traces once context exceeds 48 hours. The model accepts insulin units and carbohydrate grams with glycemic index as action curves, trains with learned Kendall-Gal weights, and maintains a native variable context window of 3.5 to 7.0 days. It remains weaker than the author at predicting hypoglycemia in the next 30 minutes. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1xvja5n/i_have_trained_a_model_to_predict_my_blood_sugar_p/)

**Scaling to 1T MoE on TorchTitan [P]: r/MachineLearning**
A ~1 T-parameter MoE reached 1,300 tokens per second per GPU on 384 GH200s using 384-way FSDP plus 4-way expert parallelism inside nodes. Full activation checkpointing with Grace offload, Muon optimizer, and FP8 expert all-gather delivered a 14× throughput gain over the team’s starting baseline. Newton-Schulz orthogonalization was moved onto GPU to cut the optimizer step from 42 s to roughly 2 s. The team replaced pipeline parallelism with FSDP plus expert parallelism to avoid long step times on InfiniBand, added node-local resharding of dense weights after the forward pass to keep the backward gather on NVLink, and routed allocations through the compute stream to free 13.5 GiB of peak memory. Group-limited routing kept expert load balanced but introduced a small training instability risk still under measurement. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1xvce5h/scaling_to_1t_moe_on_torchtitan_p/)
---
### Agent & Tool Developments
**Bolt PCHIE: a deterministic, tamper-evident safety harness for AI agents [P]: r/MachineLearning**
Every agent decision is appended to a hash chain so runs can be replayed and verified after the fact instead of trusted. Episodic memory writes are checked against the chain for tampering. The open repository is at https://github.com/wetwaferworks/bolt-pch-ie. The harness records every decision into the chain as it occurs, allowing full replay and verification of the agent’s execution history. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1xvyvbd/p_bolt_pchie_a_deterministic_tamperevident_safety/)

**Perplexity Teammates bring autonomous AI agents to the Mac app: Digital Trends**
Teammates are persistent agents that plan tasks, spawn additional agents when needed, and notify the user when work is complete. The feature, already live on the web, now runs in the Mac app and works on growth campaigns, bug triage, metrics tracking, and market research. Access requires the $200-per-month Max plan. Agents communicate through dedicated channels, maintain their own cloud instances, and continue working even after the user closes the computer. Source: [digitaltrends.com](https://www.digitaltrends.com/computing/perplexity-teammates-bring-autonomous-ai-agents-to-the-mac-app/)

**OpenAI has launched ChatGPT Wallet for AI-powered purchases: UkrMedia News**
ChatGPT Wallet lets “dots” agents find products, reach checkout, and pay after the user confirms with Face ID or fingerprint. Card details stay hidden from both the agent and merchants via tokenized payments; the service is rolling out first to selected U.S. ChatGPT Pro subscribers aged 18+. The system displays retailer, items, total, and payment method before each biometric confirmation, then generates a token that replaces actual card numbers and security codes while preserving existing rewards and consumer protections. Some merchants may still block automated purchases. Source: [ukrmedia.news](https://ukrmedia.news/en/science-tech/openai-chatgpt-wallet-pokupky-shtuchnyi-intelekt/)
---
### Practical & Community
**10 Recommendations for Building Strong Safety Evaluations: [@AnthropicAI](https://x.com/AnthropicAI)**
Anthropic’s engineering blog outlines how to design, run, and report safety evaluations that measure whether a model increases or decreases harm likelihood. The post draws on system-card experience and psychology’s replication reforms, stressing preregistration, multi-expert review, and clear documentation of sampling and grading methods. It distinguishes safety evals from capability measurements, notes that evals are easy to game and hard to reproduce, and recommends involving subject-matter experts alongside technical and methods specialists when deciding how to sample, grade, and analyze responses. Source: [anthropic.com](https://www.anthropic.com/research/building-strong-safety-evaluations)

**Google Releases TPU Sync: Open-Source KV Cache Transfer for TPUs: MarkTechPost**
TPU Sync is a C++ library that moves KV caches and weights across TPU HBM, host DRAM, storage, and network. Google reports more than 90% lower KV transfer latency on 235 B to 480 B MoE models. The library targets the movement of large KV caches and model weights between high-bandwidth memory, host memory, persistent storage, and network links in TPU clusters. Source: [marktechpost.com](https://www.marktechpost.com/2026/11/13/google-tpu-sync-kv-cache-transfer-library/)
---
### Also Today
**Databricks' Ken Wong says context, not model IQ, is what's blocking AI agents at work: BigGo Finance**
Wong argues that the 40-point accuracy gap on the BIRD benchmark disappears once explicit company-specific term mappings are supplied, showing that enterprise agent performance hinges on curated tribal knowledge rather than raw model scale. On the public BIRD leaderboard the top 50 entries all receive oracle knowledge of term definitions and reach nearly 90% accuracy, while the same systems drop to roughly 50% without it. Source: [finance.biggo.com](https://finance.biggo.com/news/06e36a7a2e12362a)

**Keyword Search Tied an 8B Embedding Model at Picking Agent Tools: Towards Data Science**
BM25 keyword search matched BGE-large accuracy on 200 ToolRet questions while running roughly 40× faster on CPU when full tool documentation was indexed. The test covered up to 3,794 tools and found that indexing complete tool documentation made the simple keyword approach competitive with the 8B embedding model. Source: [towardsdatascience.com](https://towardsdatascience.com/keyword-search-tied-an-8b-embedding-model-at-picking-agent-tools/)
---
---
### Things to Try This Week
- Install the Vercel UI SDK beta and paste the provided prompt into your coding agent to let it compose accessible components without hand-written ARIA.
- Clone the Bolt PCHIE repository and wrap an existing agent run to generate verifiable hash-chain receipts for audit or replay.
- Run the 1 T MoE TorchTitan recipe on a smaller node count to test the Muon-plus-FP8 path before committing to a full-scale job.
- Add BM25 alongside your embedding retriever for tool selection; the 40× CPU speedup is immediate on modest hardware.
- Load the personal CGM transformer from the GitHub repo and test its two-hour forecasts against your own continuous glucose data.
---
### On the Horizon
- OpenAI continues gradual rollout of ChatGPT Wallet to more U.S. Pro users; watch for expansion beyond “dots” agents.
- Anthropic’s safety-evaluation recommendations are expected to influence upcoming system-card releases.
- Perplexity Teammates on Mac may reach additional subscription tiers if usage data supports it.
- Databricks plans further Genie data-agent updates that incorporate the context-mapping work Ken Wong described.
