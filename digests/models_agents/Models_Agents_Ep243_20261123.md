**# Models & Agents**
> **Architect Labs' AI-designed Frostbite CPU runs interaction nets at 4.59x performance per watt over in-order cores.**

**What You Need to Know:** Architect Labs released Frostbite, an AI-designed CPU that moves interaction-net computation into hardware after agents handled the full flow from theory to 7 nm GDS. New arXiv work shows context-bank rot degrades Text-to-SQL consistency and that search-native pretraining can be folded into ordinary corpora. MedicalRSI and ProbeAgent introduce recursive self-improvement and automated failure diagnosis for agents. Builders should test the new architecture papers and the two agent frameworks this week.
---
### Top Story
Architect Labs introduced Frostbite, an AI-designed CPU that runs interaction nets in hardware. Agents took the design from theory through place-and-route to a 7 nm GDSII tape-out. Pre-silicon tests show 4.59x performance per watt versus a conventional in-order core on the same workload class. The result demonstrates that agent-driven hardware design can now target specialized execution models rather than only software stacks. Teams working on long-horizon agent runtimes or custom accelerators should examine the released GDS and the interaction-net ISA. Further silicon validation and compiler support are the next milestones to watch. Source: [marktechpost.com](https://www.marktechpost.com/2026/11/23/architect-labs-frostbite-ai-designed-cpu-interaction-nets/)
---
### Model Updates
**Hy-MT3 expands to 102 languages with measurable drops in mistranslation and omission rates:** Hy-MT3-30B-A3B (MoE) cuts mistranslations 43 %, omissions 74 %, and instruction-following errors 40 % on real-world data while activating only 3 B parameters; the 2 B and 7 B dense variants are also released. The model family adds game-localization and image-translation tracks with dedicated evaluation harnesses. Source: [arxiv.org](https://arxiv.org/abs/2611.27673)

**Typhoon OCR 2 adds prompt-driven extraction and full-page structured parsing for Thai, English, and Chinese:** The 2 B and 0.8 B models are fine-tuned from open document parsers then refined with GRPO; on Thai MDPBench the 2 B model reaches 80.7 and on ThaiOCRBench 59.91 while staying within 0.3 points of its English base on olmOCR-bench. Source: [arxiv.org](https://arxiv.org/abs/2611.27494)

**Weight-space programming writes in-context learning directly into model weights:** Four frontier editors applied to six tasks across three weaker model families reach ICL and LoRA fine-tuning accuracy by writing the few-shot residual into near-silent MLP units; the strongest editor also generates its own examples from unlabeled inputs. Source: [arxiv.org](https://arxiv.org/abs/2611.26841)

**Non-expanding gated continued-fraction layers replace feed-forward blocks while preserving throughput:** The new component re-implements division via log-exp and stabilizes deeper CoFrGeNets without incremental training; on GPT-2, Llama-3, Mamba-2 and nano-MoE it matches or exceeds prior continued-fraction work with higher tokens per second. Source: [arxiv.org](https://arxiv.org/abs/2611.26835)

**LLMs memorize reinforced hallucinations during post-training RL:** Across six open models, recall of self-generated hallucinations that receive outcome-based rewards rises 4.83 % on average while unrewarded hallucinations rise only 0.17 %; backtracking templates inherited from reasoning training further entrench false facts that the model later retracts. Source: [arxiv.org](https://arxiv.org/abs/2611.26863)

**Partially canonical axes appear in LLM residual streams across twelve models:** Native coordinate axes align better with other models, human brain responses, and interpretable linguistic features than random rotations that preserve geometry, yet still fall short of optimal alignment. Source: [arxiv.org](https://arxiv.org/abs/2611.26920)
---
### Agent & Tool Developments
**MedicalRSI performs recursive self-improvement by co-evolving solver and improver models:** The framework trains an Improver to write task-specific harnesses from solver failures; both roles update together so the improvement strategy adapts to unsolved problems. On multiple medical benchmarks and LLM backbones it outperforms fixed-strategy self-improvement and transfers to unseen workflows and new databases. Source: [arxiv.org](https://arxiv.org/abs/2611.26806)

**ProbeAgent automatically discovers, explains, and groups agent failures across 22 configurations:** Starting from benchmark trajectories it builds executable tests, validates them against reference solutions, then generates new tasks that isolate suspected causes; human annotators accept 90 % of the resulting failure-mode descriptions and reject 83.3 % of similar alternatives. Source: [arxiv.org](https://arxiv.org/abs/2611.26897)

**Co-evolving behavioral agents and detectors improves detection of adaptive information operations:** On 20 Twitter IO campaigns the resulting detector reduces missed detections of adaptive agents by 65 % relative to a detector trained only on archived campaigns while holding false-alarm rate constant; engagement-seeking agents become easier to catch after training. Source: [arxiv.org](https://arxiv.org/abs/2611.27156)

**Senior agents frequently fail role-integrity checks on subordinate material:** Across eight LLMs and 12 000 episodes they adopt planted procedural errors in only 2.9 % of rulings yet follow majority generic reviews up to 71 % of the time and drop witness limitations up to 65 % of cited claims; obligation prompts reduce but do not eliminate the failures. Source: [arxiv.org](https://arxiv.org/abs/2611.27139)

**Correct precedents induce policy violations in on-device agents:** A single correct release of a now-unrestricted item halves the safe rate on the next still-restricted item in 13 open-weight models; Paired Decision Distillation restores the safe rate to near 100 % via a lightweight LoRA without extra prompt text. Source: [arxiv.org](https://arxiv.org/abs/2611.27216)
---
### Practical & Community
**Tasklets supplies a shared benchmark of small synthetic tasks for sequence-mixing layers:** The suite covers recall, sequence manipulation, and state tracking with reproducible low-cost evaluation code; controlled experiments compare a broad range of layer types on identical small models. Source: [arxiv.org](https://arxiv.org/abs/2611.27607)

**Open CDLM provides a benchmark and library for continuous diffusion language models:** It pairs likelihood bounds with Kernel Text Discrepancy and diversity diagnostics so that generative-perplexity scores alone no longer mask mode collapse; the library supports reproducible sampler comparisons on OpenWebText. Source: [arxiv.org](https://arxiv.org/abs/2611.27536)

**WaXup augments introspection training sets by linear interpolation in weight space:** Weight-averaged experts inherit behaviors from their parents; on hidden-behavior models, a real-world NLP meta-dataset, and adversarial AuditBench the method improves description accuracy and robustness to distribution shift. Source: [arxiv.org](https://arxiv.org/abs/2611.27353)

**Explicit Style Extraction improves personalized long-form generation on LongLaMP:** StylePrism (28 stylistic aspects) plus two revision passes guided by self-scored profiles raises ROUGE and METEOR in 25 of 27 comparisons across three LLMs, averaging +10.2 % and reaching +35.8 % on individual tasks. Source: [arxiv.org](https://arxiv.org/abs/2611.27211)

**Document-only adaptation matches transcript-based ASR adaptation for new domains:** Denoising-based text-only adaptation fed either raw domain documents or LLM-rendered spoken dialogs reaches or approaches real-transcript performance on in-domain, out-of-domain, and cross-domain settings; a new document-grounded benchmark is released. Source: [arxiv.org](https://arxiv.org/abs/2611.27434)
---
### Also Today
**Technical safety benchmarks fail to secure public legitimacy for artificial intelligence:** Bioengineer.org Source: [bioengineer.org](https://bioengineer.org/technical-safety-benchmarks-fail-to-secure-public-legitimacy-for-artificial-intelligence/)

**Know Your Context Bank diagnoses and repairs inconsistency in enterprise Text-to-SQL context banks:** arXiv Source: [arxiv.org](https://arxiv.org/abs/2611.26775)

**Flat text matches single-model performance for violent-video review while graph and message-passing interfaces lag:** arXiv Source: [arxiv.org](https://arxiv.org/abs/2611.26776)

**Search-Native Pretraining teaches models to emit search calls during ordinary language-model pretraining:** arXiv Source: [arxiv.org](https://arxiv.org/abs/2611.26809)

**Token covariance maps reveal a consistent compress-then-compare organization across 14 decoder-only models:** arXiv Source: [arxiv.org](https://arxiv.org/abs/2611.26874)

**PreRun benchmark measures LLM runtime prediction before any execution occurs:** arXiv Source: [arxiv.org](https://arxiv.org/abs/2611.26875)

**Beyond Prompt Heuristics shows child-safety alignment collapses on requests lacking explicit harm-category cues:** arXiv Source: [arxiv.org](https://arxiv.org/abs/2611.26965)

**NightmareDiscourseBench supplies 12 fiction samples with metadata for direct-discourse identification:** arXiv Source: [arxiv.org](https://arxiv.org/abs/2611.27059)

**When Do LLM-Elicited Priors Help audits Bayesian regression priors on hidden-feature housing data:** arXiv Source: [arxiv.org](https://arxiv.org/abs/2611.27075)

**Lossless re-tokenization displaces RLVR updates by up to 0.556 batch-equivalents on Qwen2.5-0.5B:** arXiv Source: [arxiv.org](https://arxiv.org/abs/2611.27083)

**Staged attribution protocol separates automation gains from agent contributions in model validation:** arXiv Source: [arxiv.org](https://arxiv.org/abs/2611.27094)

**Vision Follow-Through benchmark measures whether IPO forward-looking claims are later realized:** arXiv Source: [arxiv.org](https://arxiv.org/abs/2611.27273)

**Observed Curated Reused quantifies observation bias created when clinical cases enter knowledge graphs via their own publications:** arXiv Source: [arxiv.org](https://arxiv.org/abs/2611.27301)

**Leave-One-Out Word JSD localizes Phantom Context Influence and enables single-word KV suppression that lifts CoT accuracy up to 8.9 points:** arXiv Source: [arxiv.org](https://arxiv.org/abs/2611.27317)

**BPE compression of reasoning traces reduces token count 14.7 % on average with 1.6-point accuracy cost across three model scales:** arXiv Source: [arxiv.org](https://arxiv.org/abs/2611.27326)

**Short-horizon process rewards computed on semantic segments outperform single outcome rewards on long-form generation:** arXiv Source: [arxiv.org](https://arxiv.org/abs/2611.27348)

**ORBIT recovers accuracy on low-resource languages for multimodal fact verification at inference time:** arXiv Source: [arxiv.org](https://arxiv.org/abs/2611.27421)

**Silent Arbitration shows LLMs resolve co-authoritative persona conflicts without surfacing the conflict in 78 % of task responses:** arXiv Source: [arxiv.org](https://arxiv.org/abs/2611.27444)

**Capability regions remain causally effective after quantization, pruning, and LoRA even when parameter overlap drops:** arXiv Source: [arxiv.org](https://arxiv.org/abs/2611.27445)

**Auditing Post-Training Unlearning tracks forget-data features across denoising stages in LLaDA-8B-Instruct:** arXiv Source: [arxiv.org](https://arxiv.org/abs/2611.27652)

**Decision models reach within one macro-F1 point of target-fine-tuned encoders on multilingual emotion classification while running at lower latency:** arXiv Source: [arxiv.org](https://arxiv.org/abs/2611.27721)
---
---
### Things to Try This Week
- Test Frostbite’s interaction-net ISA on a small agent workload if you have access to the released GDS or simulation artifacts.
- Run MedicalRSI on a medical workflow you already benchmark; the co-evolution loop is the component to inspect first.
- Apply the context-bank consistency scorer from the BIRD paper to any enterprise Text-to-SQL collection you maintain.
- Try Tasklets on a new sequence-mixing layer proposal before scaling to full pre-training runs.
- Evaluate WaXup-style weight-space mixing on your own expert fine-tunes if you already produce multiple domain adapters.
---
### On the Horizon
- Continued silicon validation results for Frostbite and similar agent-designed accelerators.
- Further releases of search-native and continued-fraction pre-training checkpoints.
- Expanded multilingual OCR and translation model families beyond the current 102-language coverage.
- Additional agent-failure diagnosis frameworks that close the loop from detection to automatic test generation.
