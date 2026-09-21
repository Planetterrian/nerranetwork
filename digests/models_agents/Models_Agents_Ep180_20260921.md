# Models & Agents
> **Korea-led AI agent tops human rivals at APEX 2026, proving agent systems can now outperform experts on complex tasks.**

**What You Need to Know:** Stealien, a Korea-led team, won the APEX 2026 competition with an autonomous AI agent that outperformed human teams. Several new arXiv papers detail practical advances in small-model uncertainty handling, clinical knowledge graphs, and multilingual benchmarks. US and China officials discussed exchanging AI safety alerts ahead of a summit. Builders should watch how semantic-entropy routing and schema-guided evaluation move from research into deployable tools this week.
---
### Top Story
Stealien AI agent tops APEX 2026 as Korea-led team outperforms human rivals. The agent secured first place in the competition by completing tasks that human teams could not match. The win highlights rapid progress in autonomous agent reliability on multi-step professional workflows. Teams working on agent orchestration can now benchmark against a documented Korea-led system that beat human baselines. Watch for follow-up technical reports on the agent's architecture and failure modes. Source: [biz.chosun.com](https://biz.chosun.com/en/en-it/2026/09/21/SIPOPA64YFEZLHMYTGTEUGJQQI/)
---
### Model Updates
**Do small language models know what they don't know?: arXiv NLP**
Token-level entropy proved near zero in 91 percent of dataset-model combinations for models under 3 billion parameters, making it unusable for confidence signals. Semantic entropy, computed by sampling multiple answers, clustering by meaning, and measuring distributional uncertainty, restored a usable signal. Routing uncertain queries to a larger expert model via semantic entropy delivered accuracy gains up to 50 percentage points, with cross-family routing averaging 22 percent improvement. The study evaluated seven distinct approaches across 7 model pairs and 5 standard NLU benchmarks. Token-level entropy early stopping and semantic entropy estimation were among the methods tested on consumer hardware. Source: [arxiv.org](https://arxiv.org/abs/2609.20824)

**From Discharge Notes to Patient Understanding: Persona-Grounded, Open-Ended Simulation of LLMs as Discharge Educators: arXiv NLP**
DischargeBench introduces 477 persona-grounded cases across 24 ICD chapters with axes for personality, education level, health literacy, and recall. An Education Monitor Agent maintains patient realism during multi-turn sessions while an LLM-as-a-Judge scores Conversation Quality, Topic Checklist, Comprehension, and Factual Consistency. Aggregate scores masked clinically relevant variation across chapters and personas, exposing coverage failures on difficult cases. The benchmark uses MIMIC-IV-Ext-DischargeBench and aligns the judge against physician annotations. Source: [arxiv.org](https://arxiv.org/abs/2609.20827)

**Beyond WER: Entity and Disfluency Recall in Accented Conversational ASR: arXiv NLP**
A three-stage pipeline using SQL curation, regional LoRA adapters on Qwen2.5-Omni-3B, and a six-category LLM judge taxonomy raised entity recall from 53-55 percent to 80-85 percent and filler recall from under 5 percent to 76-86 percent while holding WER at 6-10 percent. Curation alone contributed 2.8 to 4.2 percentage points of the entity-recall gain. The system outperformed Whisper and a commercial ASR on entity recall while matching a zero-shot 30B model at one-tenth the size. The pipeline was tested on 6k utterances from speakers in India, Indonesia, and Latin America. Source: [arxiv.org](https://arxiv.org/abs/2609.20828)

**SAGE: Schema-Guided LLMs for Grant Review: arXiv NLP**
SAGE translates grant rubrics into structured checks and links judgments to evidence in application packages. On 35 nonprofit applications it reached kappa of 0.58 after expert inspection, outperforming a one-prompt-per-criterion baseline at kappa 0.33. A claim-level audit identified confirmed, disputed, and unaddressed parts of the draft. The system was evaluated in two stages against 105 original competition reviews and produced 202 assessments in the assisted round. Source: [arxiv.org](https://arxiv.org/abs/2609.20829)

**Reviser: Revision-Capable Text Generation via Autoregressive Cursor Actions: arXiv NLP**
Reviser predicts single action tokens—INSERT, MOVE, or STOP—on a mutable canvas, enabling non-monotonic generation. On a continuation benchmark it was strongly preferred to SEDD and MDLM in arena evaluations while using substantially less inference compute than multi-pass refinement baselines at both 100M and 300M scales. The model performs frequent backward moves and mid-canvas insertions rather than end-append decoding. Source: [arxiv.org](https://arxiv.org/abs/2609.20830)
---
### Agent & Tool Developments
**Catena Trust Bank Secures Preliminary OCC Approval for AI-Agent Financial Infrastructure: forkast.news**
Catena Trust Bank received preliminary approval from the Office of the Comptroller of the Currency to build AI-agent financial infrastructure. The approval covers agent-driven operations in banking workflows. Regulated financial institutions now have a documented path for deploying autonomous agents under federal oversight. Source: [forkast.news](https://forkast.news/catena-trust-bank-secures-preliminary-occ-approval-for-ai-agent-financial-infrastructure/)

**Autonomous AI Agents Cause Widespread Digital Disruptions Across Platforms: SuaraGarut.ID**
Autonomous agents triggered disruptions across multiple online platforms through unintended actions. The incidents highlight reliability gaps when agents operate without sufficient sandboxing. Platform operators are examining containment strategies for long-running agent sessions. Source: [suaragarut.id](https://suaragarut.id/en/ai-agents-cause-digital-disruptions)

**US and China discuss AI safety plan ahead of Trump-Xi summit: BBC**
US and Chinese officials discussed a framework for exchanging AI safety alerts before the upcoming summit. The proposal includes mutual notification of safety incidents and evaluation findings. The talks mark a concrete step toward bilateral safety coordination. Source: [bbc.com](https://www.bbc.com/news/articles/c8vgyzn2d31yo)

**U.S. proposes exchanging AI safety alerts with China, Bessent says: NBC News**
Treasury Secretary Bessent stated the US proposed direct exchange of AI safety alerts with China. The mechanism would allow rapid sharing of identified risks and mitigation approaches. Implementation details remain under discussion. Source: [nbcnews.com](https://www.nbcnews.com/world/asia/us-proposes-exchanging-ai-safety-alerts-china-bessent-says-rcna598923)
---
### Practical & Community
**TatBLiMP: A Benchmark of Linguistic Minimal Pairs for Tatar: arXiv NLP**
TatBLiMP provides 1248 sentence pairs covering 16 morphosyntactic phenomena for the Tatar language, the first such grammaticality benchmark for the language. A 478M from-scratch model and a 125M monolingual model reached near 0.97 accuracy, while frontier 30-120B models scored 0.80-0.92. The benchmark runs on base models and mid-training checkpoints without requiring generation or parsing. It adapts TurBLiMP operations and adds one Tatar-specific phenomenon on bare-noun number after numerals. Source: [arxiv.org](https://arxiv.org/abs/2609.20832)

**Transsion's Speaker-Attributed Multilingual ASR System for the MLC-SLM 2026 Challenge: arXiv NLP**
Transsion's cascaded system combining DiariZen diarization, Qwen3-Omni ASR, and timestamp fusion achieved 15.41 percent tcpMER and placed second in the challenge. The pipeline produces speaker-attributed STM outputs for multilingual conversational speech. The diarization module uses local speaker activity estimation and global clustering. Source: [arxiv.org](https://arxiv.org/abs/2609.20833)

**PhysioBench: A Unified Benchmark for Physiological Signal Question Answering: arXiv NLP**
PhysioBench harmonizes 22 public datasets into 61.4 million questions across 30 tasks for physiological signal understanding. None of the 21 evaluated models, including large language, vision-language, and physiological foundation models, achieved consistently strong performance across modalities. The benchmark supplies traceable question-answer pairs grounded in signal segments. Source: [arxiv.org](https://arxiv.org/abs/2609.20836)

**μ²-Bench: A Multilingual Machine Unlearning Benchmark: arXiv NLP**
μ²-Bench simulates the full memorization-unlearning-evaluation pipeline across multiple languages and evaluates both training and hold-out languages. Successful multilingual unlearning requires methods that explicitly account for cross-lingual knowledge dispersion. Source: [arxiv.org](https://arxiv.org/abs/2609.20945)
---
### Under the Hood: Semantic Entropy Estimation in Small Language Models
Semantic entropy recovers usable confidence signals in models under three billion parameters where token-level entropy collapses to near zero. The method generates multiple samples, clusters them by meaning, and measures distributional uncertainty across clusters rather than individual tokens. This approach adds sampling overhead but enables selective routing that improves accuracy by up to fifty points when uncertain queries are handed to a larger expert. Cross-family routing from a 360M model to Phi-3.5-mini averaged twenty-two percent gains, showing that expert quality matters more than architectural match. The technique therefore functions as an intelligent compute allocator rather than a pure efficiency play. Teams should apply semantic entropy routing when operating small models on consumer hardware and when downstream accuracy justifies the extra samples; skip it when every query must run at minimal latency.
---
### Things to Try This Week
- Run semantic entropy sampling on SmolLM or similar sub-3B models and route uncertain queries to a larger expert to measure accuracy lift on your NLU tasks.
- Test TatBLiMP on any Tatar-capable base model or checkpoint to track focused language training progress.
- Evaluate your current discharge-education prompts against DischargeBench personas to surface coverage gaps across ICD chapters.
---
### On the Horizon
- Further details expected from the US-China AI safety alert exchange discussions.
- Additional results from the MLC-SLM 2026 challenge participants.
- New multilingual unlearning evaluations using μ²-Bench.
