# Models & Agents
> **Ten open MoE models expose routing choices that swing sparsity from 4x to 128x and change which hardware setups actually fit.**

**What You Need to Know:** A verified table from model configs shows DeepSeek-V4-Pro using 384 experts with sqrtsoftplus gating and hash routing in three layers, while Llama 4 Maverick keeps its gating method undisclosed. Hamburg’s data-protection office adopted GPT-5.6 Terra inside a wrapper that blocks personal-data leakage even though the model itself likely retains training data. The U.S. Center for Advancing Innovation and Standards for Super Intelligence now routes staff reports informally to the White House, raising questions about research independence.
---
### Top Story
MarkTechPost published a side-by-side audit of routing knobs across ten open Mixture-of-Experts models drawn directly from their Hugging Face config.json files and technical reports. Expert counts range from 8 in Mixtral to 384 in DeepSeek-V4-Pro and Kimi K2; top-k selection runs from 1 in Llama 4 Maverick to 8 in several Qwen and Kimi variants. DeepSeek-V3 and later variants replace the usual auxiliary loss with an aux-loss-free bias that steers expert selection without altering mixing weights. Kimi K2 demonstrated that raising sparsity from 8 to 48 cut FLOPs by 1.69x at identical validation loss. Builders now have an auditable reference for deciding whether a given MoE will run on a single 80 GB GPU or requires expert parallelism across multiple cards. The same outlet released a companion guide the same day that walks through the seven routing strategies in production use. Source: [marktechpost.com](https://www.marktechpost.com/2026/11/08/moe-model-routing-comparison/) Source: [marktechpost.com](https://www.marktechpost.com/2026/11/07/moe-routing-strategies-explained/)

### Model Updates
**GRFNet, PyTorch model for multichannel time-series classification [P]: r/MachineLearning**
The model mixes input channels with learned spatial filters initialized from electrode positions when available, then passes the result through a bank of mostly frozen dilated convolutions. It extracts summary statistics, gates them, and classifies with a 3,847-parameter head on the default 22-channel, 4-class setting. The architecture accepts variable-length inputs and adapts to sampling rate without retraining. A subject-independent evaluation on PhysioNet EEGMMIDB is underway, comparing against EEGNet and ShallowConvNet. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1xqqj67/grfnet_pytorch_model_for_multichannel_timeseries/)

**Timestral, t0, Tabby, and Morpheus-2.0 Compared on GIFT-Eval: Towards Data Science**
All four time-series foundation models scale, patch, and output quantiles; the decisive difference lies in how each series shares information across the batch. The post walks through the architectural split that determines whether models treat series independently or borrow statistical strength from one another during training. Source: [towardsdatascience.com](https://towardsdatascience.com/timestral-t0-tabby-and-morpheus-20-compared-on-gift-eval/)

**Locally trained VLA model with minimal attention based vision encoder. [p]: r/MachineLearning**
A 25.5 M parameter recurrent model maintains a 768×768 state matrix with per-cell LSTM-style gates and learns visual attention directly over raw 128×128 RGB pixels without a separate pretrained encoder. It was transitioned from a language-modeling checkpoint and now performs a shape-naming task in 1-, 2-, and 3-room 3-D environments, reaching >90 %, >80 %, and >60 % success respectively on randomized test runs. Training used supervised imitation on 70 k steps with batch size 4 after an initial 150 k language-modeling steps. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1xqrtcz/locally_trained_vla_model_with_minimal_attention/)

