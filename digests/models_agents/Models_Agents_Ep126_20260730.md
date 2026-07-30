# Models & Agents
> **OpenAI's GPT-5.6 Sol just tripled its ARC-AGI-3 score using two API settings that also cut output tokens by 6x.**

**What You Need to Know:** OpenAI detailed how retaining reasoning and applying context compaction in the Responses API lifted GPT-5.6 Sol’s public ARC-AGI-3 score 188% while slashing tokens. Simon Willison separately noted that GPT-5.6 optimizations already cut OpenAI’s serving costs 20%. Builders should test the same settings on long-horizon agent tasks this week.
---
### DEPTH OVER BREADTH (news items)

### Top Story
OpenAI reported that GPT-5.6 Sol’s ARC-AGI-3 score rose 188% on the public set after switching to the Responses API, enabling retained reasoning, and turning on context compaction. The standard harness had been discarding reasoning after each move and dropping earlier actions as context filled, forcing the model to restart. With the new settings the model builds on prior learning across multi-step 2D game tasks that test adaptation to unfamiliar rules without instructions. The change also reduced output tokens by a factor of six. OpenAI recommends the same harness and settings it uses internally for any developer chasing frontier performance on agent-style evals. This fits the ongoing capability gains versus cost trajectory tracked since yesterday. The company further emphasized that benchmark scores reflect the model together with harness design and prompting choices rather than the model in isolation. Source: [x.com](https://x.com/OpenAI/status/2082616640144048433)
---
### Model Updates
**GPT-5.6 cost optimizations: Simon Willison (AI builder)**
GPT-5.6 delivered end-to-end serving cost reductions of 20% for OpenAI. Willison notes this likely translates to billions of dollars monthly at current scale. The optimizations sit alongside the ARC-AGI-3 harness changes announced the same day. Willison separately observed that the model found concrete efficiencies in how it is served through the API. Builders evaluating GPT-5.6 should measure both capability and token efficiency on their own workloads before committing. The 20% figure applies to the full end-to-end serving pipeline rather than isolated components. Source: [x.com](https://x.com/simonw/status/2082641030093127768)

**Anthropic inference spend: Simon Willison (AI builder)**
Anthropic is paying SpaceX $1.25 billion per month for Colossus inference capacity alone. Willison states this figure is probably not even the majority of Anthropic’s total inference spend. The disclosure underscores how quickly frontier labs are scaling compute commitments. The monthly outlay covers only one major provider and leaves room for additional capacity from other sources. Willison highlighted the spend as evidence that inference costs remain a dominant line item even for labs focused on model development. Source: [x.com](https://x.com/simonw/status/2082665071499698181)

**Free researcher access: Sam Altman (OpenAI)**
Sam Altman expressed excitement about upcoming free access to OpenAI models for researchers. He framed the move as the fastest path to accelerating scientific discovery rather than keeping models internal. The program targets scientists who can put frontier systems to work on open problems. Altman noted that models are approaching the point where they can meaningfully speed up discovery across fields. He positioned the access as a way to distribute benefits broadly instead of concentrating them inside a single organization. Source: [x.com](https://x.com/sama/status/2082628413769003269)
---
### Agent & Tool Developments
**AgentGUI: arXiv NLP**
AgentGUI is a locally hosted GUI for observing and steering multiple concurrent long-running AI agent sessions. It supplies rich trajectory visualizations, manual and automated steering controls, and integration with both open-source and frontier agent frameworks. A controlled user study showed a 38% reduction in time to identify key elements from agent traces with statistical significance at p = 0.023. The automated drift-prevention feature raised task completion rates by up to 34 percentage points across 0.8B–9B models in a preliminary experiment of 50 runs per model. The project is open source at https://github.com/eth-medical-ai-lab/agent-gui and includes a demo video. Source: [arxiv.org](https://arxiv.org/abs/2607.26300)

**Voice Memory: arXiv NLP**
Voice Memory is an inference-only listener-thinker architecture that lets a frozen corrector consult a single per-domain memory.md file and decide whether to correct an ASR hypothesis or abstain. An asynchronous optimizer revises the file only when edits strictly improve a held-out score. Across ten HyPoradise domains it lowered weighted word error rate from 8.36% to 7.52% while cutting over-correction rate from 64% to 35%. The memory transfers across corrector families with zero added parameters and supports optional in-context examples that further improve results to 7.47%. Gains concentrate on domains with recoverable headroom such as air-travel commands and noisy far-field speech. Source: [arxiv.org](https://arxiv.org/abs/2607.26410)

**CMT-RAG: arXiv NLP**
CMT-RAG stores conversational memory as persistent sub-question reasoning traces in a session-level DAG. At each turn a state-space trace generator decomposes the current query into retrieval-oriented sub-questions that reference prior traces. On MuMu-QA and corpus-level RAG benchmarks it outperformed five categories of baselines in answer accuracy. The approach directly addresses the loss of cross-turn dependencies that occurs when systems rely on raw history or flat summaries. Experiments confirm consistent gains on multi-hop questions that span multiple conversation turns. Source: [arxiv.org](https://arxiv.org/abs/2607.26470)
---
### Practical & Community
**WikiLoop: arXiv NLP**
WikiLoop jointly trains a single Qwen3.5-9B policy to act as both Navigator and Builder of an agent-native wiki. The Builder proposes edits scored by a frozen Navigator’s change in downstream performance; the Navigator follows a sufficiency-before-efficiency objective. On AuthTrace the system reached 62.6 aggregate Answer Correctness, 6.3 points above the LLM-Wiki baseline, with largest gains on multi-document queries. The learned edits remain useful to a held-out Navigator and improve performance on HotpotQA and MuSiQue without dataset-specific training. Training proceeds through sequential role-specific optimization followed by a joint stage. Source: [arxiv.org](https://arxiv.org/abs/2607.26604)

**ForgetBench: arXiv NLP**
ForgetBench evaluates long-term parametric memory retention under sequential knowledge editing using concept-based and scenario-based QA streams. Existing editing methods fail to balance retention against generalization quality across multiple stages. The benchmark supplies a unified temporal-decay measurement framework that tracks retention strength and cross-instance stability. Experiments across diverse models and editing methods show that current approaches cannot maintain both long-term retention and generalization simultaneously. Code will be released upon acceptance. Source: [arxiv.org](https://arxiv.org/abs/2607.26455)

**Steering instruction hierarchies: arXiv NLP**
V-Steer edits cached value vectors at inference time to restore privileged system-prompt influence over conflicting user or tool inputs. The training-free method raises primary constraint accuracy from under 18% to 92% on role-conflict benchmarks across 7B–70B models. It adds only a one-time prefill overhead and remains compatible with fused attention backends. The intervention is strongest within a middle-layer band and transfers zero-shot to independent corpora when the same trait direction is applied. Code is at https://github.com/cindy2000sh/v-steer. Source: [arxiv.org](https://arxiv.org/abs/2607.26228)
---
### Under the Hood: Inference-Time Value Editing for Instruction Hierarchies
Everyone talks about instruction hierarchies as if a single prompt or training stage can enforce them. In practice the model’s attention layers often let lower-priority spans dominate at generation time. V-Steer starts from the observation that value vectors in cached attention states already encode the relative strength of different prompt segments. It uses direct logit attribution on the first next-token prediction to locate heads where lower-priority content is winning, then applies a simple multiplicative boost to the privileged span’s value vectors and a corresponding suppression to the conflicting span. Because the edit happens in-place on already-computed caches, it works with any fused attention kernel and costs only the initial prefill pass. The method was validated on controlled role-conflict benchmarks and broader instruction-hierarchy evaluations, matching or exceeding training-based approaches on three of four model scales. Teams facing jailbreak or tool-injection risk can therefore add a lightweight guard without retraining, provided they are willing to accept the one-time prefill cost and the need to identify the right heads per model family. The approach avoids any weight updates, preserving compatibility with existing fused backends while delivering measurable constraint accuracy gains.
---
### Things to Try This Week
- Test GPT-5.6 Sol on ARC-AGI-3 style tasks with the Responses API plus retained reasoning and context compaction to see whether the 188% lift appears on your own agent workloads.
- Clone AgentGUI and run it against any long-horizon agent traces you already have; the 38% time saving on trace inspection is immediate.
- Try V-Steer on a 7B–13B model you control if you need stronger system-prompt adherence without fine-tuning.
- Evaluate CMT-RAG on any multi-turn retrieval task where prior reasoning steps keep getting lost.
---
### On the Horizon
- More details expected on OpenAI’s free researcher access program.
- Further reports on whether the 20% serving-cost reduction from GPT-5.6 generalizes to other frontier families.
- Additional agent-framework integrations for AgentGUI now that the repository is public.