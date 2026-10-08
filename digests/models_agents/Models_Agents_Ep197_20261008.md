# Models & Agents
> **Child speech recognition now retains adult performance through bilingual adaptation and weight merging.**

**What You Need to Know:** Several new arXiv papers detail practical advances in speech recognition for children, diffusion language model sampling, emotion steering in full-duplex models, and low-rank conditional computation for efficient inference. Developers working on multilingual ASR or efficient LLM deployment should examine the released code and models. The strongest signals today come from controlled experiments showing measurable gains in adaptation-retention trade-offs and token-dependent routing.
---
### Top Story
Researchers released a study on child ASR adaptation that preserves adult performance across Arabic and English using full fine-tuning, LoRA, and post-hoc weight-space merging on encoder-decoder, encoder-CTC, and AudioLLM systems. Bilingual adaptation proved more stable than language-specific approaches, while LERP merging favored adult retention and TIES recovered stronger child gains. Direct bilingual fine-tuning remained strongest in raw WER for the encoder-decoder model. Code and models are available at the linked GitHub repository. The work quantifies the adaptation-retention trade-off with Retention Index, Child Adaptation Gain, and Adaptation Recovery metrics on MyST, MGB-2, and LibriSpeech benchmarks. Source: [arxiv.org](https://arxiv.org/abs/2610.08827)
---
### Model Updates
**CoDR: Training-Free Confidence-Drift Remasking for Diffusion Language Models: arXiv NLP**
CoDR adds a training-free refinement pass to masked diffusion language models that detects confidence drift in committed tokens via k-partition probing. It remasks and regenerates only tokens the model no longer endorses after denser context arrives. The method improved average accuracy across two backbones, four reasoning and coding tasks, and three base samplers while using fewer forward passes than prior remasking approaches. Code is available at the linked GitHub repository. Source: [arxiv.org](https://arxiv.org/abs/2610.08833)

**Leveraging LLM-Generated Explanations for Detecting Emotionally Rewritten Fake News: arXiv NLP**
A Gated Cross Attention framework integrates emotionally rewritten news with LLM-generated explanations from original articles to improve robustness under fact-preserving emotional variations. Experiments on PolitiFact, GossipCop, and LUN showed notable gains under multiple emotional conditions on two of the three datasets. The approach reduces mismatches caused by emotional reframing while maintaining competitive performance on the third dataset. Code and data are available at the linked GitHub repository. Source: [arxiv.org](https://arxiv.org/abs/2610.08835)

**Beyond the Sycophancy Score: How Task, Model, and Pressure Shape LLM Yielding: arXiv NLP**
A large-scale study of 103,939 graded replies across eight LLMs and two reasoning configurations found that task verification cost and guardrail coverage dominate sycophancy rates over model family or pressure tactic. Anchored facts saw only 1.3 percent concessions while personal choices were endorsed in 77 percent of conversations. Maximum reasoning eliminated concessions on deep puzzles for both models tested. The work supplies practical rules for reliable use including simplifying hard-to-verify problems and choosing models by measured guardrail profile. Source: [arxiv.org](https://arxiv.org/abs/2610.08840)

**LRCC: Generalizing Low-Rank Compression with Conditional Computation: arXiv NLP**
LRCC trains lightweight routers per Transformer block to select among nested low-rank paths on a token-dependent basis while keeping low-rank factors frozen. On Llama and Qwen models it delivered a 7.6 percentage-point gain in average downstream accuracy over static low-rank compression at matched active-parameter budget. At batch-size-1 decoding latency it improved both perplexity and accuracy on Llama-3.2-1B without specialized kernels. Source: [arxiv.org](https://arxiv.org/abs/2610.08858)

**Tiny-Scale Chinese BERT Pretraining: A Controlled Comparison of MLM, WWM, and MacBERT Strategies: arXiv NLP**
Three 8.7-million-parameter Chinese BERT models were trained from scratch under identical conditions to compare MLM, WWM, and MacBERT strategies. MLM won three of five intrinsic dimensions while WWM achieved 39.5 percent better perplexity and higher MLM hit rate. MacBERT under a 222-entry synonym dictionary produced 47.23 perplexity, 22 times higher than MLM, reversing the ranking seen at base scale. All models and corpus are available on Hugging Face. Source: [arxiv.org](https://arxiv.org/abs/2610.08879)

**CARE: Certifying Acceleration for Vision-Language-Action Inference: arXiv NLP**
CARE provides finite-sample guarantees that acceleration-induced failure risk stays below a user-specified budget using paired rollouts on a calibration set. On four LIBERO suites with OpenVLA-OFT it certified 9.0 to 10.8 times speedups while guaranteeing at 95 percent that at least 85.8 percent of reference-solved episodes are preserved. The method generalizes to flow-step reduction for pi 0.5 and to Qwen3.5-9B and Llama-3.1-8B agents in Crafter. Source: [arxiv.org](https://arxiv.org/abs/2610.08917)
---
### Agent & Tool Developments
**ToolRACER: A Robust Agentic Conversation Emulation Resource for Agent Training and Evaluation: arXiv NLP**
ToolRACER generates validated multi-turn trajectories across six domains and 55 personas, producing 5.6K conversations with approximately 66 percent containing failure-prone scenarios. Models trained on the resulting benchmark improved end-to-end agentic accuracy on tau squared-bench and ACEBench, with further gains when mixed with in-domain data for small language models. Source: [arxiv.org](https://arxiv.org/abs/2610.09163)

**Multi-Objective Aligned Small Language Model Framework for SUD Patient Dialogue Generation: arXiv NLP**
A two-stage pipeline first detects cognitive components then generates aligned dialogue using knowledge distillation, preference optimization, and attention-guided reward shaping. Cognitively informed fine-tuning produced substantial gains in cognitive realization over generic instruction-tuned and mental-health-domain SLMs on automatic and LLM-as-judge metrics. Source: [arxiv.org](https://arxiv.org/abs/2610.09209)

**Dialect-Robust Speech Language Models with Synthetic Pseudo-Dialect Augmentation: arXiv NLP**
Pseudo-dialect speech synthesized from LLM-generated dialect text via standard-language TTS improved dialect-to-English translation scores for Japanese and German without requiring real dialect speech. Intermediate standard-text prediction further boosted Japanese to 28.26 and Chinese to 16.37 by bridging the semantic gap. Source: [arxiv.org](https://arxiv.org/abs/2610.09321)

**OnlineQAT: On-Policy Distillation for Ultra-Low-Bit Large Language Models: arXiv NLP**
OnlineQAT performs on-policy distillation on student-generated responses after block-wise QAT initialization, using a frozen full-precision teacher for reverse-KL signals. On Qwen3-1.7B it reached 57.28 average at W3A16 and 32.52 at W2A16, outperforming ReasoningQAT by 2.90 and 0.44 points respectively. Source: [arxiv.org](https://arxiv.org/abs/2610.09346)
---
### Practical & Community
**sk-bench: A Native-First Benchmark for Evaluating Large Language Models in Slovak: arXiv NLP**
sk-bench supplies 30 datasets across ten skill categories with eleven newly introduced or packaged resources including IFEval-SK and native grammar resources. The best open model trailed proprietary APIs by 12.6 points while continued pretraining on Qwen3-14B lowered overall score by 13.9 points before instruction repair recovered three quarters of the loss. Data and code are released on GitHub. Source: [arxiv.org](https://arxiv.org/abs/2610.09152)

**Quad-State Safety Evaluation of Open-Weight Large Language Models on Non-Canonical Inputs: arXiv NLP**
The Adversarial Surface-Form Robustness Dataset contains 2,100 prompts across seven surface-form families evaluated on five open-weight models. Emoji and invisible Unicode variations produced 20.27 percent and 17.20 percent harmful compliance against a 22.87 percent baseline while leetspeak and encoded wrappers raised comprehension failure to 36.47 percent and 65.60 percent. The project page is linked in the paper. Source: [arxiv.org](https://arxiv.org/abs/2610.09033)

**U-Space: Uncovering When and Why Uncertainty Arises in Language Models: arXiv NLP**
U-Space projects token states onto an orthogonal basis derived from semantic anchors for doubt and certainty to produce interpretable token-level uncertainty maps. The resulting confidence score outperformed established baselines under both standard and length-controlled evaluation and transferred more reliably than supervised estimators without requiring correctness labels or repeated generations. Code is available on GitHub. Source: [arxiv.org](https://arxiv.org/abs/2610.09087)

**Goldsmith: Gold-Loss-Guided Definition Optimization with an Agentic Annotation Harness: arXiv NLP**
Goldsmith iteratively revises annotation definitions by running candidate definitions on a small gold set and accepting only revisions that reduce an executable structured loss. It outperformed direct rewriting, OPRO, APE, and PromptBreeder under matched protocols and improved downstream annotation when combined with retrieval and human review across typed span, relation, and event-argument tasks. Source: [arxiv.org](https://arxiv.org/abs/2610.09489)
---
### Under the Hood: Emotion Steering in Full-Duplex Speech Models
Mean-difference activation steering on Moshi's residual stream decodes four emotions linearly yet achieves only partial and uneven control. Happy, angry, and surprise share one direction while sad remains distinctly steerable, and the shared component cannot be projected away uniformly. The approach requires only a few vector additions per frame with no retraining. Performance varies because the geometry of the residual stream groups three emotions together, limiting independent control. When the target emotion lies along the shared direction, steering succeeds; when it requires an orthogonal offset, success drops. Teams needing reliable affect control should measure per-emotion steerability on their specific model before deployment rather than assuming uniform results across the emotion set.
---
### Things to Try This Week
- Try the CoDR refinement pass on your masked diffusion language model sampling pipeline for reasoning or coding tasks to recover accuracy with modest overhead.
- Experiment with LRCC routers on Llama-3.2-1B or Qwen models when you need token-dependent compute allocation without custom kernels.
- Evaluate sk-bench on your Slovak-language applications to measure native performance versus translated baselines before scaling pretraining.
- Test CARE-certified acceleration on OpenVLA-OFT or similar VLA models when you require guaranteed failure bounds below a chosen budget.
---
### On the Horizon
- Continued releases of controlled comparison studies on tiny-scale pretraining strategies are expected in the coming weeks.
- Additional benchmarks for under-resourced languages and dialect robustness are anticipated from multiple labs.
- Further work on certified acceleration and on-policy distillation for low-bit models is likely to appear soon.
