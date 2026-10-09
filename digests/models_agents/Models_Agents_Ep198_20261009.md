# Models & Agents
> **Anthropic now scans opted-in open-source projects for vulnerabilities with frontier models and supplies proof-of-concept fixes at no cost.**

**What You Need to Know:** Anthropic launches OSS Scanner and the Anthropic Cyber Mission to secure open-source software and critical infrastructure while making Claude available to federal agencies. New arXiv work introduces Diffu-LoRA for diffusion personalization, a 50-million-token memory layer that avoids recompute, and matrix-approximation sparse attention. Builders should watch the open-source security tooling and the memory-layer package for immediate experimentation.
---
### Top Story
Anthropic is launching OSS Scanner, a free service that uses its frontier models to periodically scan opted-in open-source projects for vulnerabilities. The scanner supplies a proof-of-concept exploit, an explanation, and a suggested fix in each report. The company is also committing one hundred fifty million dollars to the Genesis Mission and will make Claude plus technical support available to more than fifteen federal agencies. At the same time it is rolling out the Anthropic Cyber Mission focused on critical infrastructure and open-source security. These moves expand Anthropic’s security work beyond its own models into shared infrastructure protection. Source: [anthropic.com](https://www.anthropic.com/research/launching-opt-in-vuln-finding-service-for-open-source) Source: [anthropic.com](https://www.anthropic.com/news/genesis-mission-commitment) Source: [anthropic.com](https://www.anthropic.com/news/anthropic-cyber-mission)
---
### Model Updates
**Diffu-LoRA learns per-layer rank allocation for diffusion personalization: arXiv NLP**
Diffu-LoRA inserts gated low-rank adapters into the linear layers of Transformer blocks inside Stable Diffusion. Bilevel optimization trains the adapters and gates on separate data splits while progressive pruning removes low-value components to meet a target rank budget. Experiments on DreamBooth subjects show higher subject fidelity and prompt alignment than standard LoRA or full fine-tuning baselines. The method keeps the pretrained backbone frozen throughout training. Source: [arxiv.org](https://arxiv.org/abs/2610.10550)

**Lossy compressive text autoencoders reach lossless compression parity at 2.24 bits per byte: arXiv NLP**
The autoencoder performs residual downscaling and upscaling along the time axis with a residual low-dimension discrete bottleneck. It matches lossless text compression algorithms at 2.24 bits per byte on web text while retaining usable reconstruction quality measured by BLEU and LLM judges. Downstream question-answering and semantic similarity benchmarks remain competitive across compression levels. Source: [arxiv.org](https://arxiv.org/abs/2610.10738)

**Real long-term memory stores fifty million tokens with no recompute on a single H100: arXiv NLP**
The galahad-kv package saves the key-value state of sixteen-thousand-token blocks to encrypted local NVMe and reloads them byte-exact. Loading a block is two point eight to four point three times faster than recompute and uses eight point eight to twelve point three times less GPU energy. On Gemma 4 twelve billion and thirty-one billion parameter models the approach answers facts planted millions of tokens earlier with eighty-two and ninety-eight percent accuracy respectively. Source: [arxiv.org](https://arxiv.org/abs/2610.10845)

**Matrix-approximation sparse attention replaces mass-based selection with closed-form error reduction: arXiv NLP**
MASA scores each sparse unit by how much it reduces matrix-product approximation error instead of keeping the largest attention values. The method acts as a plug-in correction on existing sparse attention frameworks without changing kernels or budgets. Experiments across multiple backbones and benchmarks show consistent accuracy gains while preserving the original sparsity pattern. Source: [arxiv.org](https://arxiv.org/abs/2610.10871)
---
### Agent & Tool Developments
**Stochastic teacher intervention improves on-policy distillation for multi-turn agents: arXiv NLP**
STI-OPD uses teacher-student policy discrepancy measured by KL divergence to decide when to replace a student action with a teacher-generated one. A stochastic intervention schedule samples from the resulting probability instead of using fixed thresholds. An importance-weighted reverse KL objective corrects token sampling mismatch on the resulting mixed-policy trajectories. The approach outperforms prior on-policy distillation baselines on tool-integrated reasoning and long-horizon interaction benchmarks. Source: [arxiv.org](https://arxiv.org/abs/2610.10878)

**Lapras adds latent reasoning to time-series language models: arXiv NLP**
Lapras trains a student model to align hidden states with a teacher that produces explicit chain-of-thought traces. The student reasons in continuous joint time-series and language space and emits text only for the final answer. Across four backbones and five benchmarks the method improves average F1 by up to ten point seven nine percent while generating twenty-three point nine times fewer tokens. Source: [arxiv.org](https://arxiv.org/abs/2610.11111)

**SFT-as-context lets parent models acquire fine-tuned capabilities without forgetting: arXiv NLP**
The method feeds the SFT model’s response as context to the parent model so the parent can use in-context learning for specialized tasks. Across nineteen parent-SFT pairs and eleven benchmarks the approach stays within two point two percentage points of the SFT model on fine-tuned capabilities while remaining within two point two percentage points of the parent on general capabilities. It can solve queries that require both fine-tuned and general skills even when neither model succeeds alone. Source: [arxiv.org](https://arxiv.org/abs/2610.11132)

**REMORY supplements textual summaries with bounded soft memory tokens for long-horizon agents: arXiv NLP**
The neural memory network learns to generate a short sequence of soft tokens conditioned on the summary that help a frozen LLM approximate the continuation it would produce with full history. On SummHay the method improves source attribution at nearly unchanged insight coverage while using only five point two percent of the input positions. Both Qwen3.8-27B and GLM-5.3-Flash show consistent gains and fewer repeated tool outputs on BrowseComp and Terminal-Bench 2.1. Source: [arxiv.org](https://arxiv.org/abs/2610.11287)
---
### Practical & Community
**Grammar concept annotation at scale with fine-tuned 0.8B models outperforms prompted frontier models: arXiv NLP**
An 0.8B Qwen3.5 model fine-tuned on filtered teacher supervision is deployed in an end-to-end grammar mastery tracker. On two human-curated benchmarks the model exceeds prompted GPT-5.4 and GPT-5.6 Sol in precision and recall under nested matching criteria. Serving cost drops by approximately sixteen times and a live experiment records fifteen point eight percent higher learner engagement plus thirteen point two percent higher GMV from new lessons. Source: [arxiv.org](https://arxiv.org/abs/2610.10827)

**SignRAG unifies retrieval-augmented gloss-free sign language translation for decoder-only LLMs: arXiv NLP**
Hierarchical pretraining first learns sign representations then aligns the encoder with an LLM. Target-domain retrieval augmentation supplies instance-specific translation cues and retrieval-utility-guided reinforcement fine-tuning balances translation quality against harmful reliance. The method sets new state-of-the-art results on multiple SLT benchmarks and is the first gloss-free approach to outperform gloss-supervised methods on all metrics for CSL-Daily. Source: [arxiv.org](https://arxiv.org/abs/2610.11371)

**When citations mislead benchmark tests claim-level legal hallucination detection: arXiv NLP**
PARCEL contains three thousand three hundred ninety-six parenthetical-style claims from recent New York Court of Appeals decisions labeled Supported, Refuted, or Not Found. Strongest models reach up to zero point nine seven accuracy yet still incorrectly mark unsupported claims as supported even when full opinion text is supplied. Missing support is harder to detect than direct contradiction and fabricated but plausible citations cause the largest performance drop. Source: [arxiv.org](https://arxiv.org/abs/2610.10971)

**Clinician queries diverge sharply from public clinical AI benchmarks: arXiv NLP**
Analysis of one hundred twenty-seven thousand eight hundred thirty-three real queries from six thousand three hundred forty-two clinicians shows documentation and administration tasks comprise thirty-six point two percent and knowledge retrieval twenty-eight point nine percent. The median public benchmark shares only thirty-one percent of the task mix of actual use and contains no documentation requests. Benchmarks designed to resemble clinical practice are individually no closer to real use than those in frontier model reports. Source: [arxiv.org](https://arxiv.org/abs/2610.11069)
---
### Under the Hood: Bilevel optimization for learned rank allocation
Bilevel optimization separates the update of adapter weights from the update of gate parameters by training each on its own data split. The outer loop optimizes the gates while the inner loop optimizes the adapters, so the gate values reflect how much each low-rank component actually improves held-out performance rather than training-set fit. Progressive pruning then removes the lowest-valued gates until the prescribed rank budget is met, producing a nonuniform allocation across layers that still respects the total parameter count. The procedure adds roughly one extra forward-backward pass per pruning step yet removes the need for manual layer-wise rank search. In practice the method works best when the target domain is small enough that full fine-tuning would overfit but large enough that uniform low-rank adapters leave some layers under-capacity. Teams facing exactly that regime should try the bilevel-plus-pruning recipe before falling back to hand-tuned LoRA ranks.
---
### Things to Try This Week
- Try the galahad-kv package on a single H100 with Gemma 4 to store and reload KV blocks across a fifty-million-token stream without recompute.
- Test Diffu-LoRA on a DreamBooth subject to see whether learned rank allocation improves subject fidelity over standard LoRA at the same budget.
- Run SignRAG on a CSL-Daily sample to check whether the retrieval-augmented gloss-free pipeline beats your current gloss-supervised baseline.
- Feed an SFT model response back to its parent model on a mixed general-plus-specialized query to measure whether the context trick recovers both capabilities.
---
### On the Horizon
- Anthropic plans to expand OSS Scanner coverage and report additional findings from the Genesis Mission in the coming weeks.
- Multiple labs are expected to release updated long-context memory layers following the galahad-kv results.
- New sign-language translation benchmarks that include retrieval-augmented settings are anticipated later this month.
