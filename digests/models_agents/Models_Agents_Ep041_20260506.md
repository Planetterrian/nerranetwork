# Models & Agents
> **OpenAI rolls out GPT-5.5 Instant as the default ChatGPT model with better factuality and memory features.**

**What You Need to Know:** OpenAI is pushing GPT-5.5 Instant to every ChatGPT user over the next two days, along with API access via `gpt-5.5-chat-latest` and improved memory/personalization for Plus/Pro plans. Anthropic published new research on Model Spec Midtraining showing how pre-training on detailed constitutions improves safety generalization in agentic settings. Google released MTP Drafters that deliver up to 3x faster Gemma 4 inference without quality loss, while a detailed community benchmark explores practical quantization tradeoffs for Qwen 3.6 27B.
---
### Top Story
OpenAI is rolling out GPT-5.5 Instant as the default model for all ChatGPT users over the next two days, with the same model available in the API as `gpt-5.5-chat-latest`. The lighter variant brings measurable gains in factuality (especially medicine, law, and finance), image analysis, STEM question answering, and knowing when to trigger web search. It also ships with improved memory that pulls context from saved memories, past chats, files, and connected Gmail accounts, plus visible memory sources that let users inspect, edit, or disconnect what the model used. Simon Willison noted the model is less capable than the full GPT-5.5, which appears to be a deliberate cost-saving choice, and Sam Altman described the combined speed, intelligence, personality, and memory upgrades as feeling “more than the sum of the parts.” Developers should test the new default immediately in both consumer ChatGPT and the API to see where the capability/speed tradeoff lands for their workloads. Watch for further rollout of personalization features to mobile and any community feedback that might prompt OpenAI to adjust the Instant variant. Source: [x.com](https://x.com/OpenAI/status/2051709035347694047)
---
### Model Updates
**Model Spec Midtraining (MSM) from Anthropic**  
Anthropic released research on Model Spec Midtraining, a technique that inserts a mid-training phase using a detailed model spec or constitution before standard alignment. The approach teaches models broad underlying values rather than narrow rules, improving generalization to agentic settings where chat-only harmlessness training often fails. A toy example shows that training on cheese preferences tied to “pro-America” values causes the model to adopt broader pro-America stances, while swapping the spec to affordability produces different value generalization. The full paper is available on arXiv. Source: [x.com](https://x.com/AnthropicAI/status/2051758544999927943)

**Google MTP Drafters for Gemma 4**  
Google AI open-sourced Multi-Token Prediction (MTP) Drafters that use speculative decoding to deliver up to 3x faster inference on the Gemma 4 family while preserving output quality. The drafters generate multiple tokens in parallel and verify them with the target model, cutting latency without the usual quality penalty seen in aggressive speculative methods. Developers running Gemma 4 workloads can integrate the new drafters immediately for throughput-sensitive applications. Source: [marktechpost.com](https://www.marktechpost.com/2026/05/06/google-ai-releases-multi-token-prediction-mtp-drafters-for-gemma-4-delivering-up-to-3x-faster-inference-without-quality-loss/)

**Qwen 3.6 27B Quantization Benchmarks**  
A detailed LocalLLaMA test compared BF16, Q8_0, Q6_K, Q5_K_XL, Q4_K_XL, IQ4_XS, and lower quants of Qwen 3.6 27B on a chessboard state-tracking and SVG-rendering task. IQ4_XS emerged as the practical sweet spot on 16 GB VRAM hardware, retaining correct piece placement, board orientation, and move highlighting while delivering usable speeds (especially with TurboQuant KV cache tweaks). Anything below IQ4_XS showed noticeable degradation in board orientation or piece positioning. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1t53dhp/quality_comparison_between_qwen_36_27b/)
---
### Agent & Tool Developments
**Kaltura Open Sources Machine-Readable AI Skills**  
Kaltura released open-source machine-readable AI skills designed specifically for agent-first development workflows. The skills provide structured, parseable capability descriptions that agents can discover and compose without brittle prompt engineering. Developers building autonomous agents can pull the library today to improve tool selection and orchestration reliability. Source: [Google News](https://news.google.com/rss/articles/CBMitgFBVV95cUxQTzhfS0hOUmVqS1dPTlFIakhwTmdGc1dUUFJpQjZtNGpaNVlrTFFleDF1SGhsWjIteGtzVVh6Vy1ERnU0T0dPM2RjMzRMTm1JZVItR2FSNjRqcXdYanZGTDJfcmpFYmE4Mk5iTjItUDhJM0lGcUQ0cmliU0x2NV84X0NpX0lJbXNqVG0tTHFaUWlqYW5fM3lGaEQ2LUoyQlN6QzIwejR1NEgzcGRvNVFmeWZXa2dHUQ?oc=5)

**Self-Verification as Conditional Confidence Signal**  
New research evaluates same-model self-verification against strong likelihood baselines (LL-AVG, LL-SUM) on ARC-Challenge and TruthfulQA-MC. The technique improves abstention quality for some model families (notably Qwen-7B) but proves task- and prompt-sensitive, sometimes underperforming simple likelihood sums. Agent builders can use it as one signal among several rather than a universal uncertainty estimator. Source: [arxiv.org](https://arxiv.org/abs/2605.02915)

**Geometric Deviation for Pre-Generation Reliability**  
A new arXiv paper demonstrates that measuring hidden-state deviation from an answerable reference set can provide a lightweight, pre-generation signal for whether a query is answerable. The approach works reliably on mathematical prompts (ROC-AUC 0.78–0.84) but shows little signal on factual prompts, highlighting that representation geometry encodes task form more than universal knowledge boundaries. Useful for agents that need to decide when to refuse or search before generating.
---
### Practical & Community
**Evaluating Reasoning Models on Presupposition Queries**  
Researchers built a benchmark of queries containing varying degrees of false presuppositions across health, science, and general knowledge. Reasoning models only modestly outperform non-reasoning ones (2–11 % higher accuracy) and still fail to challenge 26–42 % of false assumptions, remaining sensitive to how strongly the presupposition is worded. Anyone building agents that answer user questions should test their models against this style of input.

**How Language Models Process Negation**  
Mechanistic interpretability work on Mistral-7B and Llama-3.1-8B shows that models implement both suppressive attention (attending to the negated phrase) and constructive mechanisms (building a representation of the full negated concept). Ablating late-layer attention shortcuts dramatically improves negation accuracy, revealing that poor performance often stems from simple heuristics rather than missing capability.

**MedStruct-S Benchmark for Clinical Report Extraction**  
A new 3,582-page benchmark evaluates semi-structured information extraction from OCR clinical reports under unknown keys and realistic noise. Encoder-only models surprisingly outperform much larger decoder-only models on key-conditioned QA, while fine-tuned decoder-only models win on end-to-end extraction when scale is not controlled. Practical baseline for anyone working with medical document pipelines.
---
### Under the Hood: How LLMs Actually Implement Negation
Everyone talks about “the model understands negation” as if it were a single learned skill. In practice, models implement at least two competing mechanisms that coexist inside the same network and sometimes fight each other. The first is suppressive: specific attention heads learn to attend to the phrase being negated and dampen related concepts downstream. The second is constructive: the model builds an explicit representation of the negated state (for example, turning “not gas” into a vector that promotes liquids and solids). Ablation studies show the constructive route is more prominent in the models examined, yet both are present. Late-layer attention often overrides the correct internal representation with a simple shortcut that produces the wrong answer, which is why removing those heads can raise negation accuracy dramatically even though the knowledge was already there. The effect is strongest in mid-layers and fades toward the output, explaining why prompting tricks that force step-by-step reasoning sometimes help. The practical takeaway is that negation failures are frequently fixable with targeted interventions rather than requiring more data or scale; teams hitting negation bugs should first check whether late-layer attention is the culprit before reaching for fine-tuning.
---
### Things to Try This Week
- Switch your default ChatGPT conversations to GPT-5.5 Instant and test factuality on medical, legal, or financial prompts to see where the speed/accuracy tradeoff feels acceptable.
- Pull the new Gemma 4 MTP Drafters and benchmark latency on your current workloads; the 3x speedup without quality loss makes it worth testing even if you only use Gemma occasionally.
- Run the Qwen 3.6 27B IQ4_XS quant on your 16 GB hardware with the chessboard-style state-tracking prompt to verify whether it meets your reliability needs before committing to production.
- Experiment with self-verification prompts on ARC-Challenge style tasks using Qwen or Phi models to see if the conditional confidence signal improves your agent’s abstention behavior.
- Read the full Anthropic MSM paper and try writing a short model spec for a narrow domain to test whether value-level instructions generalize better than rule lists in your own fine-tunes.
---
### On the Horizon
- Full arXiv paper and follow-up experiments on Model Spec Midtraining are expected to clarify which constitution styles produce the strongest agentic safety gains.
- Further mobile rollout of ChatGPT memory sources and personalization features should land in the coming weeks.
- Additional quantization and speculative-decoding results for the new Gemma 4 family will likely appear as the MTP Drafters see wider adoption.
- More benchmarks testing reasoning models on presupposition-heavy queries are likely as the community adopts the new evaluation set.