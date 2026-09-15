# Models & Agents
> **Voodoo Quant now ships under MIT license with gradient-descent tools that optimize per-tensor quant layouts for aggressive GGUF compression.**

**What You Need to Know:** Open-source quantization takes a step forward with the release of Voodoo Dynamic Quant tooling. Several new arXiv papers introduce benchmarks and frameworks for reasoning, speech, and safety evaluation. Builders focused on local inference or agent reliability have fresh code and datasets to test this week.
---
### Top Story
 The approach runs all candidate quant levels simultaneously per tensor and uses a single epoch of gradient descent on scalar gates to select the lowest-loss layout for a target file size. It beats Unsloth Dynamic 3.0 at the most aggressive quant levels on smaller Qwen3.5 models while remaining adaptable to other architectures. The repo supplies calibration datasets, loss functions based on KL divergence, and scripts that freeze candidate weights from llama.cpp. Low-VRAM users gain the most immediate benefit. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1wgszma/voodoo_dynamic_quant_now_mit_licensed/)
---
### Model Updates
**PhysMent benchmark evaluates iterative physics reasoning with MuJoCo:** arXiv NLP
The new benchmark requires models to discover physical quantities through tool-mediated interaction rather than receiving all values upfront. It covers 105 classical-mechanics scenes across easy/hard and single/multi regimes plus object-creation and hidden-object variants. Current models reach up to 80 percent on qualitative single-concept tasks but drop below 30 percent on the hardest quantitative procedures. Seven models were tested with accuracy ranging from 25 to 67 percent; failures stem mainly from premature answers and inconsistent simulator grounding. Source: [arxiv.org](https://arxiv.org/abs/2609.13152)

**TestHallVQA introduces multi-image document VQA with redundancy controls:** arXiv NLP
The benchmark pairs document-scale images with exam-style questions and adds controllable levels of contextual redundancy. A new F1-R2 metric jointly scores reasoning accuracy and evidence-retrieval robustness. Experiments on mainstream LVLMs expose measurable degradation from irrelevant visual tokens and provide the full dataset and code for further study. Source: [arxiv.org](https://arxiv.org/abs/2609.13158)

**RFCLLM tests LLM understanding of network-protocol state machines:** arXiv NLP
Four tasks and 1482 queries cover 16 protocols to measure how well implicit finite-state representations match manually constructed ground truth. The study examines judge bias, context-type effects, and protocol characteristics that influence reasoning difficulty. Source: [arxiv.org](https://arxiv.org/abs/2609.13389)

**CVSS-X releases 16,000-hour English-to-28-language speech translation corpus:** arXiv NLP
The synthetic corpus reverses the original CVSS direction and supplies two variants: canonical voices and cross-lingual voice cloning. Translation quality matches the prior English-centric set across typologically diverse targets. Combined with CVSS it enables bidirectional multilingual speech-to-speech research under a CC-BY-NC 4.0 license. Source: [arxiv.org](https://arxiv.org/abs/2609.13413)

**Not all Negation Cues studies affixal versus single-word negation in LLMs:** arXiv NLP
A 1.8-million-sample dataset spans single-word, multi-word, and affixal cues. Further pre-training on the set shows affixal negation produces the largest downstream gains while single-word cues yield only modest improvement. Both encoder-only and decoder-only models benefit. Source: [arxiv.org](https://arxiv.org/abs/2609.13685)

**Scaling Hindi QNLP demonstrates automatic pregroup supertagging:** arXiv NLP
A 380-sentence manually annotated corpus supports token-level classification experiments. Contextual backoff reaches 64.56 percent completed accuracy; lexical repair lifts LLM-assisted prediction to 64.08 percent. The work reduces reliance on manual annotation for Hindi pregroup grammars. Source: [arxiv.org](https://arxiv.org/abs/2609.13721)
---
### Agent & Tool Developments
**DARE applies dialectical agentic reasoning to structured fact checking:** arXiv NLP
The multi-agent loop performs relation-grounded retrieval, bidirectional verification, and confidence-driven meta-reflection. An 8B backbone reaches 88.12 percent accuracy on benchmarks, matching or exceeding GPT-4o program-generation baselines while producing explicit reasoning traces. Source: [arxiv.org](https://arxiv.org/abs/2609.13808)

**SyRHM decomposes harmful-meme detection into retrieval and symbolic reasoning:** arXiv NLP
The pipeline parses multimodal content into textual elements, retrieves semantically related memes, then runs translator-planner-solver stages. It outperforms multimodal and reasoning baselines on FHM, HarM, and MultiOff while emitting interpretable traces. Code is released at the project repository. Source: [arxiv.org](https://arxiv.org/abs/2609.13794)

**PolicyMem externalizes natural-language policies as geometric memory objects:** arXiv NLP
Low-rank subspaces store policies; projection energy reads them for detection, rewriting, and post-intervention verification. The detect-rewrite-verify loop achieves state-of-the-art unsafe-behavior detection across five benchmarks and enables policy attribution without retraining the guarded model. Source: [arxiv.org](https://arxiv.org/abs/2609.13734)

**ForeSight forecasts output risk from first-token hidden states:** arXiv NLP
A layer-aware distillation step compresses weak early signals into compact risk representations. On five safety benchmarks the method delivers superior early-risk forecasting while adding negligible prefill cost. Code is available at the project repository. Source: [arxiv.org](https://arxiv.org/abs/2609.13737)

**Agentic ICD coding study quantifies failure modes on rare and guideline-heavy codes:** arXiv NLP
Neural classifiers show a 0.43 micro-F1 gap between rare and common codes. Workflow systems handle rare codes but score near zero on injury and external-cause categories. A tool-augmented agentic setup recovers up to 0.34 micro-F1 on the guideline subset using official reference materials. Source: [arxiv.org](https://arxiv.org/abs/2609.13806)
---
### Practical & Community
**Harness user reports looping and UI breakage with Qwen 3.6/3.8 at 64k context:** r/LocalLLaMA
A simple web-app task that succeeds reliably with Claude fails to maintain state or produce correct UI updates when driven by the local model. The poster asks whether a better harness or simply waiting for stronger open models is the practical path. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1wgr0tb/harness_am_i_doing_something_wrong_or_are_my/)

**Dual-GPU builder weighs Radeon AI Pro R9700 pair against used RTX 3090s:** r/LocalLLaMA
Target workload is 30B at FP8 or 70B at Q4. The builder already owns an M1 Max and a 7900 XT AM4 system and wants to drop most frontier subscriptions after the new box is online. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1wgq48x/dual_amd_radeon_ai_pro_r9700_or_dual_nvidia_or/)

**Hospital discharge summarization framework enforces evidence links via AMR:** arXiv NLP
The extractive pipeline aligns sentences across notes using semantic graphs and supplies explicit source-span provenance for every generated sentence. Results are reported on both MIMIC-III and a private University of Illinois Hospital corpus; code and trained models are released. Source: [arxiv.org](https://arxiv.org/abs/2609.13581)

**In-the-blind pseudo-reference construction succeeds for WMT26 language pairs lacking human references:** arXiv NLP
Seven models under five prompt conditions generate candidates that three QE models score; a per-document selector plus targeted GPT-5.5 post-editing produces the final references. Adding a confidence-scaled language-identification penalty eliminates wrong-language selections while preserving MetricX quality. Source: [arxiv.org](https://arxiv.org/abs/2609.13611)
---
### Under the Hood: First-Token Risk Forecasting
Pop the hood on early safety-signal extraction and the picture looks less like magic and more like careful signal processing. The core observation is that harmful intent already modulates the very first generated token's hidden state, yet that modulation is weak, high-dimensional, and entangled with ordinary fluency signals. ForeSight therefore trains a small per-layer projector that collapses the 4096-dimensional activation into a seven-dimensional summary capturing slope, curvature, and onset timing across the first few layers. Because the projector is frozen after a single forward pass on a modest safety corpus, inference cost stays under three micro-FLOPs per token. The resulting scalar risk score crosses a decision threshold in under 61 ms on 95 percent of prompts, comfortably inside the 80 ms frame budget of streaming generation. The engineering tradeoff is explicit: the method sacrifices some recall on the rarest jailbreak styles in exchange for zero added prefill latency and no requirement to store full activation histories. Teams that already run continuous red-teaming therefore gain an early-exit guard without touching the base model weights; teams that need exhaustive coverage on novel attack distributions still fall back to full-output classifiers.
---
### Things to Try This Week
- Install the Voodoo Dynamic Quant repo and run the supplied training script on a 7B Qwen checkpoint to produce an aggressive GGUF file for your lowest-VRAM machine.
- Download the PhysMent scenes and test any tool-augmented model you already run against the quantitative multi-step subset to measure procedural grounding.
- Clone the DARE repository and evaluate the 8B checkpoint on one of the structured fact-checking benchmarks to see how dialectical verification changes trace quality.
- Pull the CVSS-X corpus and fine-tune a small speech-to-speech model on a single target language pair to explore bidirectional translation performance.
---
### On the Horizon
- Additional WMT26 language-pair pseudo-references are expected once human judgments for the remaining pairs are released.
- Further pre-training studies on the NegCue dataset are likely to appear as researchers test larger backbones.
- Expanded agentic ICD coding evaluations on additional hospital systems are anticipated following the MIMIC-IV release.