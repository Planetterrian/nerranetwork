# Models & Agents
> **Gemini 3.5 Flash gives builders faster, cheaper frontier performance on coding and agent tasks while Gemini Omni adds real-time multimodal scene editing.**

**What You Need to Know:** Google released Gemini 3.5 Flash today, claiming it outperforms the prior 3.1 Pro on coding and agentic work, runs 4x faster than other frontier models, and delivers up to 800 tokens/sec inside Antigravity. Alibaba simultaneously shipped Qwen3.5-LiveTranslate-Flash for low-latency multimodal translation across 60 languages. Developers should test both models this week for agent pipelines and real-time voice/video workflows.
---
### Top Story
Google introduced Gemini 3.5 Flash at I/O 2026 as a faster, lower-cost model optimized for AI agents and coding workloads. It reportedly beats the previous 3.1 Pro on those benchmarks while running four times faster than competing frontier models and at roughly half the cost. Early users inside Antigravity are seeing 12x speedups and 800 tokens per second. The model is already available in the Gemini App and Antigravity, with a full Pro variant promised soon. Builders working on agentic systems or high-volume coding tools should evaluate it immediately for latency-sensitive deployments. Watch for expanded context windows and deeper tool-calling integrations in the coming weeks. Source: [marktechpost.com](https://www.marktechpost.com/2026/05/20/google-introduces-gemini-3-5-flash-at-i-o-2026-a-faster-and-cheaper-model-for-ai-agents-and-coding/)
---
### Model Updates
**Qwen3.5-LiveTranslate-Flash: MarkTechPost**
Alibaba’s new real-time model handles simultaneous audio and video input across 60 languages and outputs speech in 29 languages at 2.8-second latency. It adds speaker voice cloning, lip-reading vision support, and dynamic keyword configuration for domain terms. The model outperforms prior commercial systems on FLEURS and CoVoST2 and is available only via Alibaba Cloud Model Studio WebSocket API. Source: [marktechpost.com](https://www.marktechpost.com/2026/05/20/alibaba-qwen-team-introduces-qwen3-5-livetranslate-flash-real-time-multimodal-interpretation-across-60-languages-at-2-8-second-latency/)

**Gemini Omni: Demis Hassabis (DeepMind)**
Gemini Omni introduces major gains in world understanding and multimodal editing, accepting photos, video, and audio to generate entirely new scenes. Users can upload their own videos and iteratively refine outputs, with video handling as the initial focus. Over time the system aims to support arbitrary input and output modalities. Source: [x.com](https://x.com/demishassabis/status/2056831486251380783)
---
### Agent & Tool Developments
**Red Hat AI Factory upgrade: 디지털투데이**
Red Hat expanded its AI Factory platform with new NVIDIA integrations and broader support for enterprise autonomous agents. The update targets production deployment of agentic workflows inside existing Red Hat infrastructure. Organizations already running OpenShift can now add agent capabilities without new hardware provisioning. Source: [Google News](https://news.google.com/rss/articles/CBMizgFBVV95cUxPVUVMWjBjWTAxZF94RHc4YXdHalc4a3ZTRFFoNEhSUWVfUGdlVmkxQlB2UzNaMGdtQzdlM0dFV3N5V0JwWFBjdEFGSXpta3RISGZLUWFWVDBnVjhBQVktRWZTN0pQeVdRbWd6b1pSeEJScnVmTGo0dC13ZG9INDlNVGlJckZHWnVZdUFNS0VGblZXRG81a1lmTVd0UWxXbDRUY1pDeUtpSWg0SEZ0a05SQnljbDNfdGM0N2lFSWMzNGJFVXJpQjlCQ2otcGJCZw?oc=5)

**Kay.ai insurance agent: BriefGlance**
Kay.ai launched an agent designed to automate back-office insurance processes including claims handling and policy servicing. The system focuses on structured workflows that require both document understanding and external tool calls. Early pilots target mid-size carriers looking to reduce manual review cycles. Source: [Google News](https://news.google.com/rss/articles/CBMijwFBVV95cUxOVnJEUGZPUHdscmNwZHB1Y0tOSTdXVXNwTzZqVFM1SWtJWXZraWRqWWU5OVRCWjJRbGxCUHVBRG92VHZiaXcxTk1jbnMycEZpUng1X2JXRDExY3Bhb1pnZTg3LVRGMkpFLXVwQ0taS2ZWV1piSW50Nk5GeE5wTnNFM1ZQb0dXcHdQZUhfZkxOQQ?oc=5)
---
### Practical & Community
**Guardrails for 8B models: r/LocalLLaMA**
A new preprint shows guardrails lifting an 8B model from 53% to 99% success on agentic tasks. The approach adds lightweight safety layers without changing base model weights. Teams running smaller open models for agents should review the paper for immediate implementation patterns. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1ticykd/guardrails_take_an_8b_model_from_53_to_99_on/)

**Llama.cpp optimization on Blackwell: r/LocalLLaMA**
A user running Qwen3.6-27B on dual 6000 Blackwell cards via llama.cpp reports 100-110 tokens/sec while leaving headroom for embeddings and ComfyUI. The setup uses tensor splitting, flash attention, and speculative MTP decoding. Developers with similar hardware can copy the command flags to test further gains. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tifr7c/do_you_think_there_is_room_for_optimization/)
---
### Under the Hood: Guardrails on Small Agent Models
Everyone talks about guardrails as a simple safety toggle. In practice they are a layered filtering system that runs before and after the main model call. The first layer uses lightweight classifiers to block obvious policy violations in the prompt. A second layer inspects the model’s planned tool calls and rewrites or rejects risky actions. The final layer scores the completed trajectory against task success and safety rubrics, feeding failures back into a short-term memory buffer. On the 8B model in the recent preprint this stack raised agent success from 53% to 99% while adding roughly 15-25 ms per turn and less than 1 GB of extra VRAM. The quality lift shrinks once base models exceed 30B parameters because their native instruction following already reduces unsafe outputs. Use guardrails when you must ship small models into production agents; skip them only if you have both a large base model and exhaustive red-teaming coverage. The gotcha most teams miss is that guardrails must be updated whenever the underlying model or tool set changes, otherwise false-negative rates climb quickly.
---
### Things to Try This Week
- Try Gemini 3.5 Flash inside the Gemini App or Antigravity for any coding or multi-step agent workflow — the speed and cost improvements are immediately noticeable versus prior frontier options.
- Test Qwen3.5-LiveTranslate-Flash via Alibaba Cloud Model Studio if you need real-time speech translation with vision or voice cloning.
- Add the guardrail patterns from the 8B agent paper to your local llama.cpp or vLLM setups before deploying smaller models in customer-facing agents.
- Run the provided Blackwell llama.cpp command on any dual-GPU workstation to benchmark Qwen3.6-27B throughput against your current inference stack.
---
### On the Horizon
- OpenAI plans to repeat its discounted token program for YC startups once current capacity sells out.
- Sam Altman indicated longer-term 1-3 year token commitments with guaranteed capacity will expand as demand grows.
- Anthropic continues its series of dialogues with philosophers and ethicists on frontier AI character and alignment questions.
- Red Hat and NVIDIA are expected to release additional enterprise agent tooling on the updated AI Factory platform in the coming quarter.