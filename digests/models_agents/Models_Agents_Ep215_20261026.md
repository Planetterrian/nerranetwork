# Models & Agents
> **Kolibri activates 3.46 billion parameters per token while landing on the Pareto frontier for English and German quality versus serving cost.**

**What You Need to Know:** Tsinghua released AKV, an SGLang-based cache engineering server that lets LLM agents drop and reposition KV cache instead of summarizing history, cutting average cost 27.7 percent across four agent benchmarks. Kolibri, a new 78.1B-parameter English-German MoE with 3.46B active parameters, was trained on 24T tokens with over 20 percent German data and released as open weights under Apache 2.0. SPECMEM keeps a live per-user tool-call memory with LRU eviction and side-effect gating, delivering a 27 percent gap in accepted tokens and up to 1.74x wall-clock speedup on multi-session streams.
---
### Top Story
Kolibri is a new English-German mixture-of-experts transformer with 78.1 billion total parameters and 3.46 billion active parameters per token. It was trained on 24 trillion tokens with German accounting for more than 20 percent of the data mix by bytes, then post-trained with supervised fine-tuning and reinforcement learning on over 1.2 million internally curated tasks covering reasoning, tool use, instruction following, code, and retrieval. The model activates 4.4 percent of its parameters per token and sits on the Pareto frontier of quality and serving cost among open models evaluated in the report for both English and German. It was built end-to-end inside a controlled Model Factory pipeline that includes data curation, training infrastructure, post-training, and evaluation, with a focus on sovereign and regulated-domain use cases. Builders working on German-language or regulated workloads now have a fully open Apache 2.0 checkpoint that matches or exceeds prior open models on the tested quality-cost curve. Source: [arxiv.org](https://arxiv.org/abs/2610.31945)
---
### Model Updates
**LAMB: A Modern Contextual Language Model for Latin — MarkTechPost**
LAMB is an encoder based on the ModernBERT architecture pretrained in two phases on more than 74 billion Latin tokens with a morphologically informed masking regimen. It outperforms all other evaluated models on 16 of 17 subtasks across five tasks and seventeen subtasks, coming within 0.8 percentage points of state of the art on the remaining one. The release includes two new corpora: Acervus with 24 billion BERT WordPiece tokens and Corpus Trinum, the first Latin semantic triplet dataset containing over 100 million strong and weak triplets. Source: [marktechpost.com](https://www.marktechpost.com/2026/10/26/tsinghua-akv-kv-cache-engineering-llm-agents/)

**The Schema Coherence Inventory: Measuring Whether an Assigned Belief Organizes a Language Model's Cognition — arXiv**
The Schema Coherence Inventory provides 96 forced-choice items at eight levels of Beck's cognitive model, scored by length-normalized log-likelihood without generation or parsing. Six validation studies across 107 conditions on five backbones from 1.7B to 14B parameters show belief adapters are target-specific on every backbone with a +17.7 point gain, and a condition's SCI profile identifies its own free generations in 24 of 30 cases against five expected by chance. Nine clinically trained raters recover the keyed belief at 79.5 percent accuracy. Source: [arxiv.org](https://arxiv.org/abs/2610.31683)

**Free Lunch for LLMs Confidence: The RL Critic Already Knows — arXiv**
An external model trained only on a policy's behavioral traces can estimate the policy's confidence as accurately as the policy itself without accessing internal representations. Under a correctness-based outcome, confidence estimation and critic training are mathematically equivalent, both predicting the likelihood that a policy's response will be correct from its trajectory. The reused critic is the best confidence estimator on every in-distribution split and the best-calibrated on 14 of 16 splits across math, code, tool calling, and general reasoning without hurting task performance. Source: [arxiv.org](https://arxiv.org/abs/2610.31820)

**SPECMEM: Accelerating Agentic Tool Calling via Live Memory Management — arXiv**
SPECMEM maintains a live per-user tool-call memory with LRU eviction and a side-effect gate that defers irreversible calls until verification. On multi-session, multi-user query streams served by three open-weight models, it holds a 27 percent gap in mean accepted tokens and delivers up to 1.74x wall-clock speedup compared with a frozen store that steadily loses acceptance. Ablations show the gain comes almost entirely from keeping the store live rather than from local per-user scoping. Source: [arxiv.org](https://arxiv.org/abs/2610.31840)

**An Agentic Approach with Evidence-Grounded Verification for Multimodal Emotion Reasoning in Conversation — arXiv**
The framework uses modality-specific perception agents that post evidence-cited observations to a shared board, an integration agent that produces emotion description and label set with citations, and an MLLM critic that can request one revision. On the MER2025 dataset it improves F-score by 0.6 to 2.2 points depending on the backbone across VideoLLaMA3-2B, Phi-3.5-vision-instruct, Qwen2.5-VL-7B-Instruct, and InternVL2.5-38B, outperforming both the frozen static pipeline and undifferentiated reflection baselines. Source: [arxiv.org](https://arxiv.org/abs/2610.31685)
---
### Agent & Tool Developments
**Solo.io Introduces agentshield to Protect Organizations’ Existing Infrastructure From the AI Agents They Don’t Control — AiThority**
agentshield is designed to protect existing infrastructure from AI agents that organizations do not control. It addresses security and governance gaps created when external agents interact with internal systems. Source: [aithority.com](https://aithority.com/machine-learning/solo-io-introduces-agentshield-to-protect-organizations-existing-infrastructure-from-the-ai-agents-they-dont-control/)

**Tsinghua AI Open-Sources AKV, a Cache Engineering Server for LLM Agents on SGLang — MarkTechPost**
AKV is an SGLang-based serving system that lets LLM agents drop and reposition KV cache instead of summarizing history. It cuts average cost 27.7 percent across four agent benchmarks while preserving performance. Source: [marktechpost.com](https://www.marktechpost.com/2026/10/26/tsinghua-akv-kv-cache-engineering-llm-agents/)

**The LLENS Platform for On-Premises Large Language Model Agents in a Japanese University Hospital: Development and Evaluation Study — arXiv**
LLENS runs inside the closed network of Hokkaido University Hospital on one host with eight NVIDIA H200 GPUs using the open-weight Kimi K2.6 model. On 180 questions over hospital documents it reaches 97.2 percent mean accuracy with interactive document-tool access, 15.9 percentage points above fixed retrieval, with the largest gains on filtering and counting questions. Source: [arxiv.org](https://arxiv.org/abs/2610.32151)

**X-Dubbing: Speech-to-Speech Translation under Temporal and Visual Constraints — arXiv**
X-Dubbing jointly solves time-aware speech-to-text translation and video-aware text-to-speech using a language-agnostic timing budget. It produces faithful translations that remain naturally speakable within source timing and improves isochrony and audio-visual correspondence over recent baselines without requiring paired dubbing data. Source: [arxiv.org](https://arxiv.org/abs/2610.32042)
---
### Practical & Community
**MisconceptDialogue: Evaluation Criteria Shape Measured Success in LLM Math Tutoring — arXiv**
MISCONCEPTDIALOGUE runs five open-weight LLM tutors on over 5,000 dialogues with LLM-simulated students. Benchmark-style exact-match scoring reports 42.1 percent remediation success on the same dialogues where a human-calibrated LLM-as-judge reports 81.3 percent, a 39.2-point spread larger than the combined effects of tutor model, teaching strategy, and supplied diagnostic information. Source: [arxiv.org](https://arxiv.org/abs/2610.31679)

**Rethinking Structured Generation: Can Graph-Based Reasoning Resolve Ambiguity? — arXiv**
The work reformulates structured generation as an ambiguity-aware inference problem that reasons over a set of plausible structured outputs rather than predicting a single solution. Graph-based reasoning over semantic alignment and relational consistency improves accuracy, stability, and robustness under varying levels of ambiguity on structured generation benchmarks. Source: [arxiv.org](https://arxiv.org/abs/2610.31681)

**Beyond Final Outcomes: Quantifying Claim-Level Information Dynamics in Multi-Agent LLM Interaction — arXiv**
RIVER decomposes agent outputs into atomic claims and evaluates convergence, exploration, and retention across five interaction strategies on 40 controlled news-generation cases. Repeatedly pooled interaction promotes convergence but narrows the information space, while distributed relay yields broader, less shared information. Source: [arxiv.org](https://arxiv.org/abs/2610.32333)

**SCI-AGENT-EXAM: Benchmarking Agents on Scientific Research Tasks — arXiv**
SCI-AGENT-EXAM comprises 120 expert-curated tasks across 11 scientific fields and 7 research task types. GPT-6 Astra achieves the highest overall score of 80.9, yet only 26.0 percent of its runs exceed the 0.95 success threshold, revealing distinct capability profiles and variation in execution efficiency and stability. Source: [arxiv.org](https://arxiv.org/abs/2610.32441)
---
### Also Today
**Validating the Comparison, Not Just the Scorer: Why Overall Accuracy Can Mislead in Interactive LLM Evaluation — arXiv**
An audit of 288 responses showed overall F1 of 0.916, yet prompt-specific scorer errors ranged from 2.6 percent to 33.3 percent, and an apparent 9.3-point increase from asserting certainty fell to 2.3 points under both raters. Source: [arxiv.org](https://arxiv.org/abs/2610.31678)

**Decoupling Patient Personas and Clinical Workflows: A Dual-Agent Approach to Realistic Medical Dialogue Generation — arXiv**
CoRPS-Dial generates pre-consultation dialogues through a persona-driven patient agent and a process-guided doctor agent, then applies post-hoc quality control for role consistency, workflow completeness, and textual consistency, improving alignment with real dialogues on information coverage, clinical compliance, and naturalness. Source: [arxiv.org](https://arxiv.org/abs/2610.32443)

**Profile-Driven User Simulation via Reinforcement Learning with Hierarchical Rewards for Task-Oriented Dialogues — arXiv**
ProfileSim jointly models user demographics, Big Five personality traits, and business intents reverse-engineered from real call logs, then refines the base model with Group Relative Policy Optimization using hierarchical dialogue- and utterance-level rewards. Source: [arxiv.org](https://arxiv.org/abs/2610.32435)
---
### Under the Hood: Speculative Decoding with Live Per-User Memory
Speculative decoding already re-uses past token sequences as drafts, but most deployments freeze the draft store at build time so acceptance rates decay as user behavior drifts. SPECMEM instead writes every verified tool call back into a bounded per-user LRU store during live operation, turning the memory into a continuously updated cache of that user's recurring patterns. The side-effect gate adds a deterministic check before any irreversible action is allowed to be drafted, eliminating the classic failure mode where a high-confidence but dangerous call slips through on a stale draft. Because the store is scoped per user, cross-user leakage disappears without needing extra isolation layers, and the 27 percent acceptance gap versus a frozen store shows that the value lies almost entirely in keeping the cache warm rather than in cleverer retrieval. The practical tradeoff is extra memory per active user and the need to persist the store across sessions, yet the wall-clock speedup reaches 1.74x precisely because fewer tokens are decoded autoregressively once the store stabilizes. Teams should adopt live memory when they already log tool calls and can afford per-user state; otherwise a static high-quality seed store plus periodic refresh remains simpler. The gotcha that bites most teams is forgetting to gate irreversible actions, which turns an optimization into a correctness regression.
---
### Things to Try This Week
- Deploy the open weights of Kolibri if you need strong English-German performance at low serving cost and want full control over data residency.
- Test SPECMEM on your existing tool-calling traces to measure how quickly acceptance recovers once the live memory starts filling.
- Run the Schema Coherence Inventory items against any persona-conditioned model you use for simulated patients or affective agents to check whether assigned beliefs actually organize behavior.
- Try AKV on SGLang-based agent workloads where history summarization is currently the dominant cost driver.
---
### On the Horizon
- More open-weight MoE releases are expected to target the 3-4B active-parameter regime as teams chase the same quality-cost Pareto frontier Kolibri demonstrated.
- Additional agent memory frameworks will likely adopt live per-user stores with explicit side-effect gating once the 1.74x speedup numbers propagate.
- Evaluation papers that audit scorer behavior per prompt rather than overall accuracy are becoming the norm after the 39-point spreads shown in math tutoring and interactive studies.
