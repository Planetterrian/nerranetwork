# Models & Agents
> **Self-scaling coding benchmarks just arrived, with difficulty now set by the agents themselves rather than fixed tasks.**

**What You Need to Know:** SWE-Duel pits coding agents against each other in mirrored Red-Blue turns on real repositories, generating fresh tasks and oracles at evaluation time so leakage is impossible. GPT-5.5 with Codex CLI led as the strongest solver while Claude Opus 4.8 with mini-swe-agent led as task author. Builders should watch how this changes agent evaluation away from saturating static suites.
---
### Top Story
SWE-Duel creates a self-scaling arena where two coding agents evaluate each other over mirrored Red-Blue turns on real repositories. In each turn the Red agent proposes a feature, implements it with tests, then embeds a subtle bug with sealed trigger tests; the PR is admitted only if it passes feature and existing tests while failing exactly the bug tests and a fresh session of the same agent can repair the bug blind. The Blue agent reviews without knowing a bug exists and wins only if its revision passes all three suites. A tournament across 11 model-harness pairs on 15 repositories in five languages for 1,500 turns showed GPT-5.5 with Codex CLI repairing 98.3% of defects and Claude Opus 4.8 achieving a 27.3% Red win rate; newer versions within a family produced harder tasks. Source: [arxiv.org](https://arxiv.org/abs/2610.12569)
---
### Model Updates
**Elastic Latent Recurrence removes the one-loop tax for looped language models: arXiv NLP**
A gated state update with learned step size plus loop-index conditioning lets a single checkpoint match non-recurrent accuracy at one loop while each added loop buys more accuracy. Mixed depths introduced late in pretraining with zero-initialized conditioning cut added training cost, and reusing first-loop expert routes in MoE models trims mixed-depth update time by 11.7%. On 4B dense and 30B-A3B MoE hybrids, four loops add 7.25 and 4.75 points on a ten-task average; post-training yields Koi-4B scoring an estimated 18 on the Artificial Analysis Intelligence Index at one loop. Source: [arxiv.org](https://arxiv.org/abs/2610.12582)

**Unsupervised multimodal reward modeling needs no preference labels: arXiv NLP**
A linear head on an intermediate layer of a frozen Qwen3-VL backbone is trained to score a web caption above a perturbed version of the same caption, with labeled data used only to select the layer. The chosen layer is worth 5.8 points over the last layer; one recipe transferred without re-tuning beats or matches GPT-4o on three benchmarks at 32B scale and leads VL-RewardBench by 6.6 points. Perturbations teach the frozen head 3–5 points more than curated RLAIF-V pairs at equal budget, and the objective is convex because the backbone stays frozen. Source: [arxiv.org](https://arxiv.org/abs/2610.12707)

**Neurograf v1 delivers an end-to-end Romanian-first language-model family: arXiv NLP**
The pipeline trains five decoder-only models from 160M to 6B parameters on 131 billion tokens from a 635 GB Romanian corpus, plus instruction-tuned assistants and contrastively trained embeddings. Neurograf-6B reaches 69.89% on Romanian-context questions in the 1,000-question WWTBM benchmark while Neurograf-3.2B reaches 67.38%; compute-optimal analysis gives a parameter-scaling exponent of approximately 0.423. Source: [arxiv.org](https://arxiv.org/abs/2610.13134)

**Language models contain identifiable narrative mechanisms: arXiv NLP**
Across GPT-2-Small, Gemma-2-2B, and Llama-3.1-8B, attention heads, MLP neurons, and sparse autoencoder features correlate with narrativity. Ablating selected sets increases next-token loss more on high-narrativity text and reduces narrativity of open-ended generations, with largest downstream effects on story completion and narrative question answering. Source: [arxiv.org](https://arxiv.org/abs/2610.12989)

**Evaluating LLM creativity via long-tail performance aligns rankings with human judgments: arXiv NLP**
Creativity benchmarks lie further in the tail of reference input-output distributions than standard benchmarks; model rankings from higher-tail subsets align more closely with human judgments in LM-Arena. The new q@Tail(α) diagnostic measures mean task quality on the tail fraction of an existing benchmark and reveals substantial room to improve LLM creativity through stronger tail performance. Source: [arxiv.org](https://arxiv.org/abs/2610.12998)
---
### Agent & Tool Developments
**When Charts Deceive Web Agents introduces a paired benchmark for misleading visualizations: arXiv NLP**
MisVisAgentBench contains 280 task instances in matched clean–misleading pairs that differ only in chart evidence. Replacing clean charts with misleading counterparts reduces average task success rate by more than 34 percentage points across thirteen vision-language Web agents, with failures predominantly following the targeted misleading action branch. Source: [arxiv.org](https://arxiv.org/abs/2610.12823)

**SEEDS adds preview-guided evidence admission to search agents: arXiv NLP**
The framework exposes lightweight previews of retrieved candidates and lets the agent jointly decide which candidates and how many to inspect fully, conditioned on its current reasoning state. Across nine knowledge-intensive QA benchmarks under both local corpus and live web search, SEEDS improves search effectiveness while substantially reducing full-evidence consumption. Source: [arxiv.org](https://arxiv.org/abs/2610.12932)

**SOAR brings source-aware reinforcement learning to search agents: arXiv NLP**
The paradigm disentangles external and internal knowledge into parallel observable streams via a Source-Aware Workflow and adds Source-Consistent Reward. On 3B and 7B backbones it outperforms baselines by 7.3% and 5.4% while reducing evidence fabrication by 74.8%. Source: [arxiv.org](https://arxiv.org/abs/2610.13157)

**CoBe tests zero-shot counterfactual text editing in conversational agents: arXiv NLP**
The benchmark contains 2,000 questions across healthcare, science, business, and everyday scenarios. Frontier models achieve an average score of 58.05%, frequently defaulting to associational generation rather than preserving causal structure of the original scenario. Source: [arxiv.org](https://arxiv.org/abs/2610.13057)
---
### Practical & Community
**AutoIndexer trains causal models on chains of edits for post-generation context editing: arXiv NLP**
The model predicts marker tokens for opening and closing edits while moving a cursor, trained by perturbing ground-truth labels with inverse chained edit operations. It demonstrates post-generation insertion, substitution, and deletion capabilities most autoregressive and diffusion models lack, without compromising standard LLM benchmarks; code is at https://github.com/AutodeskAILab/autoindexer. Source: [arxiv.org](https://arxiv.org/abs/2610.12545)

**KV-Repurpose enables segment-wise KV-cache reuse beyond exact prefixes: arXiv NLP**
The vLLM-based system combines cache-aware segment scheduling, prompt construction, capacity management, and runtime monitoring. Under a Zipfian RAG-style workload where 20% of requests share a fixed prefix, it reaches 63.9% token-level cache hit rate at 30 GB capacity versus 3.3% for prefix caching; source at https://github.com/taiga333/eval-kv-repurpose. Source: [arxiv.org](https://arxiv.org/abs/2610.13060)

**CliQ-RRG generates QA-style radiology reports with disease-aware alignment: arXiv NLP**
Stage 1 aligns image and text representations using predicted disease embeddings reinforced by a Prior-Guided Attention Module; Stage 2 uses GraphRAG-guided retrieval and an LLM to restructure into concise QA pairs. The framework outperforms prior methods on two public chest X-ray benchmarks across lexical and clinical metrics; code at https://github.com/chandravardhan-singh-raghaw/CliQ-RRG. Source: [arxiv.org](https://arxiv.org/abs/2610.13059)

**From 2.1M hours of raw broadcast audio to Finnish speech SSL via confidence filtering: arXiv NLP**
ASR confidence serves as a proxy for pretraining data quality and yields 3–7% relative WER improvements over LID-based filtering despite a smaller training set. Transformer, Macaron-Net, Conformer, and E-Branchformer backbones are compared at matched parameter budgets, with gains largest at Base scale and out-of-domain. Source: [arxiv.org](https://arxiv.org/abs/2610.13102)
---
### Under the Hood: Content-Aware Temporal Recall via Semantic Lag Estimation
Time-delay systems for sequence modeling replace the single compressed hidden state of LSTMs or the fixed-dimensional state of Mamba with an explicit, content-addressable delay that is estimated on the fly. The core mechanism computes a differentiable semantic lag estimator that produces soft attention weights over history based on similarity between the current input and past tokens, yielding both a weighted historical context vector and a scalar similarity score at each step. A diagonal state-space formulation then solves the cumulative sum in closed form, delivering O(1) per-step complexity with no sequential loops inside the recurrence. A fuzzy semantic modulation layer learns context-dependent rules that decide how much weight to give the instantaneous input versus the recalled history; rule centers correspond to prototypical semantic contexts so the policy remains interpretable. On text classification and generation the approach outperforms prior state-of-the-art, but the quality gain shrinks once models exceed roughly 70B parameters because larger models already encode long-range dependencies inside their attention layers. Use this technique when you need explicit, auditable recall of specific past events under tight compute budgets; the gotcha that bites most teams is that the lag estimator must be trained on sufficiently diverse semantic contexts or it collapses to always favoring the current token.
---
### Things to Try This Week
- Run the SWE-Duel tournament harness on your own coding agent to see how its task-authoring strength compares with GPT-5.5 and Claude Opus 4.8.
- Try the AutoIndexer GitHub repo on a code-correction task to test post-generation edit capabilities that standard autoregressive models lack.
- Compare Neurograf-6B against Qwen3.5-4B on Romanian-context factual questions using the WWTBM benchmark to measure the value of language-specific pretraining.
- Experiment with SEEDS on a knowledge-intensive QA workload to measure the reduction in full-evidence consumption while preserving answer quality.
- Test KV-Repurpose on a Zipfian RAG workload to quantify the cache-hit-rate lift over standard prefix caching at fixed memory capacity.
---
### On the Horizon
- More self-scaling agent benchmarks are expected as static suites saturate.
- Additional open-weight families will release looped or recurrent-depth checkpoints that trade inference compute for accuracy at serving time.
- Finnish and other lower-resource language SSL models will continue to close the gap with high-resource counterparts through confidence-filtered broadcast data.
- Web-agent robustness benchmarks will expand beyond chart deception to other forms of misleading visual evidence.
