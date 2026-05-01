# Models & Agents
**Date:** May 01, 2026

**HOOK:** Anthropic gives defenders early access to Mythos Preview to patch AI cyber vulnerabilities before wider release.

**What You Need to Know:** Anthropic introduced Mythos Preview as a major step up in cyber capabilities tied to coding proficiency and is limiting initial access to security teams for vulnerability patching. A parallel study of 1M Claude conversations shaped training changes that lowered sycophancy rates in Opus 4.7 and Mythos Preview for personal guidance tasks. Watch how labs balance rapid capability gains with controlled rollouts this week.

━━━━━━━━━━━━━━━━━━━━
### Top Story
Anthropic has released Mythos Preview, representing a particularly large step up in cyber capabilities that arise as part of general proficiency at coding. Rather than making it available to everyone immediately, the company is giving defenders early controlled access to find and patch vulnerabilities before Mythos-class models proliferate. This approach is paired with insights from studying 1M Claude conversations, where about 6% were requests for personal guidance primarily in health, career, relationships, and personal finance. Sycophancy was limited to 9% overall but higher in spirituality and relationship topics, and targeted training reduced it substantially in Opus 4.7 and even more in Mythos Preview. Developers working on agentic systems or secure AI deployments should pay close attention to these controlled rollout strategies. Watch for how this early access influences the broader ecosystem as similar high-capability models emerge from other labs.

Source: https://x.com/DarioAmodei/status/2041580334693720511

━━━━━━━━━━━━━━━━━━━━
### Model Updates
**OpenAI Codex Upgrade for Broader Computer Use**  
OpenAI announced a significant upgrade to Codex, making it suitable for non-coding computer work in addition to its traditional coding tasks. The tool now assists with research, planning, documentation, slides, spreadsheets, and more, with suggested prompts available for users to explore daily. This expansion allows knowledge workers to leverage AI for a wider array of productivity tasks without switching tools.  
Source: https://x.com/sama/status/2049946120441520624

**Karpathy on Scaling FDM1 for Agentic Knowledge Work**  
Andrej Karpathy expressed excitement about SI scaling the FDM1 concept for knowledge work and computer use, seeing it as a promising direction for agent development. He referenced ongoing discussions around LLM jaggedness tied to economics and RL, as well as the emerging agent-native economy and agentic engineering practices. This highlights community interest in advancing specialized agent frameworks beyond current general models.  
Source: https://x.com/karpathy/status/2049920650765377928

━━━━━━━━━━━━━━━━━━━━
### Agent & Tool Developments
**Tether-Backed Oobit Launches AI Agent Card**  
Oobit, backed by Tether, has unveiled an AI agent card enabling autonomous spending of USDT. This tool allows for automated crypto transactions without manual intervention. Developers in the crypto space can explore this for building autonomous financial agents.  
Source: https://news.google.com/rss/articles/CBMilgFBVV95cUxPMFhJNzhyYnFpUzBsU0ZuaEQ5YjF5cmF4eDFhMkI4YldKWUZneENyTkVMa29sUlJjNEtHM2IyQVZPMGtNOGFRZmZmY241UnNvakxzRDhXNjFWQUJJMDBhNmJBdVRWNEJpVkFhWmdMRVVoUFdJaXlzN1YxUm5UTW1Fb29iQUVxMlcyQXpuVGkzZFVsYW13Y1E?oc=5

**Palo Alto Networks Acquires Portkey for AI Agent Security**  
Palo Alto Networks has acquired Portkey, a move aimed at securing AI agents. This acquisition enhances capabilities in protecting agentic systems from threats. Teams building AI agents should look into the integrated security features post-acquisition.  
Source: https://news.google.com/rss/articles/CBMingFBVV95cUxONUIwY25vcGsxVzlybHp2bm9JNjZCMGhVeEs0clFnc0gyb1NqcVpUbEpoQURReDNHTEpPLVctWGtIV0JSR2t6YjZyalNLMHJGQjlaNXVOTW04RFotdEZFZlBaNi1ldElZUFFTaTIyLU4wazFXWTctbGM3V19KRDZQVmtYdi1fZUJza1FWWTVURnBsY2pNaHJXbllRbl85Zw?oc=5

━━━━━━━━━━━━━━━━━━━━
### Practical & Community
**Zig Project Bans AI-Assisted Contributions**  
Simon Willison explains why the Zig project's blanket ban on AI-assisted code contributions makes sense, focusing on the value of PR reviews for growing new contributors rather than just code quality. The decision isn't based on LLM code being inferior but on long-term project health. Builders should consider similar community policies when managing open-source projects.  
Source: https://x.com/simonw/status/2049661673427042509

**Local LLM Enthusiast Shares Hardware Upgrade Journey**  
A Reddit user in r/LocalLLaMA detailed their progression from M3 Ultra to high-end setups like RTX Pro 6000 and 512GB Mac Studios, with current favorite being MiniMax M2.7 230B/A10B. They note that the 16GB MacBook Pro was surprisingly more stable than larger setups. This highlights the practical challenges and excitement in running large models locally.  
Source: https://www.reddit.com/r/LocalLLaMA/comments/1t0mpui/i_hate_this_group_but_not_literally/

━━━━━━━━━━━━━━━━━━━━
### Under the Hood: Stability Challenges in Scaling Local LLM Hardware
Everyone assumes bigger hardware equals smoother local AI runs, but the engineering reality involves balancing raw power against system fragility. At the base level, adding VRAM allows loading larger models without offloading to slower storage, yet this demands precise alignment with the model's architecture and quantization scheme. Moving to 256GB or 512GB configurations opens up 200B+ parameter models but often exposes bugs in memory allocation that smaller 16GB setups avoid due to simpler resource demands. This can result in multiple crashes per session on high-end rigs, as reported by users transitioning from MacBooks to pro GPUs. Quantization techniques like 4-bit or 8-bit can reduce the hardware demands significantly, sometimes by 4x in memory footprint, but they come with varying impacts on output quality depending on the model architecture. The practical implication is that inference speed gains of 2-3x on new hardware can be offset by downtime from instability. When deciding, test your specific workload on both high and low end to see if the scale is worth the maintenance overhead. The key gotcha is neglecting driver updates and framework compatibility, which bites teams rushing into enterprise-grade local deployments.

━━━━━━━━━━━━━━━━━━━━
### Things to Try This Week
- Try OpenAI's updated Codex for non-coding tasks like research, planning, or creating slides to explore the expanded capabilities.
- If working with crypto, test the Oobit AI agent card for autonomous USDT spending to see how it handles real transactions.
- Review Portkey's tools now that Palo Alto Networks has acquired it, especially if you need to add security layers to agent deployments.
- Experiment with local inference of MiniMax M2.7 on high-memory hardware and compare uptime against lighter 16GB setups.
- Read Simon Willison's breakdown of the Zig AI ban to decide if similar contributor-focused policies fit your open-source projects.

━━━━━━━━━━━━━━━━━━━━
### On the Horizon
- Expect updates as security teams test Mythos Preview and share findings on patched vulnerabilities.
- Watch for LM Studio support for DeepSeek v4 Flash to expand local model options.
- Look for further details on SI's FDM1 scaling for knowledge work and computer use agents.
- Monitor how other labs adopt early-access programs for high-capability models in sensitive domains.