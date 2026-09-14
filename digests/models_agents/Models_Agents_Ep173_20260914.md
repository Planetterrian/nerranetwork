# Models & Agents
> **Sam Altman lays out two concrete risks that could derail AI progress and must be actively avoided.**

**What You Need to Know:** OpenAI's CEO details the twin dangers of losing control to AI and excessive power concentration, while calling for safety cases before major training runs and federal safety rules. Several new papers introduce modular fact-checking, byte-level distillation that eventually beats token models, and agent frameworks that let general models drive physical robots without task-specific training. Builders should watch the byte-model scaling results and the new agent-as-policy approach for manipulation tasks.
---
### Top Story
Sam Altman posted two specific risks that AI progress must avoid. The first is losing control of the future to AI, which requires alignment and safety techniques to stay ahead of capabilities. The second is excessive concentration of power in one person, company, or country that could impose a single worldview. He argues that a narrow middle path is needed, including consistent federal safety requirements and safety cases before frontier reinforcement learning runs. OpenAI already uses explicit safety cases ahead of major training runs in addition to pre-release work. The post emphasizes that pacing means slowing progress relative to what is technically possible, not stopping it, and that international coordination will eventually require government help. Source: [x.com](https://x.com/sama/status/2099352016988614852)
---
### Model Updates
**Breaking the Token Ceiling: Distilling Smaller, Stronger Byte Models — arXiv NLP**
Researchers introduce two methods to convert token logits to byte logits for distillation: Marginalize-It for approximate conversion and End-Of-Token for exact conversion. They train decoder-only dense transformer models with roughly one billion parameters across token and byte tokenization schemes up to one trillion bytes of data. Token-1B models outperform byte models in the low-FLOP regime but plateau, while byte models start lower yet surpass them with more compute and reach a higher performance ceiling. Distilled End-Of-Token-1B models are predicted to outperform distilled Token-1B by up to four percent asymptotically and match Token-1B performance using only one-sixth the training data. The byte models also reduce logit storage costs to roughly one-fifth because they operate over a 256-byte vocabulary instead of roughly 100K tokens. Source: [arxiv.org](https://arxiv.org/abs/2609.12303)

**Representation-based Masked Diffusion Model — arXiv NLP**
The new RMDM framework encodes text into a continuous semantic space with a pretrained encoder and learns an invertible transformation that normalizes the representation distribution to a Gaussian prior. It conditions a masked diffusion model on this latent semantic representation to coordinate parallel token updates during generation. Empirical results show that RMDM significantly improves generation quality, especially in aggressive few-step sampling regimes. Source: [arxiv.org](https://arxiv.org/abs/2609.12382)

**Chopthin-Consensus Power Sampling: A Diversity-Preserving Approach to LLM Decoding — arXiv NLP**
Chopthin-Consensus Power Sampling applies the Chopthin resampler to LLM decoding to enforce an upper bound on the ratio between largest and smallest weights instead of equalizing weights. The method preserves a richer set of distinct reasoning paths while keeping the weighted SMC approximation unchanged in conditional expectation and guaranteeing a lower bound on effective sample size. Combined with semantic-majority selection that merges token-identical trajectories and clusters semantically equivalent answers, CCPS matches or exceeds Power-SMC baseline accuracy in 14 of 15 settings across three open-weight models and five reasoning benchmarks, with absolute gains up to 10.6 percentage points. Source: [arxiv.org](https://arxiv.org/abs/2609.12243)

**ORQA: An Occupation-Realistic Question and Answer Framework for LLM Professional Knowledge — arXiv NLP**
ORQA connects O*NET occupations to trusted occupation-specific websites and converts them into source-traceable question-answer pairs covering 116 occupations from all 21 major SOC groups with 480 questions from 187 websites. Claude Opus 4.6, GPT-5.4 and Claude Sonnet 4.6 perform best at approximately 58-62 percent while smaller open-weight models reach 33-41 percent. Healthcare-related occupations reach 78 percent accuracy while Office and Administrative Support reach approximately 40 percent, with some individual occupations at essentially zero. Source: [arxiv.org](https://arxiv.org/abs/2609.12366)
---
### Agent & Tool Developments
**Agent as Policy for Robotic Manipulation — arXiv NLP**
AGP places task planning and execution under a general-purpose agent's control so the agent interprets visual evidence, writes executable programs, issues motion commands, and revises actions based on physical outcomes. The approach is tested across precision manipulation, dynamic motions, and deformable objects including assembly from human videos, block construction from goal images, die reorientation, targeted throwing, and bimanual towel folding. AGP achieves 100 percent, 100 percent, and 80 percent success rates on three block construction configurations without any task-specific or environment-specific training. Source: [arxiv.org](https://arxiv.org/abs/2609.12541)

**LifeMem: Enabling Lifelong Experience Reuse for LLM Agents — arXiv NLP**
LifeMem clusters accumulated interaction trajectories based on underlying workflows to extract reusable skills and recalls relevant skills and trajectories at inference time to guide actions across new tasks. Experiments across 10 environments and over 13k tasks with 2k newly annotated trajectories show reduced forgetting on learned tasks and superior cross-task transfer. Consolidating structurally similar trajectories within memory further boosts performance. Source: [arxiv.org](https://arxiv.org/abs/2609.12655)

**CueMem: Cue-Guided Context Reconstruction for Long-Term Conversational Memory — arXiv NLP**
CueMem extracts fine-grained memory cues from dialogue turns, links each cue to its source turn, and at query time retrieves relevant cues, maps them to source-turn anchors, and expands over a turn graph to reconstruct compact evidence context. Experiments on LoCoMo and LongMemEval show consistent outperformance of representative long-term memory baselines while reducing query-time input tokens and latency compared with full-history LLM settings. Source: [arxiv.org](https://arxiv.org/abs/2609.12354)

**DuplexDrama: A Synthesized Dialogue Dataset with Scenarios, Full-Duplex Behaviors, Expressive Speech, and Sound Events — arXiv NLP**
DuplexDrama is built via a four-stage pipeline and contains more than 2,000 hours of audio across a 64-voice timbre pool spanning 13 personas and five age buckets, with 3.8 percent of turns carrying at least one full-duplex behavior. A curated subset of 6,400 bilingual dialogues totaling 800 hours will be released, with roughly 500 hours in Chinese and 300 hours in English. Source: [arxiv.org](https://arxiv.org/abs/2609.12872)
---
### Practical & Community
**Built a little local web app to help edit commit messages for a repo — Simon Willison (AI builder) (X)**
Simon Willison released a local web app that helps edit commit messages for a repository. The tool runs entirely locally and is documented at simonwillison.net. Source: [x.com](https://x.com/simonw/status/2099310866021916710)

**GraphProfiler: Source-Linked Sensitive Attribute Inference via Personal Knowledge Graphs — arXiv NLP**
GraphProfiler represents each user's post history as a source-linked personal knowledge graph where nodes and edges trace back to the originating post and resolves attribute predictions to cited graph records and source texts. It reaches 86.7 percent attack success rate on the eight-attribute SynthPAI benchmark and 84.6 percent on PANDORA while citing supporting evidence for over 98 percent of predictions. Source: [arxiv.org](https://arxiv.org/abs/2609.12448)

**Meddies-PII: A Multilingual Framework for Personally Identifiable Information Extraction in Clinical De-identification — arXiv NLP**
Meddies-PII-Dataset contains one million synthetic clinical documents spanning seventeen languages and nine PII labels, generated with attribute-conditioned prompts and validated through thirteen deterministic gates. The resulting Meddies-PII-Model achieves a mean F1 of 0.827 across fifteen external benchmarks. Source: [arxiv.org](https://arxiv.org/abs/2609.12544)

**Zipbench: Low-Cost Framework for Compressing Comprehensive Benchmarks of Large Language Models — arXiv NLP**
Zipbench evaluates only a small set of anchor LLMs, synthesizes pseudo evaluation results, learns compact sample representations, and selects a small yet representative subset. The resulting ZipBench Zoo collection of compact versions of over 100 benchmark proxies achieves mean absolute errors of 0.002 to 0.02 and average Spearman correlations of approximately 0.98 with the full benchmarks. Source: [arxiv.org](https://arxiv.org/abs/2609.12475)
---
### Under the Hood: Rate-Distortion Limits on Factual Hallucination
The paper models factual recall as a coverage-compression tradeoff where a learner observes M training facts, compresses them into at most B bits, and answers test queries without retrieval. The derived bound separates two error sources: compression distortion on observed facts given by the inverse rate-distortion function of a uniform K-ary source, plus missing coverage on unobserved facts. Simulations and controlled fact-injection probes in modern language models confirm that lossy recall of observed facts under finite memory is a separable failure mode distinct from simple absence of facts. When memory is constrained, even facts that were seen during training can only be stored approximately, producing hallucinations that look like retrieval failures but originate in compression. The bound gives a compact way to reason about selective memory, forced compression, structure, retrieval, abstention, and long-context organization. Teams facing persistent factual errors on known content should first measure effective trainable memory load before assuming additional retrieval will solve the problem.
---
### Things to Try This Week
- Try the local commit-rewriter web app from Simon Willison if you frequently edit commit messages in a repository.
- Test the byte-distilled End-Of-Token models on reasoning benchmarks once weights are released, especially if you are compute-constrained.
- Experiment with AGP-style agent control on a physical robot arm for simple manipulation tasks if you have access to one.
- Run Zipbench on a new evaluation suite you care about to reduce benchmark cost while preserving rank order.
---
### On the Horizon
- More results from the R2VC modular fact-checking architecture are expected as the code and ablations are examined.
- Additional occupation-level benchmarks following the ORQA methodology may appear for other professional domains.
- Further full-duplex dialogue datasets building on DuplexDrama are likely given the validation results already shown.
