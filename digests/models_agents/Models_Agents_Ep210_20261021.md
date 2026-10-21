**# Models & Agents**
> **RL training is driving models to abandon English in chain-of-thought traces, revealing internal reasoning that no longer needs human language.**

**What You Need to Know:** Andrej Karpathy highlighted that reinforcement learning now produces coherent non-English reasoning traces. Dario Amodei detailed nine commercially costly safety steps Anthropic has taken in the past year while defending its frontier strategy. Simon Willison released a reusable AI proofreading prompt and added real-time multiplayer to his Battle Drones demo. Multiple new arXiv papers introduce calibrated unlearning, phonetic-expert adaptation for accented ASR, and latent multi-hypothesis memory for long-horizon agents.
---
### Top Story
Andrej Karpathy observed that current RL post-training is working because models are producing coherent chain-of-thought traces that no longer rely on English. The shift indicates the models have developed internal representations that are more efficient for the task than natural language. Builders using reasoning traces for verification or auditing will need new inspection methods once the intermediate steps stop being human-readable. The observation aligns with earlier reports of models inventing private token sequences during long-horizon tasks. Watch for labs to publish tools that surface or translate these non-English traces. Source: [x.com](https://x.com/karpathy/status/2112763753754485205)
---
### Model Updates
**H2DF: Calibrated Target Bands for Controllable Language-Model Unlearning — arXiv NLP**
H2DF replaces unbounded gradient ascent with a data-dependent target band that applies pressure only below a lower threshold and reverses it once the band is reached. The method needs only one forget-batch pass per step plus sparse retain replay every tenth step. On TOFU it matches GradDiff forget and retain NLL while cutting variability; on MUSE-News it improves retention over GA and NPO. Source: [arxiv.org](https://arxiv.org/abs/2610.26864)

**Mixture of Phonetic Experts Based Low-Rank Adaptation of Conformer Models for Accented English Speech Recognition — arXiv NLP**
MoPE-LoRA places six low-rank experts aligned to manner-of-articulation classes and routes at the frame level with a hybrid phoneme-plus-acoustic gate. The shared expert set removes the need for accent-specific modules and supports zero-shot transfer to held-out accents. On L2-ARCTIC it delivers a 12.3 % relative WER improvement over single LoRA in the zero-shot setting. Source: [arxiv.org](https://arxiv.org/abs/2610.26888)

**Do We Need the Largest LLMs for Every Clinical Decision? — arXiv NLP**
CERTA supplies a statistical certificate that decides when an 8-bit or 4-bit quantized model can safely replace its BF16 reference for a given clinical verification decision. Across eleven models the 8-bit path covered 99.8–100 % of decisions; the 4-bit frontier cut amortized cost to roughly 26 % of the BF16 baseline while staying under 48 GB. Source: [arxiv.org](https://arxiv.org/abs/2610.26937)

**The Bottleneck Is Retrieval, Not Reading: Diagnosing Evidence-Based Generation with RAG for Long Context Question Answering — arXiv NLP**
EBG requires line-level citations and scores both correctness and grounding. On MultiHop-RAG and QASPER-MP it shows that similarity retrieval reliably surfaces any relevant chunk but frequently misses the full set needed for multi-fact questions, while chunking erases document-level metadata required for identity resolution. Source: [arxiv.org](https://arxiv.org/abs/2610.26951)

**The Culture Within: Towards Mechanistic Understanding of Cultural Reasoning in LLMs — arXiv NLP**
CultureLens varies country, value, true-norm and contradictory-norm evidence across 9 261 scenarios. Stating a contradictory norm drops aligned answers by 32–47 points even when the model knows the correct country norm; blocking the contradictory norm inside the model restores the correct answer in most cases. Supervised fine-tuning on contradictory-norm examples raises aligned performance to 85–93 % on unseen countries. Source: [arxiv.org](https://arxiv.org/abs/2610.27202)

**Learned Readout Tokens for Extracting Large Language Model Confidence — arXiv NLP**
A learned readout token is inserted and its hidden state is used to train a confidence probe. The approach outperforms probes that read from existing vocabulary tokens on multiple datasets and model families; extending it to multiple learned tokens yields further gains. The change is a drop-in replacement for any existing probe. Source: [arxiv.org](https://arxiv.org/abs/2610.27566)
---
### Agent & Tool Developments
**LAMB: Latent Multi-Hypothesis Beliefs for Long-Horizon Large Language Agents — arXiv NLP**
LAMB encodes interaction evidence in a shared Common state and competing hypotheses in weighted Delta components, updating them recurrently from action-outcome predictions without emitting text. On ALFWorld it raises SR@30 by 6 points and cuts redundant actions by 17.7 points; on ScienceWorld success rises 22 points. Source: [arxiv.org](https://arxiv.org/abs/2610.26955)

**LoWAgent: A Low-Resource Multilingual Benchmark for Web Agents — arXiv NLP**
LoWAgent supplies six fully localized websites across English, Hindi, Bengali, Urdu and Amharic, yielding 3 000 task instances. Both closed and open-source agents drop sharply on the low-resource languages, with open-source models showing the largest degradation; post-training on a small subset of traces recovers substantial performance. Source: [arxiv.org](https://arxiv.org/abs/2610.27205)

**Which Agent's Skill Should Change? Group-Relative Credit Assignment for Evolving Multi-Agent Teams — arXiv NLP**
GRSE runs each question multiple times under the same skill libraries and contrasts executions to assign credit to specific agent–skill pairs. On HotpotQA it outperforms MASkills on multi-hop questions; on corrupted libraries it correctly signs every planted harmful skill and recovers clean-library performance. Source: [arxiv.org](https://arxiv.org/abs/2610.27227)

**MMedAgent-Plus: Scaling Multimodal Medical Agents across Modalities, Tasks and Workflows — arXiv NLP**
MMedAgent-Plus pairs a vision-language planner with 18 specialist models spanning 12 tasks and 8 modalities. The planner achieves 91 % tool-call accuracy in single-tool multi-round settings and 80.7 % in multi-tool single-round settings; end-to-end accuracy on held-out cases reaches 0.98, matching dedicated specialists. Source: [arxiv.org](https://arxiv.org/abs/2610.27233)
---
### Practical & Community
**AI proofreading prompt shared — Simon Willison**
Simon Willison published the exact prompt he uses for AI proofreading and made it available in his agentic-engineering-patterns guide. Source: [simonwillison.net](https://simonwillison.net/guides/agentic-engineering-patterns/prompts/#proofreader)

**Online multiplayer added to Battle Drones after headache bug — Simon Willison**
After an audio-only multiplayer mode caused motion sickness, Simon Willison added a WebSocket relay for real online multiplayer in his Battle Drones demo. Source: [simonwillison.net](https://simonwillison.net/2026/Oct/20/battledrones/#update-online-multiplayer-support)

**Releasing 211 scorpion toxin binder designs and lab data — [@AnthropicAI](https://x.com/AnthropicAI)**
Anthropic released all 211 tested binder designs plus the corresponding lab data on Hugging Face as a public resource for scientists. Source: [huggingface.co](https://huggingface.co/datasets/Anthropic/scorpion-toxin-binder-design)

**FairStress: A deeper evaluation of fairness in LLM decision-making — Hugging Face Blog**
AllenAI published FairStress, a benchmark that probes fairness across a wider set of decision scenarios than prior suites. Source: [huggingface.co](https://huggingface.co/blog/allenai/fairstress)

**Franchisee reconciles cash in 94% less time with ChatGPT Work — OpenAI Blog**
An independent Schlotzsky’s and Cinnabon franchisee used ChatGPT Work to cut menu-repricing time by 95 % and surface a workflow that could free roughly $100 K in cash flow. Source: [openai.com](https://openai.com/index/ted-taylor-restaurant)
---
### Also Today
**Dario Amodei defends Anthropic's "race to the top" strategy and lists safety actions — [@DarioAmodei](https://x.com/DarioAmodei):** Dario Amodei published a detailed reply listing nine commercially costly safety actions taken by Anthropic in the past year while defending the company’s frontier strategy. Source: [x.com](https://x.com/DarioAmodei/status/2112732230124818891)

**Sam Altman welcomes Aleksander Madry back to OpenAI for safety work — Sam Altman:** Sam Altman announced that Aleksander Madry has rejoined OpenAI to lead safety and security work on superintelligence. Source: [x.com](https://x.com/sama/status/2112652656602923366)

**OpenAI Acquires Orchestra Bio for Drug Development — [@OpenAI](https://x.com/OpenAI):** OpenAI acquired Orchestra Bio to extend its Rosalind life-sciences tooling into full drug-development coordination. Source: [x.com](https://x.com/OpenAI/status/2112607347688583586)

**ALTK-Evolve: How learned memory tops the τ²-bench leaderboard on customer service tasks without a frontier model — Hugging Face Blog:** IBM Research released ALTK-Evolve, which uses learned memory to reach the top of the τ²-bench customer-service leaderboard without requiring a frontier model. Source: [huggingface.co](https://huggingface.co/blog/ibm-research/altk-evolve-bc)
---
### Under the Hood: Implicit Budgeting Under Task Composition
When several tasks share a single prompt, models allocate fewer tokens to each task than they would in isolation, even when the total context remains comfortably inside the window. The effect appears because the model maintains an implicit per-task compute budget that shrinks under competition; tasks whose isolated solutions already require long traces suffer the largest accuracy drop. The budgeting is visible in token counts per sub-task and in the sudden rise of errors once any single task’s trace length exceeds a model-specific threshold. Adding explicit per-task length instructions or forcing intermediate verification steps restores most of the lost performance, but at the cost of extra tokens overall. The practical takeaway is to measure per-task token usage on representative multi-task prompts before deployment; if any task routinely exceeds roughly 60 % of its isolated length, split the prompt or add verification rather than relying on the model to self-regulate.
---
### Things to Try This Week
- Paste Simon Willison’s proofreading prompt into your editor and run it on the next technical document you write; it catches subtle phrasing issues that generic prompts miss.
- Test H2DF-style target-band unlearning on a small TOFU-style dataset if you need controllable forgetting without the overshoot common in plain gradient ascent.
- Run MoPE-LoRA on an accented English ASR fine-tune; the six phonetic experts give measurable gains on held-out accents without maintaining separate modules.
- Try the learned-readout-token confidence probe on your current generation pipeline; it is a one-line insertion that improves AUROC on both in-domain and out-of-domain checks.
- Evaluate LAMB-style latent multi-hypothesis memory on any long-horizon agent task where competing explanations must be retained without bloating the context.
---
### On the Horizon
- OpenAI is expected to expand the Rosalind life-sciences tooling now that Orchestra Bio has been acquired.
- Anthropic plans to release further details on its public-benefit fund and pacing strategy in the coming weeks.
- More labs are likely to publish non-English chain-of-thought inspection tools following Karpathy’s observation.
- Additional low-resource web-agent benchmarks and adaptation recipes are anticipated after the LoWAgent release.
