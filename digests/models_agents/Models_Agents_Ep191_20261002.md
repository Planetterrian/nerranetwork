# Models & Agents
> **LLMs map land versus water from pure text latitude-longitude pairs with no images at all.**

**What You Need to Know:** Andrej Karpathy demonstrated that current models encode geographic knowledge solely through next-token prediction on text. Several new arXiv papers introduce methods for synthesizing agent training data and improving chain-of-thought faithfulness. NVIDIA continues optimizing AI factories for tokens per megawatt while open research explores tokenization costs across languages.
---
### Top Story
Andrej Karpathy showed that large language models can correctly classify land versus water when given only latitude and longitude as text. The evaluation queried models 16,200 times across a grid and rendered the answers as an image that closely matches real geography. The result demonstrates that factual spatial knowledge emerges from compressing internet text alone. No vision training or image data was involved in the models tested. Builders can reproduce the test with any frontier model by feeding coordinate strings and plotting outputs. The finding reinforces that scale on text continues to unlock structured world knowledge without multimodal input. Source: [x.com](https://x.com/karpathy/status/2105909609487872075)
---
### Model Updates

**GraphForge: Training Working Agents with Graph-Anchored Workspace Synthesis: arXiv NLP**
GraphForge builds tasks from real files and an evidence graph so both the task and its verification rubrics are grounded in the same documents. Fine-tuning Qwen3.6-27B on 2,169 trajectories raised GDPVal to 1445.7 under OpenHands and improved Workspace-Bench-Lite and SpreadsheetBench II scores. The data and models are released publicly. Source: [arxiv.org](https://arxiv.org/abs/2609.38923)

**Settle: Learning When to Stop Reasoning: arXiv NLP**
Settle trains the end-of-reasoning token on answer stability observed in completed traces. On MATH-500 with Qwen3-4B it cut token count by forty percent while accuracy dropped only half a percentage point. The method requires only ordinary decoding at inference time. Source: [arxiv.org](https://arxiv.org/abs/2609.38997)

**Making LLMs Say What They Think: Measuring and Improving CoT-Interpretability Alignment: arXiv NLP**
The authors introduce CoT-Interpretability Alignment as a metric comparing chain-of-thought traces to internal reasoning detected by interpretability tools. Baseline alignment across three tasks and three models ranged from forty-four point eight to seventy-five point nine percent. Post-training with both accuracy and faithfulness rewards improved parametric faithfulness while preserving task performance. Source: [arxiv.org](https://arxiv.org/abs/2609.38972)

**The Invisible Language Tax: Token Premiums of French and Regional Languages in 2026 LLM Tokenizers: arXiv NLP**
French requires thirty-one to fifty-eight percent more tokens than English across seven 2026 tokenizers. Regional languages of France pay roughly one point six to three point three times the English token count. A byte-level BPE prototype called Baracoda FR v1.2 reduces the French premium by eleven point five percent relative to Tekken while using three point seven percent fewer tokens on English. Source: [arxiv.org](https://arxiv.org/abs/2609.39001)

**Fairness Beyond a Single Run: Training-Seed Variability in Speech LLM Adaptation: arXiv NLP**
Seed choice moved fairness metrics more than audio compression on most demographic axes when fine-tuning speech LLMs on four hundred sixty hours of LibriSpeech. Eighty-five point three percent of the variation in Fair-Speech ethnicity normalized gap was attributed to seed rather than compression. Scaling the adaptation set to nine hundred sixty hours reduced but did not eliminate the effect. Source: [arxiv.org](https://arxiv.org/abs/2609.38976)
---
### Agent & Tool Developments
**AutoSynthData: Generating Training Data for Enterprise Agents: Hugging Face Blog**
AutoSynthData turns a target model's failures and a stronger teacher's successes into new training tasks that exercise the same capability in varied situations. Tasks are generated inside EnterpriseOps Gym and validated for feasibility against the environment specification. The curriculum shifts automatically toward remaining weaknesses as the model improves. Source: [huggingface.co](https://huggingface.co/blog/ServiceNow-AI/autosynthdata)

**RSIGame: Autonomous Agentic Game Development with Recursive Self-improvement: arXiv NLP**
RSIGame runs local explore-diagnose-improve loops alongside a global loop that preserves the best checkpoint and detects saturation. Across one hundred forty GameCraft-Bench tasks it raised quality on two engines and five generators. Experience internalization let Qwen3.8-27B exceed GPT-5.5 one-shot scores while using eleven times fewer generation tokens. Source: [arxiv.org](https://arxiv.org/abs/2609.39045)

**Evidence First, Arithmetic Second: A System Report and Failure Analysis for DocSem: arXiv NLP**
The EVICALC system reads PDFs, selects passages, asks a language model to write arithmetic expressions, and evaluates them locally. It achieved eight point six one percent joint accuracy on the official test set of one thousand seven hundred thirty tasks. A public-validation run reached ninety-two point seventeen percent answer accuracy with perfect evidence F1. Source: [arxiv.org](https://arxiv.org/abs/2609.39013)

**Structure vs. Chain-of-Thought: Evaluating LLM Criteria Extraction for Depression Severity: arXiv NLP**
Criteria extraction was compared with chain-of-thought prompting on two Reddit corpora using PHQ-9 and BDI-II questionnaires. For frontier models the extraction approach showed no significant gain once decision thresholds were fixed a priori from the questionnaire criteria. The nine billion parameter model labeled most posts severe regardless of prompting style on one corpus. Source: [arxiv.org](https://arxiv.org/abs/2609.39049)
---
### Practical & Community
**Tips for understanding LLM outputs: ASD-STE100 writing, diagrams, HTML, explainer videos: Andrej Karpathy (X)**
Karpathy recommends asking models to explain concepts in ASD-STE100 controlled language for cleaner output. He suggests requesting HTML for interactive web pages and custom 3b1b-style explainer videos that use ElevenLabs narration. The approach treats large custom software artifacts as cheap and discardable once intelligence and code become abundant. Source: [x.com](https://x.com/karpathy/status/2105819303471976479)

**Emphasizing LLMs learn solely from text prediction with no images involved: Andrej Karpathy (X)**
Karpathy stressed that all observed capabilities arise from reading large amounts of text and predicting the next token. Image-like arrangements appear only in the two-dimensional layout of text responses. The point underscores that spatial and factual knowledge can emerge without any visual training data. Source: [x.com](https://x.com/karpathy/status/2105912048668590090)

**Bitdefender launches AI Guardian beta for Mac agents: SecurityBrief Australia**
Bitdefender released a beta of AI Guardian that runs on Mac agents. The tool focuses on detecting and containing rogue agent behavior at the endpoint level. Source: [securitybrief.com.au](https://securitybrief.com.au/story/bitdefender-launches-ai-guardian-beta-for-mac-agents)

**DigiCert aims to help tame rogue AI agents: technologydecisions.com.au**
DigiCert announced new certificate and identity controls intended to give organizations visibility and revocation options when autonomous agents act outside intended boundaries. Source: [technologydecisions.com.au](https://www.technologydecisions.com.au/content/security/news/digicert-aims-to-help-tame-rogue-ai-agents-1293296962)
---
### Under the Hood: Tokenization Tradeoffs in Multilingual Settings
Byte-pair encoding builds a vocabulary by repeatedly merging the most frequent adjacent symbol pairs until a target size is reached. The resulting token boundaries reflect training-data statistics rather than linguistic structure, so languages with different orthographies or morphologies pay different token counts for the same meaning. Adding French data to a tokenizer training run reduces the French premium within the first few thousand merges but increases the English token count as vocabulary slots are reallocated. The effect plateaus after roughly fifty thousand merges while the English cost keeps rising, creating a direct capacity trade-off. At inference time the higher token count directly raises both latency and cost because billing and context windows are measured in tokens. When a workload is known to be French-heavy, training a dedicated tokenizer or fine-tuning an existing one on French text yields the largest reduction; otherwise the marginal gain rarely justifies the English penalty. Teams should measure the actual token ratio on their target corpus before committing to a multilingual tokenizer change.
---
### Things to Try This Week
- Ask any frontier model to rewrite an explanation in ASD-STE100 controlled language and compare readability with the default output.
- Reproduce Karpathy's land-or-water coordinate test on your preferred model and plot the results to see geographic knowledge emerge from text alone.
- Fine-tune a small open-weight model on the released GraphForge trajectories to test agent performance on real-file workspaces.
- Generate a custom 3b1b-style explainer video prompt for a topic you are teaching and test it with an ElevenLabs API key.
---
### On the Horizon
- Additional results from the ongoing OpenAI review of agent incidents are expected in the coming weeks.
- More labs are scheduled to release tokenizer variants optimized for specific languages later this quarter.
- New agent safety tooling from endpoint vendors is slated for wider beta access next month.
