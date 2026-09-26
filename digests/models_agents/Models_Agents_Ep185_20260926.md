# Models & Agents
> **Claude solved a nine-loop scattering amplitude problem in particle physics that stood as the prior record at eight loops.**

**What You Need to Know:** Anthropic reports that Claude completed the calculation in a research environment using methods from SLAC physicist Lance Dixon, at a cost of a few thousand dollars. Google detailed three new agent layers inside Search powered by Gemini 3.5 Flash. Simon Willison described the past year in AI as feeling like a century of change compressed into months. The nine-loop result was verified independently by Dixon after the model ran unsupervised for days on a single prompt. Google set Gemini 3.5 Flash as the global default for AI Mode and reported one billion monthly active users for the feature. Willison posted the compressed-century observation the same day he delivered the closing keynote at WeAreDevelopers.
---
### Top Story
Claude completed a nine-loop scattering amplitude calculation in the planar N=4 super-Yang-Mills model. The previous record stood at eight loops, set by Lance Dixon and collaborators at SLAC. A single prompt describing the nine-loop problem was given to Claude in the Claude Science environment. The model ran largely unsupervised for days and produced a result that Dixon later verified independently. The total compute cost came to a few thousand dollars using only an academic-scale budget. Physicist and writer [@4gravitons](https://x.com/4gravitons) had issued the challenge last month. The full write-up appears on the Anthropic science blog. The calculation used methods developed by Dixon and his colleagues throughout the run. No additional human intervention occurred after the initial prompt. The result marks the first time the nine-loop threshold has been crossed in this simplified model. Source: [x.com](https://x.com/AnthropicAI/status/2103541577083719888)
---
### Model Updates
**Karpathy clarifies AGI to ASI terminology shift: Andrej Karpathy (X)**
Karpathy stated that dropping the word "Artificial" from AGI and ASI has been standard terminology for a decade. He called the shorter forms cleaner because the prefix is redundant. The post came in response to ongoing discussion about capability trajectories beyond current frontier systems. Karpathy noted that researchers have discussed the progression from general to super intelligence for ten years. He emphasized that the change simply removes an unnecessary qualifier without altering the underlying concept. Source: [x.com](https://x.com/karpathy/status/2103528977583546678)

**Simon Willison keynote remarks on industry pace: Simon Willison (X)**
Willison wrote that the last year in technology has felt like one hundred years compressed together. He noted that every limit frontier models encounter collapses within roughly a month. The comments preceded his closing keynote at the WeAreDevelopers conference. Willison added that everything done with frontier models today will become instantaneous and free within a few years. The observation was posted the morning of the keynote. Source: [x.com](https://x.com/simonw/status/2103688757337895282)

**Gemini 3.5 Flash becomes default for AI Mode: forkast.news**
Google set Gemini 3.5 Flash as the new default model for AI Mode globally. Sundar Pichai described Flash as four times faster than other frontier models while delivering frontier-level performance at less than half the price. AI Mode has now surpassed one billion monthly active users. The company also reported that AI Overviews now reach two billion five hundred million users. Pichai tied the rollout to an infrastructure investment of one hundred eighty to one hundred ninety billion dollars in twenty twenty-six. Source: [forkast.news](https://forkast.news/google-just-turned-its-biggest-product-into-an-agent-platform/)

**Simon Willison on stage for keynote: Simon Willison (X)**
Willison posted that he would be on stage for the keynote in ten minutes. The appearance was the closing keynote at WeAreDevelopers on the main stage. The post received twenty-eight thousand six hundred views within hours. Willison had referenced the rapid industry change in earlier remarks the same day. Source: [x.com](https://x.com/simonw/status/2103641180923978031)
---
### Agent & Tool Developments

**Microsoft Autopilot runs persistent agents without prompts: Trend Hunter**
Microsoft Autopilot continues executing workplace tasks after the initial user prompt ends. The system maintains ongoing agent sessions that operate autonomously across documents and applications. Persistent sessions allow the agent to finish multi-step workflows without further input. The feature targets enterprise document and productivity environments. Source: [trendhunter.com](https://www.trendhunter.com/trends/office-and-autopilot)

**Meta AI agent relied on human call-center support: CNET**
Leaks show that Meta's new AI agent Muse used real people at call centers to complete phone-based tasks. The arrangement allowed the agent to handle conversations that current models could not finish independently. The support was required for tasks involving live phone calls to external parties. The revelation came from internal documents obtained by the publication. Source: [cnet.com](https://www.cnet.com/tech/services-and-software/leaks-metas-new-ai-agent-muse-real-people-call-centers/)
---
### Practical & Community
**Guide to distributed algorithms for LLM training and inference: r/MachineLearning**
A Reddit post shares a curated list of papers on data, tensor, pipeline, and model parallelism. The author includes a GitHub repository with basic implementations for each technique. The collection aims to give practitioners enough background to start coding distributed setups quickly. The post recommends reading the papers then immediately coding the referenced implementations. The repository link was shared directly in the thread for easy access. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1wqk0x2/a_little_guide_to_learning_distributed_algorithms/)

**Proaction reports productivity gains with Codex: OpenAI Blog**
Proaction used Codex, GPT-Live-1, and GPT-6 Astra to build, operate, and sell fleet-management software. The company recorded a sixty percent sales increase and saved more than seventy-five hours per week on development tasks. The models handled code generation, operations automation, and sales workflow acceleration. The reported gains came after integrating the three OpenAI tools into daily engineering processes. Source: [openai.com](https://openai.com/index/proaction)

**OpenRouter acquisition discussion: Latent Space**
The Latent Space podcast episode covers OpenRouter's path from seed round to a reported seven-billion-dollar acquisition by Stripe. The discussion focuses on infrastructure for routing across dozens of frontier and open-weight models. The episode highlights how the platform grew amid rapid expansion of available models. Stripe's purchase price was disclosed during the conversation. Source: [latent.space](https://www.latent.space/p/openrouter)
---
### Under the Hood: Pipeline Parallelism Tradeoffs
Pipeline parallelism splits a model across multiple GPUs so that different layers run on different devices and micro-batches flow through the stages like an assembly line. The approach reduces the memory footprint on any single GPU compared with placing the entire model on one card. Bubble time appears when a stage finishes its micro-batch before the next stage is ready, lowering overall utilization. With eight stages the bubble fraction can reach twenty-five percent unless the micro-batch size is increased to keep every stage busy. Activation checkpointing trades extra computation for lower memory use, cutting peak memory by roughly half at the cost of thirty percent more FLOPs. Teams choose pipeline parallelism when model size exceeds single-GPU memory yet tensor parallelism would require expensive high-bandwidth interconnects. The practical rule is to start with pipeline stages equal to the number of GPUs and then add tensor parallelism inside each stage only when communication latency becomes the bottleneck. Eight-stage pipelines therefore require careful micro-batch tuning to avoid the twenty-five percent utilization penalty. Checkpointing remains the first lever teams adjust when memory pressure appears before they increase interconnect spend.
---
### Things to Try This Week
- Try the distributed algorithms repository from the Reddit post to implement basic tensor and pipeline parallelism on a small model.
- Test Gemini 3.5 Flash inside Google AI Mode for generative UI tasks that previously required separate coding tools.
- Run a persistent Autopilot session on a multi-step document workflow to see how it continues after the initial prompt.
- Explore the OpenRouter routing options now that the platform has been acquired by Stripe for seven billion dollars.
---
### On the Horizon
- Google plans to expand information agents to more subscriber tiers later this summer.
- Custom Antigravity mini-apps inside Search are scheduled to reach AI Pro users in the coming months.
- OpenRouter users can expect continued routing improvements as more labs release new models.