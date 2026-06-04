# Models & Agents
> **Gemma 4 12B puts capable local agents on laptops with only 16GB VRAM under an Apache 2.0 license.**

**What You Need to Know:** Google released Gemma 4 12B, a compact model that runs locally while delivering strong agentic performance. OpenAI added agentic coding and drug-discovery tools to its GPT-Rosalind life-sciences series. Endava, ServiceNow, and Snowflake all announced production deployments of autonomous agents this week.
---
### Top Story
Google released Gemma 4 12B today alongside the milestone of 150 million total Gemma downloads. The 12B model runs on a laptop with 16GB VRAM yet supports agent workflows that previously required much larger systems. It ships under the Apache 2.0 license, allowing unrestricted commercial use and local fine-tuning. Early community tests show it completing full retro-game implementations in a single 45k-token prompt at steady 18 t/s on consumer AMD hardware. Builders should watch how quickly the ecosystem ports existing agent scaffolds to this size class. The release narrows the gap between closed frontier models and practical on-device agents. Source: [x.com](https://x.com/demishassabis/status/2062241713398149524)
---
### Model Updates
**Gemma 4 12B: Google DeepMind**
The new 12B checkpoint extends the Gemma 4 family with improved instruction following and tool-use stability while remaining runnable on consumer GPUs. It joins the existing 150-million-download milestone and keeps the Apache 2.0 license. Local runs already demonstrate full end-to-end coding agents without cloud round-trips. Builders working on privacy-sensitive or offline agents should test the 8-bit quantized “heretic” variant this week. Source: [Google News](https://news.google.com/rss/articles/CBMipwFBVV95cUxPSVgtemJtZzZNM0JnSzRBWl9MQnJWdGRydXpJclpzenU3U1NRZFVYc3FsZERKb3c3Rk5vZlBneVJEQ1B1MUp1Q00yaGdkMldyN0pBTnVsOGNHOU9sejJDdWtDQkdEVktXTzRmb3hLM1lhVm90a3lWV01ENDhxSlJIUzdhWGNSNUxGNEFvREVOb1pLUXFtQmZ5YWg4X1l5QlV2TWlTUGRrYw)

**GPT-Rosalind: OpenAI**
OpenAI extended its life-sciences series with GPT-5.5-level agentic coding and tool use plus stronger domain intelligence for drug discovery and experimental design. The update targets enterprise-scale research workflows that combine code generation with wet-lab planning. Early users report tighter integration between analysis scripts and molecular design loops. Life-sciences teams should evaluate the new tool-calling surface this week. Source: [x.com](https://x.com/OpenAI/status/2062281977122996256)

**POLARIS-9B: arXiv 2606.04095**
Researchers applied GRPO with LLM-as-judge rewards and human-reference injection to Qwen3.5-9B, producing a model that follows length instructions up to 12k tokens while remaining competitive with 27B baselines. Training used only 1.4k prompt-story pairs and four A100s. The work shows length generalization is a useful stress test for creative-writing models. Writers experimenting with long-form local generation should try the released weights. Source: [arxiv.org](https://arxiv.org/abs/2606.04095)

**Meta next model: Yahoo Finance**
Meta delayed the developer release of its next open model while internal testing continues. No new parameter count or benchmark details were shared. The pause suggests Meta is prioritizing stability over the rapid cadence seen with Llama 3. Source: [Google News](https://news.google.com/rss/articles/CBMipgFBVV95cUxNb3RVTzUwWGVVS3V6VUVBWXV4T0lkVWtPakpxaHk3ZVpyNW1QSm0tcUNleHl0RGZrLU1DZzV3THRLSTJYRzBaeWo0ZkpfYmQ4V1UyYkRJNzRzOVMzQTZIeEtpcnlzS3g0TFZ6TnMtUmpITkRDR0xBREdZdlNCTG9ndGM0VkVaa2lhNnBKWHg0eV85SF9vMFBEVi1IbEZyTVlYTktxTl9R)
---
### Agent & Tool Developments
**Endava + OpenAI agents: OpenAI News**
Endava is embedding ChatGPT Enterprise and Codex agents into its software-delivery pipelines to automate workflows and enforce an AI-native culture. The program focuses on measurable acceleration of enterprise codebases rather than experimental prototypes. Teams adopting similar agent-augmented delivery should study Endava’s governance patterns. Source: [openai.com](https://openai.com/index/endava-frontiers)

**ServiceNow autonomous agents: AD HOC NEWS**
ServiceNow launched a new suite of autonomous agents aimed at enterprise workflows while navigating insider-sales scrutiny. The agents target repeatable back-office processes with explicit human-in-the-loop checkpoints. Early adopters should monitor how the platform handles long-running task state. Source: [Google News](https://news.google.com/rss/articles/CBMizgFBVV95cUxOUEJpUVVpclhna1lVUWtJQ0YxWW1nN3pWRGo2RUZGRlI2c0tmN0VRQTF6TVhqWGJqYjlYdWJxUDA0WHFLaG9iNEZyVDYybDE4MU9VSXNLNmQxeG1FU1h3VEUteFFKQnpnWXJnOVNVZ1YtMzVPc3U2WVNreGRiS0pabVlXRFlZM2loSk9CSWZ4UVBPS1JiVVhjXzlhOEdXWEdpX0pPTlZ6dHRmVDFHRnVBU3E0Z3FRUlc1RU1BWGdSRDU0b0RObzY1X09LbFk0QQ)

**Snowflake autonomous agents: The Hindu**
Snowflake announced deeper investment in autonomous agents to compete in the enterprise software race. The move pairs its data platform with agent orchestration layers for analytics and ETL. Data teams should watch for native integration patterns that reduce context-passing overhead. Source: [Google News](https://news.google.com/rss/articles/CBMi1wFBVV95cUxOYkk1bTF2QmMyNDRBbFFDa2h2Q1Nab3dQYmk2Q3lwUWtQWXh3enRScFA4YzZUR2tiNHR1dGU1NFFFS3pWNzV2LWsyeWlHdzlyLUk5ZVVjMVpuU2M4X1dRbm1oZWNfanZUcXdGaFFlZWh2UjFmMjNaeExjVFRrRmJHTDluRy1wXzlHeEJIMTJXeEprZGdpWEt5VUJTdWI0UExZNUhlUDVCUUc3Z29oc2xWWXhRaDR6ZXR5TjBjb2IxLUNKWm9xOEVHdDY1ZlllYTJPd3h6TnNBa9IB3gFBVV95cUxQazAxaW5lTkl3enlyWTgtN2lrVnlYR3U5MS1NRnJmX3FKMEZacWp0eXdWWUhiS2dkVFZnZEdhVjRBLTFUb090VUctSjNiN3FBVmE4N3k2QjlCM0poOC1mSG9uRXBPWnd4TjNuNXpjaVc2RlVlaXpNTXluT0V4WjdjdGFBbUE4Z0VSYWs1V0NtMUxkOXBaY3hvRXFxNlRuQ2ZfUVZSLW9PaDFzelpKSzJBQ09pYXFWNldjWHBTaUpTWWVORjhfdkE1M0RKeWNuMjY1SDA0ZjBpZWJWNFN3bnc)

**Kore.ai multi-agent CX: CX Today**
Kore.ai highlighted a shift toward coordinated multi-agent customer-experience systems that hand off context across specialized agents. The approach targets contact-center automation with measurable containment rates. CX teams should evaluate handoff latency and state consistency before scaling. Source: [Google News](https://news.google.com/rss/articles/CBMiuAFBVV95cUxPTkZlVlc2ZWJZbUo0UnJrbFhGMGRyUTk2b2xtOHNWT1pnMFpMZllXS1NOQ0gtNlc2c1VrVnR6Z0R3MDRCd0hkdDhvZFAtSGNKMHRuNmh4SnM1UFdvWGNERFV6dFdwQWo5MWtrT1pfamUwV3RWZ2VrT0tRNXlOUWdqaHc0dlRXUXRvb2VWeUFwY2hJSU5YWGxhTGZJcWxVN3JpenRUNmtLQ25lNXFINnY3RmViajNzRkdR)
---
### Practical & Community
**attnhut attention implementations: r/MachineLearning**
A new GitHub repo collects clean PyTorch implementations of multiple transformer attention variants, including MiniMax M3 sparse attention, aimed at SLM experiments and computer-vision encoders. The maintainer invites PRs for additional mechanisms. Researchers swapping attention modules should clone the repo and benchmark on their target sequence lengths. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1twhhnq/repo_for_implementations_of_various_transformer/)

**Gemma 4 12B Heretic coding run: r/LocalLLaMA**
A detailed single-prompt run shows the 8-bit Heretic variant writing a complete 467-line retro cyberpunk brick-breaker game in one 4-minute stream at 18.76 t/s on an RX 6800. Cache reuse hit 96.4 % across turns thanks to llama.cpp LCP checkpoints. Local coding-agent builders should replicate the exact chat template and KV-cache settings. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1twelo6/gemma_4_12b_8q_heretic_oneshot_coding/)

**Jetson AGX Orin 64GB quantization: r/LocalLLaMA**
Users report q8_0 delivering 29 % faster prefill than q6_k on the Jetson AGX Orin 64GB despite higher memory traffic, indicating the device is compute-bound rather than bandwidth-bound for this workload. The observation applies to Qwen3.6-27B-class models. Edge-deploy teams should re-test their preferred quant on the Orin before locking a deployment config. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1twgwrf/jetson_agx_orin_64gb_q8_0_good_q6_k_bad/)
---
### Under the Hood: Deferred Positional Encoding in KV Caches
Everyone treats positional encoding as a fixed property baked into the KV cache at write time. In practice it is a separate transformation that can be applied later inside the attention kernel. LazyAttention keeps raw keys and values without positional offsets, then injects rotary or ALiBi adjustments on the fly during the matmul. The approach removes the need to materialize new caches when the same prefix is reused at different positions, cutting TTFT by roughly 1.37× under skewed document distributions. The tradeoff appears in kernel complexity: every attention call now carries extra index arithmetic, though the overhead stays under 5 % on modern GPUs. Teams running long-context RAG should adopt deferred encoding when prefix reuse exceeds 30 % of total tokens; otherwise the simpler static cache remains simpler to debug.
---
### Things to Try This Week
- Run Gemma 4 12B locally with the 8-bit Heretic weights for offline coding agents; the single-prompt game demo proves it handles 20k+ token contexts at usable speed.
- Test GPT-Rosalind’s new tool-use surface on a small drug-discovery workflow to see how the life-sciences fine-tune changes agent reliability.
- Clone the attnhut repo and swap attention mechanisms inside a 7B–9B SLM to measure latency versus quality on your target task.
- Compare q8_0 versus q6_k on any Jetson AGX Orin workload before finalizing an edge deployment.
---
### On the Horizon
- Meta’s next open model remains in extended testing; watch for a revised release date in the coming weeks.
- OpenAI continues expanding the GPT-Rosalind series; expect additional domain-specific tool packs.
- arXiv papers on learnable-rank LoRA and dynamic logit-level gating suggest new fine-tuning and ensembling patterns will appear in libraries soon.
- ServiceNow and Snowflake agent platforms are likely to publish early-adopter case studies within the next month.