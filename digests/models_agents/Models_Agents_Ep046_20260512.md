# Models & Agents
> **OpenAI's Daybreak pairs frontier models with Codex Security to let developers find, validate, and patch vulnerabilities earlier in the cycle.**

**What You Need to Know:** OpenAI launched Daybreak today, an initiative that combines its latest models with an agentic coding system and partner network to automate security detection and response. Sam Altman highlighted how the new ChatGPT model, personality controls, and personalization now cross a usability threshold for many users. Meanwhile, Andrej Karpathy shared practical prompting techniques for richer LLM outputs, and several new research papers benchmarked agent behavior and multimodal embeddings.
---
### Top Story
OpenAI is launching Daybreak, a cybersecurity program that integrates frontier AI models with Codex Security, its coding-focused agentic system, and a network of security partners. The effort targets developers, enterprise teams, researchers, and government defenders who need to detect, validate, and patch software vulnerabilities earlier in the development process. Daybreak automates detection, validation, and response while respecting existing security rules and compliance requirements. Early access is open now at openai.com/daybreak, with Altman inviting companies to start continuous security work immediately. Watch for partner integrations and expanded Codex capabilities as the program scales. Source: [x.com](https://x.com/sama/status/2053951874408276193)
---
### Model Updates
**Karpathy on HTML-structured outputs and vision-first interfaces: Andrej Karpathy**
Karpathy recommends prompting LLMs to return responses as HTML or slideshows for better readability and interactivity, noting that vision is the brain's preferred output channel. He outlines a progression from raw text to markdown to HTML and eventually interactive neural videos or simulations. This approach gives builders more flexible, browser-viewable results today without waiting for new model releases. Source: [x.com](https://x.com/karpathy/status/2053872850101285137)

**jina-embeddings-v5-omni multimodal suite: arXiv**
The new jina-embeddings-v5-omni models encode text, image, audio, and video into one semantic space by freezing existing text towers and training only lightweight connectors (0.35% of total weights). Performance stays competitive with larger multimodal models while keeping text embeddings identical to prior Jina v5 releases. Developers can adopt the approach for efficient multimodal retrieval without full retraining. Source: [arxiv.org](https://arxiv.org/abs/2605.08384)

**SalesSim benchmark for retail user simulators: arXiv**
SalesSim evaluates multimodal LLMs as persona-driven shoppers in multi-turn retail conversations, measuring decision alignment and conversational quality. Current models show fluent output but low lexical diversity, over-disclosure, and drift from persona specs (strongest model under 79% alignment). The paper introduces UserGRPO, a multi-objective RL method that lifts alignment by 13.8% while preserving fluency. Source: [arxiv.org](https://arxiv.org/abs/2605.08334)
---
### Agent & Tool Developments
**Laserfiche AI agents for natural-language workflows: AI News**
Laserfiche released AI agents that execute tasks via natural language prompts while enforcing the platform's security and compliance rules. The agents act autonomously inside content management systems, keeping sensitive data protected. Users can now describe workflows in plain language instead of building rule-based scripts. Source: [artificialintelligence-news.com](https://www.artificialintelligence-news.com/news/laserfiche-ai-agents-act-autonomously-for-the-platforms-users/)

**Circle USDC tools for AI agent payments: Cryptonews.net**
Circle is extending USDC infrastructure to support payments initiated by AI agents. The move targets the growing volume of autonomous transactions in agent ecosystems. Developers working on agentic commerce can now integrate stablecoin rails directly into agent tool-calling loops. Source: [Google News](https://news.google.com/rss/articles/CBMiXEFVX3lxTE5PNVZ3S0pZaC05OTNGOU9PdF9kOUdkU0pWeVJURDVfdEZjMFY2UDZLSHp0LUNoMVNWR0I2MnYtTDREdExWQ1p4cFVGY0p4ZzJDX2Nlb2p5cVducWp4?oc=5)
---
### Practical & Community
**Llama 3.x fine-tuning still relevant? r/LocalLLaMA**
Community discussion asks whether Llama 3.3 70B remains competitive for fine-tuning given newer 70B-class models like Qwen3. Users report continued success with Llama 3 variants when compute or licensing constraints favor them. The thread surfaces practical tips on dataset choices and evaluation for those still iterating on these checkpoints. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1tau8jx/llama_models_still_valuable_for_finetuning_or/)

**Claude Code memory footprint: Simon Willison**
Willison measured ~30 GB total memory use from multiple Claude Code processes across terminal windows, with the largest single process at 4.9 GB. The observation highlights the hidden resource cost of running several agentic coding sessions simultaneously on consumer hardware. Source: [x.com](https://x.com/simonw/status/2053973809510916205)
---
### Under the Hood: Frozen-Tower Multimodal Embeddings
Everyone talks about multimodal embeddings as if you simply bolt vision and audio encoders onto a text model. In practice the engineering win comes from keeping the original towers frozen and training only thin adapters. This preserves the exact text embedding space you already tuned while adding new modalities at roughly 0.35 % of total parameter cost. The adapters learn to project non-text features into the frozen language-model input space, so inference latency grows only by the cost of the new encoders plus a small projection step. Quality stays within a few points of fully trained multimodal models on retrieval benchmarks because the heavy semantic lifting is still done by the original text backbone. The main tradeoff is that cross-modal alignment can never exceed what the frozen text space already encodes; if your downstream task needs tighter image-text coupling, you eventually pay for joint fine-tuning. Use the frozen approach when you already have production text embeddings and want to add images or audio without retraining or breaking existing indexes; switch to end-to-end training only when you can measure a clear gap on your specific retrieval or classification metric.
---
### Things to Try This Week
- Point your LLM at a task and append “structure your response as HTML” then open the file in a browser—Karpathy’s quick test for richer, interactive outputs.
- Sign up for Daybreak at openai.com/daybreak if you maintain production codebases and want early access to AI-assisted vulnerability validation.
- Benchmark your current embedding pipeline against jina-embeddings-v5-omni on a mixed text-plus-image retrieval set to see whether the frozen-adapter route saves training time without hurting recall.
- Run a small SalesSim-style persona test on your own agent: give it a shopper profile and measure how often it drifts from the stated preferences across five turns.
---
### On the Horizon
- More companies are expected to announce agent payment integrations following Circle’s USDC push.
- Watch for follow-on papers that apply the UserGRPO recipe to non-retail agent benchmarks.
- Laserfiche-style governed agents will likely appear in additional enterprise content platforms this quarter.