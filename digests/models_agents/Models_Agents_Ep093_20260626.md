# Models & Agents
> **OpenAI's internal rollout shows agents handling complex, cross-functional work at scale, giving builders an early view of what production agent systems will soon need to match.**

**What You Need to Know:** OpenAI reports Codex agents are already doing longer-running, cross-team tasks across every department. YesWeHack launched autonomous agents for on-demand penetration testing. Nemotron-TwoTower decouples autoregressive context from diffusion denoising for 2.42× throughput at near-parity quality. Developers should watch how these internal patterns translate to external tooling and open-weight alternatives this week.
---
### Top Story
OpenAI stated that agents powered by Codex are now transforming work across every department, handling tasks that are more complex, longer-running, and increasingly cross-functional. The company positions this internal usage as an early signal of how agentic tools will reshape workflows once they reach broader availability. No specific benchmarks or model versions were shared, but the emphasis on cross-functional scope suggests agents are moving beyond single-user chat interfaces into multi-step, multi-stakeholder processes. Builders should note the implied requirements around reliability, state management, and tool interoperability that such deployments demand. Watch for any follow-on details on the underlying agent framework or evaluation methods OpenAI is using internally. Source: [x.com](https://x.com/OpenAI/status/2070196105745518913)
---
### Model Updates
**Nemotron-TwoTower: NVIDIA**
NVIDIA introduced Nemotron-TwoTower, a block-wise autoregressive diffusion model built on Nemotron-3-Nano-30B-A3B that splits context representation into a frozen AR tower and a trainable bidirectional diffusion denoiser. The model retains 98.7% of the baseline autoregressive quality after training on approximately 2.1T tokens while delivering 2.42× higher wall-clock generation throughput. It supports both dense 2.5B and MoE 25B-A2.8B scales, with gains persisting after 80B-token long-context midtraining. Builders working on high-throughput inference should test the released weights for long-context generation workloads. Source: [arxiv.org](https://arxiv.org/abs/2606.26493)

**Dynamic-dLLM: Research Team**
Dynamic-dLLM adds Dynamic Cache Updating and Adaptive Parallel Decoding to diffusion LLMs such as LLaDA-8B-Instruct and Dream-v0-7B-Instruct. The approach adaptively allocates cache-update budgets per layer and calibrates decoding thresholds, achieving more than 3× average inference speedup across MMLU, GSM8K, and HumanEval while preserving benchmark performance. It requires no retraining and works as a plug-and-play module. Teams running diffusion-based generation should evaluate it against static caching baselines for latency-sensitive applications. Source: [arxiv.org](https://arxiv.org/abs/2606.26120)

**SOLAR Soft-Token Alignment: Research Team**
SOLAR introduces an auxiliary supervised fine-tuning objective that aligns soft-token representations across languages using English as a pivot. On four multilingual reasoning benchmarks it improves accuracy by up to +17.7 points over the base model and +3.8 over standard SFT, with the largest gains on low-resource languages. The method reduces language-cluster separability in final-layer embeddings. Developers building cross-lingual reasoning systems should experiment with the alignment loss on their own multilingual fine-tunes. Source: [arxiv.org](https://arxiv.org/abs/2606.26466)

**Know2Guess Benchmark: Research Team**
Know2Guess provides a contamination-aware, multi-zone benchmark with 1,200 items across five domains, explicit abstention labels, and dual parsers for measuring answerability versus guessing in LLMs. Evaluations of FLAN-T5, Qwen2.5-Instruct, and Llama-3-Instruct show that stronger instruction-tuned models still struggle with selective abstention and calibration. The dataset and parsers are publicly released. Researchers auditing model reliability should incorporate the benchmark into their evaluation suites. Source: [arxiv.org](https://arxiv.org/abs/2606.26101)
---
### Agent & Tool Developments
**YesWeHack Autonomous Agents: SMBtech**
YesWeHack deployed autonomous AI agents for on-demand penetration testing, allowing users to request security assessments without scheduling human testers. The system targets the growing need for continuous, scalable security validation in agentic environments. No specific performance numbers or integration details were released. Security teams evaluating automated testing platforms should request early access to compare coverage against traditional manual pentests. Source: [Google News](https://news.google.com/rss/articles/CBMingFBVV95cUxPSHVxb2xWQXM4bndWaWl6T2NQdXNvbks3Rm00bzI5dnhwNV9TczQ0U2dzVkhMYWRzNUp0OWtFNFBJbTd5ZGFpX2hEMFJUMmRGX0lQTE85dTdfWXI5RjJEYnJoNjl4RFZzc2lYSnl0MXREUGdFWENMYkszX0txVzlWaGpXY0dTWkxaOEZhQWMyY2ZrMW9ub1ZnTWNqMDFCQQ?oc=5)

**Cisco WideField Acquisition: CRN**
Cisco announced the acquisition of WideField Security to address security gaps in agentic AI systems. The move targets risks arising from autonomous agents that interact with enterprise environments and external tools. No technical specifications or integration timelines were disclosed. Organizations deploying agents in production should monitor Cisco's forthcoming agent-security offerings for policy and monitoring capabilities. Source: [Google News](https://news.google.com/rss/articles/CBMiuAFBVV95cUxQamVpdXNveVRPb2tzU0s1UmloU0hEUTNXM0ZVbzBiLWhaU3pUdkRyTDZKTldaUXc4d0NEZE9zOHJ1cm43cXpVM0VBOXFjVnBOQlVJeV8xN09uUE5ZWHN5cnZveXM0SHFFNURqeHRwTkpIdVlZVEE3ckpnRHF3aGZUZ3NLSHdMQnpra1RfZV9qd2hDYjBfcEF1TzBacnhScEtFclhFOEZhUVZtUHFIMFhiQXNTNC1pR21G?oc=5)

**MemStrata Temporal Validity: Research Team**
MemStrata maintains a bi-temporal ledger that retires stale facts using deterministic (subject, relation, object) supersession rules when contradictions appear. Across six benchmarks with a 7B model it matches standard RAG on static knowledge while reaching 0.95–1.00 accuracy on evolving knowledge where RAG drops to 0.20–0.47. It eliminates the 15–40% stale-fact error rate seen in RAG at roughly 2.1 s retrieval latency. Agent developers handling time-sensitive data should integrate the supersession mechanism to avoid serving outdated information. Source: [arxiv.org](https://arxiv.org/abs/2606.26511)
---
### Practical & Community
**LLM Production Deployment Discussion: r/MachineLearning**
A developer using OpenRouter APIs is seeking affordable, controllable open-source LLM deployment options that support fine-tuning without CUDA or Transformers complexity. The post highlights ownership of the full stack and use-case-specific adaptation as primary motivations. Community responses are likely to surface managed platforms or simplified inference servers. Builders facing similar constraints should review the thread for current recommendations on private deployment paths. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1ufyuph/howre_you_deploying_llms_in_production_nowadays/)

**ContextForge Context Recycling: Research Team**
ContextForge recycles task-relevant information across multi-turn conversations using structured query generation, external memory retrieval, and controlled synthesis. On a 15-turn healthcare benchmark it improves consistency and reduces token consumption compared with a baseline agent while maintaining response accuracy. Code and evaluation artifacts are available on GitHub. Teams building long-horizon agents should test the recycling approach to lower context-window pressure. Source: [arxiv.org](https://arxiv.org/abs/2606.26105)
---
### Under the Hood: Delta-Rule Memory Updates
Everyone talks about delta-rule linear attention as a simple “correct before you write” trick. In practice it still ties the correction to the current write address, so stale values sitting at other addresses stay untouched until passive decay eventually removes them. The engineering fix is to add an independent erase step that first suppresses outdated memory along a learned direction, then performs the usual delta correction at the active write location. This adds a second learned vector per update but keeps the core delta math intact, preserving the quality of the corrective write while giving the model an explicit cleanup path. In 2.5B and 25B-scale pretraining runs the extra path helps most when decay is weak, cutting stale-fact retention without increasing overall memory bandwidth. The practical takeaway is to adopt the decoupled erase when your workload contains frequent value changes; if facts are mostly static, the added vector offers little return and the simpler single-address delta rule remains preferable.
---
### Things to Try This Week
- Test Nemotron-TwoTower weights on long-context generation tasks to measure the 2.42× throughput gain against your current autoregressive baseline.
- Integrate MemStrata-style supersession rules into any RAG pipeline handling time-sensitive facts to eliminate stale-value errors.
- Run ContextForge on a 10–15 turn internal workflow to quantify token savings versus full context replay.
- Compare Dynamic-dLLM against static caching on your diffusion LLM workloads for latency-sensitive applications.
- Review the Know2Guess dataset and parsers to add answerability/abstention metrics to your model evaluation harness.
---
### On the Horizon
- Further details expected on OpenAI’s internal agent tooling and evaluation methods.
- Additional open-weight diffusion LLM releases following the Nemotron-TwoTower pattern.
- Security tooling updates from Cisco following the WideField acquisition.
- Expanded multilingual reasoning benchmarks incorporating soft-token alignment techniques.