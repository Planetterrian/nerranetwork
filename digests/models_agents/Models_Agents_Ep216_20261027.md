# Models & Agents
> **OpenAI’s GPT-6.1 Terra delivers faster computer-use agents at half the prior token price.**

**What You Need to Know:** OpenAI began rolling out GPT-6.1 Terra to ChatGPT Work, Codex, and the API as gpt-6.1-terra, with 50% lower standard API prices than GPT-5.6 Terra and strong results on agent benchmarks. The model handles screen understanding, cross-app actions, and natural writing while finishing tasks over 3× faster than GPT-6 Astra on average. Builders should test it first for agentic workflows where cost and speed matter more than maximum capability.
---
### Top Story
OpenAI released GPT-6.1 Terra, a new model optimized for fast, capable computer use at lower cost. It understands screen content, performs actions across applications, and writes naturally while matching GPT-6 Astra performance on Agents’ Last Exam at one-tenth the price per token. The model finishes tasks over three times faster on average than both Astra and GPT-6.1 Sol. In ChatGPT Work and Codex the usage allowance stretches further than with GPT-5.6 Terra. Developers can access it immediately through the API or ChatGPT interfaces for agent-style work. Watch for continued price and speed improvements across the GPT-6.1 family as OpenAI pushes the cost-intelligence frontier. Source: [openai.com](https://openai.com/index/introducing-gpt-6-1-terra/)
---
### Model Updates
**OpenESM: Energy-Steered Models Are Scalable Foundation Learners: arXiv NLP**
OpenESM integrates energy steering and token generation in one architecture that first optimizes a latent state over an energy landscape before using the refined state for generation. The models were pre-trained on three large-scale corpora and evaluated on 26 downstream tasks, where they show promising scaling behavior and outperform GPTs on most tasks. The team fully releases model weights and training infrastructure on GitHub and Hugging Face. Source: [arxiv.org](https://arxiv.org/abs/2610.33005)

**Linear-Time Context Compression with State-Space Encoding: arXiv NLP**
The Boa Compressor uses a Mamba state-space model to encode arbitrary-length context in a single linear-time pass and produces a representation that conditions a frozen target LLM. At equal compression ratios it matches or exceeds existing offline Transformer-based baselines while running an order of magnitude faster. The method scales to 16× compression and longer contexts without adding per-query overhead. Source: [arxiv.org](https://arxiv.org/abs/2610.33006)

**Conceptizer: Next-Token Prediction Is Not All You Need: arXiv NLP**
Conceptizer adds a fixed ~9K-concept vocabulary of contextual synonyms to next-token training so the model receives a reward for meaning rather than only the exact next token. Applied to 1B–8B models across three families, it achieves the lowest held-out perplexity at concept-target positions and the highest probability on contextual synonyms. Downstream gains appear on knowledge and sentiment tasks while commonsense performance stays comparable. Source: [arxiv.org](https://arxiv.org/abs/2610.33027)

**Merge-Based Vocabulary Extension Stalls at the Pre-Tokenizer: An English-Preserving Repair for Nepali, Tested in Continued Pretraining: arXiv NLP**
A small regex edit to the pre-tokenizer keeps every token ID of text without combining marks or Devanagari characters and, with 32,000 new merges, reduces Nepali token count to 1.01 times English. The repair cuts Nepali tokens by about 54% versus standard vocabulary extension on Llama-3 and Qwen3. Continued pretraining experiments on Llama-3.2-1B and Qwen3-0.6B show the original tokenizer still wins on held-out Nepali bits per byte under every tested recipe. Source: [arxiv.org](https://arxiv.org/abs/2610.33016)

**AdaptTok-Indic: Script-Aware Adaptive Tokenization for Indic Languages: arXiv NLP**
AdaptTok-Indic combines Unicode-normalized preprocessing, explicit Indic conjunct handling, script-aware routing, and learned byte-level boundary prediction. On Bengali and Hindi it records mean fertility of 1.432 and 1.388 respectively, well below SentencePiece BPE. Downstream scores average 57.69 on evaluated Indic settings versus 50.82 for the SentencePiece baseline. Source: [arxiv.org](https://arxiv.org/abs/2610.33017)
---
### Agent & Tool Developments
**Recursive Semantic Divergence for LLM Agent Consistency: arXiv NLP**
Recursive Semantic Divergence measures expected cumulative semantic disagreement between independent rollouts of the same agent from the same state using natural language inference. When used as a reward signal it reduces task-progress variation from 132% to 91% on tau2-bench and from 90% to 44% on toolsandbox while improving performance across benchmarks and scales. The metric requires no ground-truth labels and estimates future divergence from the current state. Source: [arxiv.org](https://arxiv.org/abs/2610.33012)

**SLICE-Mem: Salience-Gated Lightweight Information Curation for Efficient LLM Agent Memory: arXiv NLP**
SLICE-Mem uses a compact classifier for salience-guided admission and a semantic-dependency extractor that converts turns into concise memory entries without generative LLM calls. On Memora Weekly and LongMemEval-S with Qwen3-30B backbones it matches the generative baseline MemOS while cutting total LLM token consumption by 92.4% and 99.5% respectively. Cross-entry reconciliation is deferred to an offline stage. Source: [arxiv.org](https://arxiv.org/abs/2610.33015)

**FlexA-Mem: Budget-Adaptive Agentic Memory for LLM Agents: arXiv NLP**
FlexA-Mem writes each unit of history once into an immutable store and renders a fresh compact timeline plus detail for every call using a fixed rule that fits remaining budget without an LLM call. On AppWorld at 4k context it outperforms the second-best method by 11.5% and on 147 unused tasks it beats A-Mem with summary by 12.2%. The timeline carries completion while recovery mainly saves steps. Source: [arxiv.org](https://arxiv.org/abs/2610.33274)

**TraceQuery: learning what to recompute from full-denoising trajectory in diffusion language models: arXiv NLP**
TraceQuery predicts a small set of near-future trajectory-relevant positions from full-denoising trajectories and queries only those candidates. It delivers the strongest quality-computation trade-off among cache-based approaches for diffusion LLMs while generalizing across tasks, model variants, and families. Code is released on GitHub. Source: [arxiv.org](https://arxiv.org/abs/2610.33008)
---
### Practical & Community
**Entity-Aware Evaluation of OCR Systems for Historical Document Transcription: arXiv NLP**
The work introduces entity-level analysis of OCR errors on a 175-document benchmark from the Berrutti Archive containing 5,209 manually annotated entity mentions. Qwen 3.6 achieves the highest entity coverage across tolerances while several lower exact-match systems recover substantially when small character errors are tolerated. The benchmark and annotations will be released upon acceptance. Source: [arxiv.org](https://arxiv.org/abs/2610.33004)

**Whispering Wisely: Smart Subset Selection for ASR Fine-Tuning: arXiv NLP**
An embedding-based k-center subset selection method using Whisper’s pretrained encoder selects diverse training subsets for ASR fine-tuning. On Hebrew and Danish the approach often beats random sampling, especially at smaller subset sizes, and k-center subsets capture broader lexical diversity. The method provides a practical way to adapt Whisper to new languages or domains with limited transcribed audio. Source: [arxiv.org](https://arxiv.org/abs/2610.32997)

**A Benchmark for Controllable Speaking-Style Captioning in Audio-Language Models: arXiv NLP**
StyleInstructCaps supplies the first standardized benchmark and evaluation framework for instruction-following speaking-style captioning that measures metadata groundedness, hallucination, instruction following, and speaker-style consistency. Across nine state-of-the-art audio-language models, instruction-diverse training substantially improves groundedness and controllability. Source: [arxiv.org](https://arxiv.org/abs/2610.33036)

**EviGround-CT: Sentence-to-Volume Grounding for Verifying LLM-Generated Chest CT Reports: arXiv NLP**
EviGround-CT extracts positive finding sentences from LLM-generated CT reports and uses a 3D grounding model to predict evidence masks for each sentence. Sentence-grounded verification raises evidence-supported precision from 0.263 to 0.365 on a held-out 100-case subset while lowering the unsupported positive finding rate from 0.737 to 0.635. Source: [arxiv.org](https://arxiv.org/abs/2610.33038)
---
### Also Today
**AI agents could transform banking, but risks remain, say industry experts: Business Standard**
Industry experts note that AI agents could transform banking operations while highlighting remaining risks around security, compliance, and oversight. Source: [business-standard.com](https://www.business-standard.com/industry/banking/ai-agents-could-transform-banking-but-risks-remain-say-industry-experts-126102700782_1.html)

**Analysis | How to get started using AI agents even if you never imagined it: The Washington Post**
The piece walks through practical first steps for individuals and teams beginning to experiment with AI agents. Source: [washingtonpost.com](https://www.washingtonpost.com/technology/2026/10/27/how-get-started-using-ai-agents-even-if-you-never-imagined-it/)

**Insights: What agentic AI means for the future of oil and gas operations: Oil & Gas Journal**
The discussion explores how agentic AI can connect workflows and accelerate decisions in oil and gas operations. Source: [ogj.com](https://www.ogj.com/general-interest/podcast/55414447/insights-moving-beyond-copilots-as-agentic-ai-connects-workflows-accelerates-decisions)

**Anthropic Files S-1 Registration Statement for Proposed IPO: [@AnthropicAI](https://x.com/AnthropicAI)**
Anthropic filed an S-1 registration statement with the SEC for its proposed IPO. Source: [anthropic.com](https://www.anthropic.com/news/s1-sec)

**GPT-6.1 Sol helps CodeRabbit strengthen security across complex codebases: OpenAI Blog**
CodeRabbit uses GPT-6.1 Sol to investigate security risks across complex codebases and review proposed fixes. Source: [openai.com](https://openai.com/index/gpt-6-1-sol-coderabbit-code-security)

**Greptile takes bug detection beyond code review with GPT-6 Astra: OpenAI Blog**
Greptile uses GPT-6 Astra to test user workflows, strengthen security, and reduce rework inside Codex. Source: [openai.com](https://openai.com/index/greptile-code-review-codex-astra)

**ChatGPT’s expanding world of work: OpenAI Blog**
OpenAI Signals data covers 165 work activities across nearly 100 countries and shows how ChatGPT usage for work evolves over time. Source: [openai.com](https://openai.com/index/chatgpt-expanding-world-of-work)
---
### Under the Hood: Linear-Time Context Compression with State-Space Encoding
The Boa Compressor replaces the usual Transformer backbone for soft-prompt compression with a Mamba state-space model that encodes context in one linear-time pass. The SSM is trained by distillation so its compressed representation produces the same next-token logits as the target LLM ingesting the full context. Because the compressor runs online on every query instead of once offline, it removes the latency overhead that previously confined soft-prompt methods to repeated-query settings. At identical compression ratios the approach matches or exceeds prior offline baselines while cutting compression time by roughly an order of magnitude. It continues to scale to 16× ratios and longer contexts without the quadratic cost that grows with Transformer-based compressors. The practical limit appears when the target LLM’s own context window becomes the bottleneck rather than the compressor itself. Teams facing repeated long-context queries should test Boa first; teams that compress once and reuse across many queries can still prefer the older offline methods.
---
### Things to Try This Week
- Test GPT-6.1 Terra through the OpenAI API or ChatGPT Work for agentic computer-use tasks where speed and token cost dominate.
- Experiment with the released OpenESM weights on Hugging Face for energy-steered pre-training on your own corpora.
- Try the Boa Compressor implementation on long-context workloads to measure end-to-end latency versus your current offline compression pipeline.
- Apply the k-center subset selection method from the Whisper paper when fine-tuning ASR models on Hebrew or Danish data with limited transcribed audio.
- Evaluate AdaptTok-Indic on Bengali or Hindi text if you need lower token fertility than standard SentencePiece BPE.
---
### On the Horizon
- Anthropic’s proposed IPO filing moves the company closer to public-market scrutiny of its frontier-model roadmap.
- Continued GPT-6.1 family releases are expected to push further on the cost-intelligence curve for agent workloads.
- More labs are likely to release similar online context-compression tools built on state-space models following the Boa results.
- Additional entity-aware OCR benchmarks for historical documents are anticipated once the Berrutti Archive annotations are public.
