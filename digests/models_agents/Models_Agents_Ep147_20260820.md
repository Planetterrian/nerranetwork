> **# Models & Agents**
OpenAI is testing private safety processing that keeps frontier-model interactions off-limits to staff while still catching risks across long agent sessions.

**What You Need to Know:** OpenAI previewed Private Safety Processing for frontier models to improve safety without personnel seeing raw content. Simon Willison documented an untrusted-sandbox experiment where Claude Code triggered an autonomous GitHub Actions push. New benchmarks and tokenization work on smaller models plus practical inference tuning on llama.cpp round out the day’s concrete releases.
---
### Top Story
OpenAI previewed Private Safety Processing for frontier models. The system is designed to flag risks across related interactions in longer autonomous workflows without giving OpenAI staff access to the underlying content. It sits alongside the company’s continued Zero Data Retention offering. Builders working with extended agent sessions now have an explicit path to stronger safety controls that do not require sharing raw data. The preview directly addresses the scaling challenge of monitoring multi-turn tool use and memory-heavy conversations. Watch for how the feature integrates with existing API workflows and whether other labs adopt similar private-review patterns. Source: [x.com](https://x.com/OpenAI/status/2090165328290701800)
---
### Model Updates
**NE-BERT: A Multilingual Language Model for Nine Northeast Indian Languages — arXiv NLP**
NE-BERT is a domain-specific encoder trained on 8.3 million sentences across nine Northeast Indian languages plus Hindi and English. It uses weighted sampling and a custom SentencePiece Unigram tokenizer, delivering 15.97× lower average perplexity than IndicBERT-V2 and 7.64× lower than MuRIL. The model improves tokenization fertility 1.50× over mBERT and shows downstream gains on part-of-speech tagging for three of the languages. Researchers released the model, test sets, and corpus under CC-BY-4.0. Teams working on low-resource Indic languages should test it this week for both perplexity and tagging tasks. Source: [arxiv.org](https://arxiv.org/abs/2608.18094)

**SuTRA: Structurally-Unified Tokenization with Root Awareness — arXiv NLP**
SuTRA is a morphology-aware tokenizer that preserves akshara indivisibility and penalizes merges across morphological boundaries for Hindi, Marathi, and Gujarati. It reduces morphological shattering and records peak gains of +14.7% Boundary F1 and +34% semantic recoverability on Hindi over standard BPE. The method delivers an average +8.08 chrF2 improvement in machine translation. The team also released a new morphological segmentation dataset for the three languages. Developers building Indic MT or retrieval systems should evaluate SuTRA tokenizers against their current BPE baselines.

**LongNovel: A Multi-Scale Benchmark for Hallucination Detection in Long-Context Novel Summarization — arXiv NLP**
LongNovel provides a bilingual (Chinese/English) benchmark built from 29 Chinese novels (16k–100k tokens) and BookSum chapter data. It defines eight hallucination types and uses multi-model arbitration plus entity-referenced generation to create balanced test cases, followed by manual revision. The benchmark is explicitly designed to study how hallucinations scale with context length in narrative settings. Researchers released the dataset and evaluation code. Summarization teams should add LongNovel to their long-context hallucination test suites.

**Nine Emotion Centroids: A Label-Free Valence Axis That Transfers Across Four Modalities — arXiv NLP**
The work extracts a single valence direction from nine emotion category names plus 50 short paragraphs per emotion. The resulting axis captures 93% of supervised performance on SST-2 and transfers to vision, audio, and brain recordings without target-modality labels. A 2-parameter classifier trained only on text reaches AUC 0.961 on images and 0.828 on brain data. The method is bounded to continuous attributes and does not work on categorical concepts. Researchers working on cross-modal affect or lightweight steering should test the nine-centroid recipe on their own encoders.
---
### Agent & Tool Developments
**Persona-Guided LLM Agents for Task-Oriented Dialogue — arXiv NLP**
The framework runs two LLMs in a training-free loop: a user agent expressing a target Big-Five personality and a system agent that adapts while completing hotel or restaurant tasks from the SGD dataset. Oracle personality knowledge improves constraint satisfaction and user satisfaction but reduces truthfulness; cue-based inference (Try condition) offers the best reliability–performance tradeoff. The study evaluates GPT-4o, Qwen3-Next-80B, and Gemini 2.0 Flash across all trait poles. Teams building personalized customer-service agents should examine the three knowledge conditions and the observed truthfulness cost.

**StocksTalk: A Voice-Enabled Conversational Agent for Structured Query Generation over Web Data — arXiv NLP**
StocksTalk converts spoken financial screening requests into validated SQL using streaming ASR, retrieval-augmented constraint extraction, schema-grounded generation, and rule-based validation inside an interactive dashboard. A 150-prompt benchmark shows retrieval grounding and human-in-the-loop verification raise constraint accuracy, SQL executability, and multi-turn stability over plain LLM baselines. The system surfaces intermediate artifacts so users can inspect and edit each stage. Developers building voice-driven analytics tools should review the constraint-extraction and verification pipeline.

**Notes and research report on smolmachines-untrusted-sandbox — Simon Willison**
Simon Willison released notes and a GitHub research repo on running untrusted code in a smolvm sandbox. The setup was used to test Claude Code in a restricted environment that lacks /dev/kvm. The work provides concrete configuration details for builders who need isolated execution for agent tool calls. Practitioners experimenting with code-execution agents should examine the sandbox constraints and logging approach described in the report. Source: [simonwillison.net](https://simonwillison.net/2026/Aug/19/smolmachines-untrusted-sandbox/)
---
### Practical & Community
**3 days benchmarking most llama.cpp flags on my weird 40gb vram laptop + tb4 egpu setup — r/LocalLLaMA**
A detailed three-day benchmark on a 4090 laptop plus 7900 XTX eGPU over Thunderbolt 4 reached 27 t/s generation and full 262k context on Qwen3.8-27B Q6_K_XL after tuning MTP, ngram, KV cache type, and layer split. The author filed an upstream issue on multi-GPU MTP prefill penalties and published the LLM-Tuner repo used for the experiments. The post includes concrete flag combinations and device-specific tradeoffs. Anyone running llama.cpp on mixed NVIDIA/AMD or eGPU setups should review the final command and the MTP bug report. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1vtc0z7/3_days_benchmarking_most_llamacpp_flags_on_my/)

**Google is giving 1-year Gemini AI plans free for students — The Indian Express**
Google is offering eligible students a full year of Gemini AI access at no cost. The program targets higher-education users and provides the same model capabilities available to paid subscribers. Students and educators should check eligibility and claim the plan before the offer window closes. Source: [indianexpress.com](https://indianexpress.com/article/technology/artificial-intelligence/google-is-giving-1-year-gemini-ai-plans-free-for-students-10841466/)

**Fractional Decay KV-Cache: Ownership-Aware Memory Management for Improved Inference Relevancy in Dialog Systems — arXiv NLP**
FD-KVC maintains dual scoring channels per KV pair—cumulative attention and recency-weighted relevance with temporal decay—and uses an ownership loss to drive adaptive learning rates. Across 600-dialog test sets it outperforms H2O by 6.7% on late-turn alignment and adapts to topic shifts 3.6× faster while running entirely on CPU. The method preserves historical tokens while rapidly deprioritizing stale context. Dialog-system teams should test the dual-channel scoring approach against standard H2O eviction.
---
### Under the Hood: KV-Cache Eviction Under Topic Drift
Everyone treats KV-cache eviction as a simple “keep the most attended tokens” rule. In practice the decision surface changes as soon as the conversation topic shifts, because attention mass from earlier turns stops predicting future utility. The core insight is that importance is not stationary: a token that was heavily attended during the first topic can become irrelevant noise once the user changes subject. Dual-channel scoring separates aggregate attention from a recency-weighted relevance signal that decays unless reinforced by new matches. Adding an ownership loss term prevents the eviction policy from oscillating when the same entities reappear later in the dialogue. The practical tradeoff is modest CPU overhead for the extra scoring pass versus measurable gains in late-turn alignment and faster recovery after topic changes. Teams running long multi-turn agents should prefer dual-channel or ownership-aware eviction once context exceeds roughly 50k tokens; single-signal LRU or H2O remains adequate for shorter, single-topic sessions.
---
### Things to Try This Week
- Test NE-BERT on any Northeast Indian language tagging or retrieval task; the released weights and corpus make it a drop-in low-resource baseline.
- Run the SuTRA tokenizer against your current BPE pipeline on Hindi or Gujarati MT data to measure the reported chrF2 lift.
- Add LongNovel to your long-context summarization eval harness to surface hallucination patterns that news or paper benchmarks miss.
- Try the final llama.cpp flag set from the 40 GB mixed-GPU benchmark on your own Qwen3.8-27B workload and watch for the MTP prefill interaction.
- Prototype a dual-channel KV eviction policy in your dialog agent using the FD-KVC description as a starting point.
---
### On the Horizon
- Further details expected on OpenAI’s Private Safety Processing rollout and integration surface.
- Additional low-resource Indic model releases are already signaled in the NE-BERT and SuTRA papers.
- More llama.cpp multi-GPU and MTP fixes are likely after the filed issue receives community attention.
- Expanded student and education access programs from other frontier labs remain possible following Google’s move.