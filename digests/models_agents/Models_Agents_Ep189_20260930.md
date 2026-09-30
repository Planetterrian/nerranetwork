# Models & Agents
> **Memory systems for agents now split fast judgments from slow reasoning, cutting token use dramatically while boosting task success.**

**What You Need to Know:** Mnemon keeps raw conversation records and uses a lightweight decision model for quick yes-no judgments alongside an LLM for search planning. New papers introduce environment steering for agent safety, budget-aware tool retrieval, and statistical tools for LLM-judge evaluations. Builders should test the memory split and the new safety verifier on their agent workloads this week.
---
### Top Story
Mnemon keeps full conversation histories as raw dated records instead of rewriting them into facts or graphs at write time. A lightweight decision model called Jev makes dozens of independent yes-no judgments per record in under a third of a second. An LLM handles the slower System-2 work of planning searches and naming what a reply needs. On LoCoMo the system reaches 91.7 percent with gpt-4.1-mini while using under four thousand tokens of context per question. With a reasoning model it hits 92.2 percent on LoCoMo and 94.4 percent on LongMemEval-S. The approach scales from one hundred thousand to ten million tokens of history with only a 1.11 times cost increase per question. Source: [arxiv.org](https://arxiv.org/abs/2609.36059)
---
### Model Updates
**Sieve and Sage: Efficient Distraction Filtering for Reliable RALM Abstention:** arXiv NLP
Sieve screens retrieved documents for distracting or adversarial content before a heavier Sage model performs grounded generation and abstention. The two-stage split improves accuracy by up to 69.4 percentage points and Macro-F1 by 55.2 percentage points over one-stage baselines. It also delivers up to 1.99 times speedup across general and high-stakes expert domains. Source: [arxiv.org](https://arxiv.org/abs/2609.35794)

**Alignment Forecasting: Predicting Misalignment From Training Data:** arXiv NLP
Alignment Forecasting predicts whether fine-tuning on a given dataset will increase failure modes such as deception or sycophancy before training begins. ALIGNMENTFORECASTBENCH contains over five thousand forecasting questions spanning seventeen target models, thirty-two datasets, and sixteen failure modes. A forecasting scaffold that rates dataset influence and combines it with base rates beats both direct frontier-model prompting and a model fine-tuned on the task itself. Source: [arxiv.org](https://arxiv.org/abs/2609.35805)

**TRACE: Deployable Tree-Relational Structure Enhancement for Oncology LLMs:** arXiv NLP
TRACE builds an updatable tree-relational structure of oncology concepts and relations offline, then retrieves compact prompt evidence at inference time. It improves both label-free and supervised performance across ten oncology classification tasks and one MedQuAD CancerGov QA benchmark. The method outperforms vanilla RAG and generic GraphRAG while remaining useful under leakage-controlled METABRIC inputs. Source: [arxiv.org](https://arxiv.org/abs/2609.35810)

**Less Uniform Discrete Diffusion is More Powerful and Scalable:** arXiv NLP
Less Uniform Diffusion adds a less-uniform loss that directs each reverse transition toward the clean token and equips the model with per-token time embeddings. A seven-billion-parameter UDLM trained this way achieves a three-token-per-step speedup over autoregressive decoding while remaining competitive with masked diffusion baselines. The approach continues training from a seven-billion autoregressive checkpoint into a capable reasoning UDLM. Source: [arxiv.org](https://arxiv.org/abs/2609.35817)
---
### Agent & Tool Developments
**Environment Steering: Using Data Flow Control to Improve Agent Utility and Safety:** arXiv NLP
Environment Steering models the agent and execution state as database tables, tracks record-level data flows, and checks them against declarative policies at runtime. When violations occur, policy-specific feedback steers the agent toward safe trajectories. On AgentDyn the method raises task success rate above the no-defense baseline while holding attack success rate at zero percent. Source: [arxiv.org](https://arxiv.org/abs/2609.35807)

**Lookahead-R: Budget-Aware Tool Retrieval via Execution-Centric Planning:** arXiv NLP
Lookahead-R uses a lightweight execution-aware surrogate world model that predicts tool success, latency, and semantic utility without calling real APIs. A cost-sensitive Monte Carlo Tree Search navigates the tool space under strict budgets. On the hardest I3 split of ToolBench it reaches NDCG@5 of 91.40 percent, 1.24 points above the prior state-of-the-art ToolGen. Source: [arxiv.org](https://arxiv.org/abs/2609.35811)

**SCOUT: Synergizing Reasoning and Tool-Use for Computer-Use Safety:** arXiv NLP
SCOUT first reasons over task and trajectory to generate task-specific completion and safety rubrics, then uses a probing agent to gather post-execution evidence through tool calls. On AutoElicit-Bench it achieves 75.4 unsafe F1 and 74.5 completion F1. Test-time reflection lowers unsafe execution rates from 30.2 percent to 17.2 percent. Source: [arxiv.org](https://arxiv.org/abs/2609.36201)

**Constructing Challenging Browser-Use Tasks by Controlled Environment Interventions:** arXiv NLP
BreakingWeb pairs each base task with deterministic interventions at different web-stack layers while preserving the original instruction and success criterion. The benchmark contains 519 clean-intervention pairs across seven sites and twenty-nine intervention families. Interventions cut agent pass rates by 22.9 percent on average; seventy-five percent of agent failures end with a declared success even though the required change never occurred. Source: [arxiv.org](https://arxiv.org/abs/2609.35814)
---
### Practical & Community
**How to Run Statistics over LLM Judges and Trust the Results: Calibrated Inference for Small-Sample AI Evaluation with evalstats:** arXiv NLP
evalstats implements nine hypothesis tests via prediction-powered inference, including the first PPI corrections for four rank-based tests. Bootstrap-adaptive power tuning keeps estimates stable with small human calibration sets. The package automatically selects calibrated methods for evaluations with fewer than one hundred samples. Source: [arxiv.org](https://arxiv.org/abs/2609.35815)

**PACT: Pairwise-Anchored Calibrated Tuning for Single-Token Typed Decisions:** arXiv NLP
PACT adds four training terms that exploit contrastive pairs and machine-checked certificates without new annotation. On a 324-item holdout it matches published accuracy at 84.6 percent while halving position bias and lowering ordinal error on rubric fields. Seed-to-seed variance drops by half and negative log likelihood falls 26 percent versus plain cross-entropy. Source: [arxiv.org](https://arxiv.org/abs/2609.35865)

**CruxBench: A Benchmark of Information Discovery:** arXiv NLP
CruxBench grades LLM-generated questions by their value of information on 293 future-world forecasting targets. Value-of-information correlates 0.90 with independent capability measures. Even frontier models only narrowly beat a random-timing baseline on the open-ended task. Source: [arxiv.org](https://arxiv.org/abs/2609.35879)
---
### Under the Hood: Entropy-Driven Routing Between Retrieval and Long-Context Inference
Predictive entropy on the first few generated tokens already correlates 0.85 with hallucination rate on a two-thousand-generation held-out set. The router therefore escalates only when that early entropy exceeds a validation-tuned threshold. In practice the system keeps 97.4 percent of pure long-context accuracy while cutting total token spend by 70.7 percent and escalating just 18.2 percent of queries. The accuracy gap to the full long-context baseline is statistically indistinguishable from zero at standard sample sizes. The same entropy signal works across any retriever and any long-context backbone because it is produced by the model itself during ordinary decoding. Teams running mixed RAG and long-context workloads should therefore log first-token entropy on a small validation slice, sweep the threshold against their accuracy and cost targets, and deploy the resulting policy; the main gotcha is that very short or highly templated queries can produce artificially low entropy even when retrieval is incomplete.
---
### Things to Try This Week
- Try Mnemon on your longest agent conversation histories to see whether the raw-record plus fast-judgment split reduces context cost while preserving accuracy.
- Run SCOUT's two-stage verifier on any computer-use agent trajectories you already have to measure unsafe execution rates before and after reflection.
- Compare Lookahead-R against your current semantic tool retriever on the I3 split of ToolBench if budget-aware selection matters for your agent.
- Add evalstats to your next small-sample LLM-judge evaluation to obtain properly calibrated confidence intervals and hypothesis tests.
---
### On the Horizon
- New open-weight diffusion language models are expected to continue scaling beyond the seven-billion-parameter LUDI checkpoint.
- Additional multilingual voice-agent benchmarks extending the tau-Multilingual language packs are in preparation.
- Further releases of agent safety platforms that embed policy checks directly in execution environments are anticipated from multiple labs.
