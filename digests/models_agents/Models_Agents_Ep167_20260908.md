# Models & Agents
> **Mistral just closed Europe’s largest venture round at a $24B valuation, giving builders a new well-funded open-weight contender to test against closed frontier models.**

**What You Need to Know:** Mistral raised €3B in a Samsung-led round that pushes its valuation past $24B, with the company signaling a shift toward larger-scale training. Arm simultaneously unveiled a new AI-native compute platform and Neoverse CSS N4 aimed at agentic workloads and mobile graphics. Local builders reported concrete inference gains on Qwen3.8-Flash-Next and new embedding-migration tools that avoid full re-indexing.
---
### Top Story
Mistral AI raised €3 billion in Europe’s largest venture funding round, led by Samsung, lifting the company’s valuation above $24 billion. The round supports Mistral’s strategy shift toward larger models and expanded infrastructure. Multiple outlets confirm the same core terms: $3.5 billion total raise, Samsung as lead investor, and explicit positioning against U.S. frontier labs. The company stated the capital will accelerate training runs at greater scale than prior releases. Builders now have a better-capitalized European open-weight option with clearer long-term roadmap visibility. Watch for the next model release cadence and any new licensing terms that affect commercial deployment. Source: [nytimes.com](https://www.nytimes.com/2026/09/08/business/mistral-ai-fund-raising.html)
---
### Model Updates
**Mistral AI Exceeds $24 Billion Valuation After Samsung-Led Investment Round: WSJ**
The company closed a round that values it at more than $24 billion. Samsung led the investment. The announcement aligns with earlier Reuters and Times reporting on the same €3 billion raise. The funding round is described as Europe’s largest venture round to date. Mistral indicated the proceeds will fund a shift in strategy focused on scaling model training. No immediate changes to existing model licensing were announced alongside the round. Source: [wsj.com](https://www.wsj.com/tech/ai/mistral-ai-exceeds-24-billion-valuation-after-samsung-led-investment-round-ea377b82)

**Arm introduces new AI-native compute platform built for agentic AI and mobile graphics: Arm Newsroom**
Arm released a new compute platform targeting agentic AI workloads alongside mobile graphics. The platform includes the AGI CPU and Neoverse CSS N4. It is positioned for both edge and infrastructure deployments. Arm described the platform as AI-native and built specifically for the agentic era. The release includes support for mobile graphics alongside the agent-focused silicon. Early partner sampling is expected in the coming months. Source: [newsroom.arm.com](https://newsroom.arm.com/news/arm-css-for-mobile-2-agentic-ai-mobile-graphics)

**Qwen3.8-Flash-Next on 2x3090: 9–12% faster decode at ~119k context, with a completed quality screen: r/LocalLLaMA**
A local build swap from full-row sorting to radix-selection top-k cut median decode time from 30.2 t/s to 33.3 t/s at 119k context on dual 3090s. The change affects only the sparse-attention indexer fallback path. A 480-request quality screen showed no consistent regression versus the prior build. Three seeds were tested with 42 requests each per arm. Control accuracy reached 235 out of 240 correct while the candidate reached 238 out of 240. The disputed question involved listing twelve items and was omitted equally by both builds. The improvement is now running in the submitter’s production setup on the same 2x RTX 3090, dual Xeon E5-2696 v4, 128 GB DDR4-2133 hardware with UD-Q4_K_XL and 150 expert-cache slots. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1wacae2/qwen38flashnext_on_2x3090_912_faster_decode_at/)

**Voice conversations between Gemma4 12B and E2B on GPU and Jetson Orin: r/LocalLLaMA**
Gemma 4 12B runs on an RTX PRO 4500 Blackwell while the E2B variant runs on Jetson Orin NX 16GB. Cortexist Little Gemma handles inference in C for CUDA devices and supports lip sync, expressions, and gestures. The full pipeline and engine source are open source. Similar performance is expected on Jetson Orin Nano Super 8GB. The engine is reported faster than llama.cpp on Jetson Orin with no degradation after long voice prompts. Both systems use a reSpeaker Flex 4-mic array and a 3W speaker. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1waefz4/voice_conversations_between_gemma4_12b_and_e2b_on/)
---
### Agent & Tool Developments
**Airties Introduces Aura: Agentic AI Engine for Connected Intelligence: PR Newswire**
Airties released Aura, an agentic AI engine designed for connected intelligence use cases. The engine targets network and device orchestration scenarios. No specific install commands or benchmarks were included in the announcement. The release positions Aura as a platform for agentic workflows across connected devices. Airties described the engine as enabling connected intelligence without detailing underlying model choices. Source: [prnewswire.com](https://www.prnewswire.com/news-releases/airties-introduces-aura-agentic-ai-engine-for-connected-intelligence-302870301.html)

**S2W launches DRI autonomous AI agent for criminal investigations: 디지털투데이**
S2W announced DRI, an autonomous AI agent built for criminal investigation workflows. The release adds to prior coverage of no-code agent platforms but introduces domain-specific investigative tooling. Details on model backend or deployment remain limited in today’s reporting. The agent is described as fully autonomous within the criminal investigation domain. No new information on licensing or integration requirements was provided. Source: [digitaltoday.co.kr](https://www.digitaltoday.co.kr/en/view/101252/s2w-launches-dri-autonomous-ai-agent-for-criminal-investigations)
---
### Practical & Community
**My lab found a way to migrate between embedding models with zero downtime: r/MachineLearning**
Embedflow lets teams upgrade embedding models on up to one billion documents without full re-indexing. The method reranks K documents from the old index with the new model; at K=50 the retrieval quality matched the target model on tested migrations. The package is available via pip and works with Qdrant. The lab tested 63 migrations on up to one million documents. The best result came from upgrading Qwen4B to 8B at 50 documents. The approach avoids the 108-day backfill estimated for one billion vectors on an H100. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1wabmm7/my_lab_found_a_way_to_migrate_between_embedding/)

**For Strix Halo - Official llama.cpp isn't ideal and how to highest possible throughput: r/LocalLLaMA**
Three community forks deliver substantially higher throughput than official llama.cpp on Strix Halo hardware with Qwen 3.8 Flash Next. Halogen-flash-server reaches ~50 t/s decode and 1200 t/s prefill at 90% of theoretical peak. Another fork hits ~60 t/s decode and 600 t/s prefill at 80% of theory. Official llama.cpp is reported at 2x t/s decode and 2xxt/s prefill on the same model and hardware. All three forks are optimized specifically for Strix Halo and Qwen 3.8 Flash Next. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1wa9m61/for_strix_halo_official_llamacpp_isnt_ideal_and/)

**I reduced image-processing token usage by ~95% compared with GPT-4o direct vision, while maintaining roughly the same accuracy: r/MachineLearning**
A new preprocessing approach cut image tokens by approximately 95% versus sending raw images to GPT-4o while holding accuracy steady on the MOMA Graph benchmark of 1,315 questions. Implementation details are not yet public as the method is still under development. The submitter is seeking feedback on whether the result would be considered meaningful across larger benchmarks. No latency or API cost numbers beyond the token reduction were reported. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1wab7ui/i_reduced_imageprocessing_token_usage_by_95/)
---
### Under the Hood: Sparse Attention Top-K Selection in Long-Context Decode
Long-context sparse attention models often hide a simple but costly implementation choice in the top-k selection step that picks which tokens to attend over. The default path in many CUDA builds falls back to a full-row sort when newer CUB DeviceTopK primitives are unavailable, turning an O(n) selection into an O(n log n) operation per committed token. Replacing that fallback with a radix-selection implementation drops the kernel time from roughly 5.1 ms to 0.25 ms per token on wide rows, which translated into a measured 9–12% median decode throughput gain at 119k context on dual 3090 hardware. The improvement stays confined to the indexer and does not change model quality when the rest of the pipeline remains fixed. The gain disappears once the build already links against a newer CCCL that supplies the optimized DeviceTopK path natively. Teams running older CUDA 12.0 toolchains on long-document workloads should check whether their top-k path is still using the sort fallback before assuming sparse attention is inherently slow. The 8,192-column threshold used in the tested build is one practical setting that avoids the expensive sort while preserving the sparse attention pattern.
---
### Things to Try This Week
- Test the latest Mistral models on your preferred inference stack now that the new funding round clarifies the company’s scale ambitions.
- Try embedflow on a Qdrant index if you need to swap embedding models without rebuilding vectors from scratch.
- Run the radix-selection top-k patch on Qwen3.8-Flash-Next with your current CUDA version to measure decode gains at long context.
- Experiment with the three Strix Halo forks on Qwen 3.8 Flash Next if you have that hardware and want higher prefill and decode throughput than official llama.cpp.
- Compare Gemma 4 12B and E2B voice pipelines on Jetson Orin hardware using the open-source Cortexist Little Gemma engine.
---
### On the Horizon
- Next Mistral model release expected to leverage the new capital for larger-scale training runs.
- Arm’s Neoverse CSS N4 and AGI CPU platforms moving into early silicon sampling with partners.
- Further community forks and patches for Strix Halo and other edge platforms as adoption grows.
- Continued work on embedding migration techniques as teams face repeated model upgrades on large corpora.
