# Models & Agents
> **OpenAI just made real-time voice agents available to every ChatGPT Plus and Pro user, with free rollout starting now.**

**What You Need to Know:** GPT-Live, the next-generation voice model, is now live across iOS, Android, and web for paid tiers, with free users coming in the next few days. OpenAI also audited SWE-Bench Pro and retracted its recommendation after finding 30% of tasks broken. NVIDIA released a compressed 75B MoE model that doubles server throughput at matched per-user speed. Sam Altman confirmed GPT-5.6 Sol arrives Thursday.
---
### DEPTH OVER BREADTH (news items)

### Top Story
OpenAI audited SWE-Bench Pro, one of the most widely used AI coding benchmarks, and found 30% of tasks broken. The company is retracting its prior recommendation that the research community treat it as a leading coding eval because it no longer reliably measures frontier capability. As coding models improve, the post notes that evals must become harder, fairer, and more trustworthy to track real progress. Builders working on agentic coding tools should watch for new benchmarks that replace SWE-Bench Pro in the coming months. The change directly affects how teams evaluate tool-calling and long-horizon code agents. This development continues the Frontier Models tracking arc from last episode, where the focus was on capability gains versus reliable measurement; today's retraction moves the open question of trustworthy evals forward by removing a previously recommended standard. Source: [x.com](https://x.com/OpenAI/status/2074972179385720836)
---
### Model Updates
**GPT-Live Voice Model: [@OpenAI](https://x.com/OpenAI)**
GPT-Live is now fully rolled out to all ChatGPT users on Go, Plus, and Pro plans, with free-user rollout in progress. Users must update the iOS or Android app to access it via the Voice button. Sam Altman described the experience as feeling “magical and real” and noted it may shift his own preference from typing to voice. The model is also coming soon to the API. This release advances the Frontier Models program by delivering a production voice capability that was previously limited; attentive listeners should watch for the API rollout and any measured improvements in multi-turn coherence over the coming weeks. Source: [x.com](https://x.com/OpenAI/status/2075019750569378007)

**Nemotron-Labs-3-Puzzle-75B-A9B: MarkTechPost**
NVIDIA released Nemotron-Labs-3-Puzzle-75B-A9B, a compressed hybrid MoE variant of Nemotron-3-Super that drops from 120.7B total / 12.8B active parameters to 75.3B / 9.3B. On a single 8xB200 node it delivers 2.03x the original model’s total throughput at 100 tokens per second per user; on one H100, 1M-token concurrency rises from 1 request to 8. The model was produced via iterative hardware-aware structural compression alternating with short knowledge-distillation recovery phases. Teams running high-concurrency inference should test it for cost-sensitive deployments. This update fits the AI Compute & Inference arc by demonstrating concrete throughput gains from compression techniques that preserve user-experienced speed. Source: [marktechpost.com](https://www.marktechpost.com/2026/07/09/nvidia-releases-nemotron-labs-3-puzzle-75b-a9b-a-compressed-hybrid-moe-llm-delivering-2-03x-server-throughput-at-matched-user-throughput/)

**GPT-5.6 Sol: Sam Altman**
Sam Altman announced that GPT-5.6 Sol launches Thursday. The release continues OpenAI’s frontier cadence and will be available for builders to test immediately after launch. This sits within the ongoing Frontier Models tracking, where the key open question remains the balance between capability jumps and cost trajectory; the Thursday arrival provides a near-term data point on release cadence. Source: [x.com](https://x.com/sama/status/2074709023807664454)
---
### Agent & Tool Developments
**Multi-Agent Capabilities: IBM Newsroom**
IBM added multi-agent capabilities and specialized modernization workflows to its enterprise AI software development platform. The update targets complex enterprise tasks that benefit from coordinated agent teams rather than single-model calls. This development aligns with the Agents & Tool Use program, where reliability of long-horizon agents remains an open question; the enterprise-focused multi-agent addition tests whether coordinated workflows improve outcomes on modernization projects. Source: [Google News](https://news.google.com/rss/articles/CBMi6AFBVV95cUxNckE1TjZhbm83N1FnWFFzbzFPLVpLR3BRbFFuMUUxN0VwY3E3SUNGMXdRZzFRZXRSMll2djFqLTNQbG9xNHJOcFlKWXdKVkVndldfR0dEU2E3R2tIa3c1MTRUOWVJeFZrdl94aTNVWEJNOXFnVS1FQVpwdEgyU2gtVlE0bFctRXdxb18zRUZrQXVZcm1GcTR4aGE1bnRERlNjeEM1dTNnMGtCeGVqMk1Ec1plZS05cHFHSXM3SVpkbnN2ZENza2dWaElNaklDN0xlME1OR0dZMTlWZ2ZZUjN1OUJXY1JmUDl0?oc=5)

**Agentic AI Identity Maturity Model: csoonline.com**
A new 6-stage maturity model for non-human identities was published to help organizations manage agentic AI systems. The framework addresses identity, authentication, and governance challenges that arise when autonomous agents act on behalf of users or organizations. It directly supports the Agents & Tool Use focus on standardization of agent/tool protocols by offering a staged path for identity management as agent autonomy increases. Source: [Google News](https://news.google.com/rss/articles/CBMitwFBVV95cUxQRHFXa3lTSjB0VDRzenRqbDRPYktjdlppQVphQ1duM3F0bF9SdGZjSVB0b0xMYlV4QUFjUUJQWlkwR3Nqc1ZqM19rTGR5LXRraEVMY3pSdTIxOE1kQ1VaLTh5YVc1aVhfQTdZREMwdk1xeDFfSkk3SE9kOXA0VmZySHN2THFjRnhDQkpYYl9lNkRsN0E2bFZIY1k3dlRoYWVRUG1takNyVmVkWGdmM3JGcHZqZGhSV3M?oc=5)

**Autonomous Yen Payments: CoinPost via 디지털투데이**
Japan is testing AI agent-based autonomous payments in yen using the XJPY token. The trial explores whether agents can handle real financial transactions without human intervention at each step. This experiment tests the reliability of long-horizon agents in a regulated financial domain, an open question in the Agents & Tool Use program. Source: [Google News](https://news.google.com/rss/articles/CBMisgFBVV95cUxQUTVFU29wVDQ2YXlsR0p6dGQtaTZod0tCUHdlaVVkVHNzVzFydWtZSzFPVlJRWnRqbGtzMXdOOVBHUzBTdjZNcFBfM1JkcFhnT25Vdmt0MzRZcFJtZ1JLU3RCSUxERzZIcm9zekE1QUxhQ1BzNXUyQVJsN19MZWFIdUNJWnBfZmc1dkoybWlrTjZoWTNUX28tcFhsR2ZSRENpTUllb2NqZ284VWY4VEVXazdn?oc=5)
---
### Practical & Community
**Commit Practices with AI: Simon Willison**
Simon Willison shared that he now lets Claude and GPT-5.5 write almost all commit messages but finds the results often omit higher-level framing. He prefers linking commits back to human-written issues rather than relying on AI-generated rationales, which can guess incorrectly. Smaller commits remain easier to review. Source: [x.com](https://x.com/simonw/status/2074948137182257284)

**Dual-Use AI Research: [@AnthropicAI](https://x.com/AnthropicAI)**
Anthropic published research on off-switch mechanisms for dual-use AI capabilities, conducted in collaboration with AE Studio. The work explores technical approaches to limiting unintended agent behaviors. Source: [x.com](https://x.com/AnthropicAI/status/2075005777522172146)
---
### Under the Hood: Activation Steering for Dialect Bias
Everyone talks about activation steering as a simple “add this vector, subtract that vector” trick. In practice it requires locating the exact layers where the unwanted behavior is represented and extracting a direction that isolates the target attribute without collapsing fluency. Researchers first run causal tracing to find which layers most strongly influence the biased continuation, then compute a steering vector from paired AAE/SAE examples. At inference they add a scaled version of that vector only to the identified layers. The method reduced dialect bias 5–20× more than prompting while preserving SAE fluency, but the steering strength must be tuned per model family or the output begins to sound unnatural. The biggest gotcha is that the same direction can affect unrelated syntactic features if the localization step is skipped. Teams should start with a small validation set of dialect pairs and sweep the steering coefficient before deploying at scale. The approach also scales across model sizes from 14B to 70B without retraining, yet requires the REAL-AAE corpus of 17,479 validated triplets to generate reliable directions in the first place.
---
### Things to Try This Week
- Update the ChatGPT mobile app today and test GPT-Live on a multi-turn planning task to see how the new voice model handles follow-up corrections.
- Run the new Nemotron-Labs-3-Puzzle-75B-A9B on an 8xB200 node if you serve high-concurrency 1M-token workloads and compare tokens-per-second against your current setup.
- Audit any internal coding agents against SWE-Bench Pro tasks you still trust and flag the 30% broken subset before the benchmark is fully deprecated.
- Experiment with activation steering on your own models using the REAL-AAE corpus if you need to reduce dialect bias without retraining.
- Review Simon Willison’s commit workflow and test linking your next PR to an issue instead of relying on AI-generated messages.
---
### On the Horizon
- GPT-5.6 Sol expected Thursday from OpenAI.
- GPT-Live API access coming “soon” after the ChatGPT rollout.
- Continued free-tier expansion of GPT-Live over the next few days.
- Potential new coding benchmarks to replace the retracted SWE-Bench Pro tasks.