### Agent & Tool Developments
**Nine AI agents tried autonomous research on open questions from US national labs and none passed the experts' bar: The Decoder**
Nine autonomous agents were given open research questions drawn from U.S. national-lab problem lists and produced no outputs that met the bar set by domain experts. The evaluation focused on whether agents could formulate, execute, and validate novel research steps without human intervention. Source: [the-decoder.com](https://the-decoder.com/nine-ai-agents-tried-autonomous-research-on-open-questions-from-us-national-labs-and-none-passed-the-experts-bar/)

**Law Firms Have Malpractice Insurance. Should Their A.I. Agents?: The New York Times**
The piece examines whether existing malpractice policies cover errors made by AI agents that draft contracts, perform due diligence, or manage discovery. It notes that firms already purchase coverage for human associates and asks how liability should attach when the agent operates inside the firm’s workflow. Source: [nytimes.com](https://www.nytimes.com/2026/11/07/business/dealbook/crosby-ai-agent-liability-malpractice-insurance.html)

**Amazon Quick Unveils Taxonomy for Agentic AI Primitives: The Chenab Times**
Amazon Quick released a taxonomy that breaks agentic systems into named primitives for planning, tool use, memory, and verification. The taxonomy is intended to give developers a common vocabulary when composing multi-step agents on AWS infrastructure. Source: [thechenabtimes.com](https://thechenabtimes.com/2026/11/07/amazon-quick-unveils-taxonomy-for-agentic-ai-primitives/)

### Practical & Community
**What if diffusion models generates Neural Network weights? Gen AI generate Gen AI [R]: r/MachineLearning**
A small diffusion model was trained to output neural-network weight tensors instead of images, with a proof-of-concept repository and web demo that lets users request simple controllers such as a Pong paddle network. The author reports partial success after 3 000 of 4 000 training steps on CPU and invites community contributions or pointers to related papers. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1xqsl8d/what_if_diffusion_models_generates_neural_network/)

**TristanTube: YouTube viewer from Tristan's top channels: Andrej Karpathy**
Karpathy built a YouTube-style viewer over the 47 k videos in Tristan’s tier list, adding dark mode, an about page, and a TV mode for passive watching. The entire site was generated in three minutes with Claude Code. Source: [karpathy.ai](https://karpathy.ai/tristan-tube/) Source: [x.com](https://x.com/karpathy/status/2119130029699547594)

**Garak: LLM Vulnerability Scanner & Probing Guide: CASRAI**
CASRAI published a practical guide to Garak, an open-source scanner that probes LLMs for prompt-injection, data-leakage, and jailbreak vulnerabilities. The guide walks through installation, probe selection, and result interpretation for red-team workflows. Source: [casrai.org](https://casrai.org/guides/garak)

### Also Today
**Hamburg regulator uses OpenAI model to draft letters as complaints rise 62%: PPC Land**
The Hamburg data-protection office reviewed and then deployed an OpenAI-based chatbot wrapped so that personal data cannot leak back out, using it to draft routine correspondence while humans retain final legal reasoning. Source: [ppc.land](https://ppc.land/hamburg-regulator-uses-openai-model-to-draft-letters-as-complaints-rise-62/)

**Staff at the US center for AI safety are reporting to the White House, raising independence concerns: ABC News**
The Center for Advancing Innovation and Standards for Super Intelligence lacks a permanent director, has stopped publishing research, and now routes staff work informally to the White House, prompting concerns that findings on frontier systems could be muted. Source: [abcnews.com](https://abcnews.com/US/wireStory/staff-us-center-ai-safety-reporting-white-house-137950879)

**Advice needed regarding classical ML conference submission [D]: r/MachineLearning**
A PhD student reports that area chairs at top conferences rejected classical ML work on SVMs and logistic regression as “done and dusted,” even when reviewers found the claims novel, and asks whether such topics now belong only in journals or on arXiv. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1xqqrof/advice_needed_regarding_classical_ml_conference/)

**Can I become an ML/AI Engineer with a BS Mathematics and Data Science degree instead of Computer Science? [D]: r/MachineLearning**
A student pursuing a mathematics-and-data-science degree asks whether employers view the credential as sufficient for ML engineering roles and what additional CS fundamentals would close any perceived gap. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1xqcl2h/can_i_become_an_mlai_engineer_with_a_bs/)
---

### Things to Try This Week
- Run the Garak scanner against any new model release you are evaluating to surface prompt-injection or data-leakage vectors before production use.
- Clone the nngen repository and continue the diffusion weight-generation experiment on a narrow controller domain to test whether the partial results hold.
- Compare Timestral against Tabby on your own time-series dataset using the GIFT-Eval protocol to see which information-sharing strategy reduces error on your data distribution.
- Load the GRFNet PyTorch implementation on your own multichannel EEG or sensor data and measure how the learned spatial filters affect subject-independent accuracy versus a standard EEGNet baseline.

### On the Horizon
- Continued community experiments on diffusion-based weight generation may surface papers or larger-scale replications in the coming weeks.
- More regulators are expected to publish case studies on wrapped frontier models following Hamburg’s nine-page review.
- Additional agent evaluations on national-lab open questions will likely appear as teams refine harnesses and success criteria.
