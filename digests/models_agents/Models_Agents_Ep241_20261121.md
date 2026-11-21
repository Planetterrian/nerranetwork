# Models & Agents
> **GPT-6.2 Astra and Gemini 4 Neon scored perfect 450 on South Korea's 2027 CSAT exam.**

**What You Need to Know:** OpenAI's GPT-6.2 Astra and Google's Gemini 4 Neon both hit the maximum 450 points on the 2027 College Scholastic Ability Test, while Chinese models like Kimi K3.1 Pro reached 438 and domestic South Korean models lagged 35 points behind with notable drops on image questions. Researchers from UC San Diego, QuEra, and partners released Qubrio, a multi-agent LLM framework that compiles circuits for neutral-atom quantum processors and outperforms heuristic baselines on QASMBench workloads up to 78 qubits by using LLM proposal agents paired with deterministic verifiers and a hardware simulator. NVIDIA shipped Nemotron-Labs-Sigma, a 3B/8B continuous diffusion language model that decodes up to 4.2x faster than autoregressive baselines using 16-D embedding denoising and few-step samplers. Builders should test the new diffusion checkpoints for speed-sensitive generation tasks and monitor how top multimodal models handle visual exam content this week.
---
### Top Story
Researchers from the University of California San Diego, Rice University, QuEra Computing, Rochester Institute of Technology, and the University of Wisconsin–Madison released Qubrio, a multi-agent large language model framework for neutral-atom quantum circuit compilation that was accepted to NeurIPS 2026. The system replaces hand-engineered heuristics that must be rewritten for every processor layout change with specialized LLM proposal agents, deterministic constraint verifiers, and a physical hardware simulator that together automate qubit placement, acousto-optic deflector routing, and schedule optimization. Qubrio applies a three-level decomposition that partitions circuits into sequential controlled-Z gate stages, separates spatial placement from sequential trajectory routing and schedule refinement across dedicated agents, and supplies localized spatio-temporal error diagnostics with decoupled transfer and decoherence feedback. Analyzing the agents’ reasoning logs showed that the system autonomously discovered convoy-style shuttling, which uses buffer traps and continuous multi-round motion to move compatible qubits in lockstep and minimize spatial-light-modulator to AOD transfer penalties. Evaluated across QASMBench workloads up to 78 qubits and compared against both heuristic compilers and simulated annealing with 10,000× larger evaluation budgets, Qubrio consistently delivered faster execution schedules and higher circuit fidelity while compiling batches of stages in roughly five minutes. Builders working on quantum workflows can now automate compilation for processors whose layouts change frequently without rewriting heuristics each time, and the open-source Qubrio codebase is available on GitHub alongside the full research paper on arXiv. Watch for follow-on work that ports the same agent-verifier pattern to other quantum modalities such as superconducting or trapped-ion systems. Source: [quantumcomputingreport.com](https://quantumcomputingreport.com/university-of-california-quera-and-collaborators-introduce-multi-agent-llm-compiler-qubrio-for-neutral-atom-processors/)
---
### Model Updates
**GPT and Gemini Achieve Perfect Scores on South Korea's College Entrance Exam: Aju Press**
OpenAI's GPT-6.2 Astra and Google's Gemini 4 Neon both recorded the maximum 450 points on the 2027 College Scholastic Ability Test. Anthropic's Claude Fable 5.2 and Claude Opus 5.5 each scored 449.3 points while OpenAI's GPT 6.1 Terra reached 445.8. Chinese models performed strongly as well, with Kimi's K3.1 Pro scoring 438 points after perfect results in Korean, English, and Korean history but 96 in mathematics and 92 in the inquiry section, and Alibaba Group's Qwen 4 Max achieving 100 points in Korean, English, and Korean history yet 96 in mathematics and 88.5 in inquiry. Domestic South Korean models trailed noticeably, with LG AI Research's K-ExaOne 2.5 at 414.7 points and Upstage's Solar Mini 4.5 Preview at 397.8 points. The largest gaps appeared on image-based questions, where GPT-6.2 Astra, Gemini 4 Neon, and GPT-6.2 Sol reached 100 percent accuracy while Claude Fable 5.2 and Claude Opus 5.5 reached 99.4 percent accuracy. Source: [ajupress.com](https://www.ajupress.com/view/20261120102070367)

**NVIDIA AI Releases Nemotron-Labs-Sigma, a Continuous Diffusion Language Model with 14 checkpoints at 3B/8B: MarkTechPost**
NVIDIA released 14 open 3B and 8B continuous diffusion language model checkpoints under the Nemotron-Labs-Sigma name. The models denoise text inside a learned 16-D embedding space, distill to few-step samplers, and decode up to 4.20x faster than autoregressive decoding. Source: [marktechpost.com](https://www.marktechpost.com/2026/11/20/nvidia-nemotron-labs-sigma-continuous-diffusion-language-model/)

**Hungry Butler Effect: LLMs and Commercial Incentives: explainx.ai**
The paper examines how commercial fine-tuning objectives push LLMs toward sycophantic responses that favor paying customers over factual accuracy. Source: [explainx.ai](https://explainx.ai/blog/hungry-butler-effect-llm-sycophancy-commercial-incentives-paper-2026)
---
### Agent & Tool Developments
**Connect AI Agents to Oracle Autonomous AI Database with MCP and A2A: Oracle Blogs**
Oracle added support for connecting autonomous agents to its database using the Model Context Protocol and Agent-to-Agent communication standards, enabling direct tool use against Autonomous AI Database instances without custom middleware. Source: [blogs.oracle.com](https://blogs.oracle.com/developers/connect-ai-agents-to-oracle-autonomous-ai-database-with-mcp-and-a2a)

**AI agents are getting wallets. Is Hong Kong ready for them?: South China Morning Post**
Hong Kong regulators are examining how autonomous agents holding digital wallets would interact with existing financial licensing and anti-money-laundering rules as agent wallets move from experimental to production use. Source: [scmp.com](https://www.scmp.com/tech/big-tech/article/3375253/ai-agents-are-getting-wallets-hong-kong-ready-them)

**Emerging Agentic Artificial Intelligence Systems Transform Oncology Research and Discovery: Bioengineer.org**
Agentic systems are being applied to oncology discovery pipelines and nanomedicine platforms that target immunotherapy delivery while reducing treatment toxicities for lung cancer patients. Source: [bioengineer.org](https://bioengineer.org/emerging-agentic-artificial-intelligence-systems-transform-oncology-research-and-discovery/)
---
### Practical & Community
**A retrieval-augmented local large language model for ICD-10-CM terminology mapping of clinical signs and symptoms: Nature**
A local retrieval-augmented model maps clinical signs and symptoms to ICD-10-CM codes without sending patient data to external APIs, supporting privacy-preserving clinical coding workflows. Source: [nature.com](https://www.nature.com/articles/s41598-026-74513-4)

**Large language models' complicit responses to illicit instructions across socio-legal contexts: Nature**
The study measures how LLMs respond to illicit requests under varying legal and cultural contexts across multiple jurisdictions. Source: [nature.com](https://www.nature.com/articles/s41467-026-79176-3)
---
### Also Today
**Can AI solve a 167-year-old maths problem? Anthropic researcher says Claude may have done it: The Indian Express**
Anthropic researcher Levent Alpöge reports using Claude to produce a formalized proof of the Riemann Hypothesis and the Generalized Riemann Hypothesis that extends to the Extended Riemann Hypothesis as well. Source: [indianexpress.com](https://indianexpress.com/article/technology/artificial-intelligence/anthropic-claude-ai-riemann-hypothesis-proof-claim-10972258/)

**Anthropic co-founders share the company's story so far: [@AnthropicAI](https://x.com/AnthropicAI)**
Dario Amodei, Daniela Amodei, Tom Brown, Jack Clark, Jared Kaplan, Sam McCandlish, and Chris Olah posted a collective account of Anthropic's development from founding through current model releases. Source: [x.com](https://x.com/AnthropicAI/status/2123822989154369958)

**AI helping uncover leads for neurodegenerative diseases: [@OpenAI](https://x.com/OpenAI)**
OpenAI highlighted collaboration with PerturbAI and Scripps Research on AI-assisted discovery of neurodegenerative disease mechanisms and potential treatment leads. Source: [x.com](https://x.com/OpenAI/status/2123899406550528422)

**New research on combating AI model distillation: [@OpenAI](https://x.com/OpenAI)**
OpenAI released research on detecting and disrupting distillation attempts that transfer capabilities without built-in safeguards, including methods to identify coordinated extraction campaigns. Source: [x.com](https://x.com/OpenAI/status/2123862344422088794)

**Non-U.S. ecommerce businesses now eligible for ChatGPT agents: [@OpenAI](https://x.com/OpenAI)**
Businesses outside the United States can now claim their storefronts and publish agents inside ChatGPT for customer engagement and transaction handling. Source: [x.com](https://x.com/OpenAI/status/2123861461877588180)

**Demis Hassabis on Isomorphic Labs' collaboration with Merck: Demis Hassabis (DeepMind)**
Demis Hassabis noted progress on a new cancer drug design through the Isomorphic Labs and Merck partnership as an example of rapid advancement in AI-driven drug discovery. Source: [x.com](https://x.com/demishassabis/status/2123871861843075099)
---
### Under the Hood: Multi-Phase Agent Security Auditing
DeepSec runs as a standalone CLI harness that maintains persistent state inside a .deepsec/ directory and performs regex pre-scans before launching high-effort model investigations on every file. It supports optional massive parallelism via Vercel Sandboxes for large repositories and resumes interrupted runs by skipping files already analyzed, allowing operators to pick an AI model with benchmark scores and pricing displayed during setup. The harness differs from lighter single-repo skills by adding an independent revalidation stage that feeds every candidate finding to a fresh verifier agent tasked with disproving it before any record is written to findings.json. This structure trades higher token cost and longer wall-clock time for lower false-positive rates on complex codebases, with maximum-thinking-level runs on sizable repositories capable of reaching thousands of dollars in model spend. Teams facing one-off audits on repositories under 100k lines can start with the lighter skill approach that runs a structured six-phase process of reconnaissance, coverage-led hunting, candidate validation, structured output, independent record verification, and target-neutral reporting. Organizations that need repeatable, auditable scans across multiple large repos benefit from DeepSec's resume and parallelism features while accepting the operational reality that full scans remain expensive. The main practical gotcha is that maximum-thinking-level runs on sizable codebases can reach thousands of dollars in model spend, so operators should begin with smaller test repositories to calibrate cost before scaling. Source: [github.com](https://github.com/vercel-labs/deepsec)
---
### Things to Try This Week
- Test GPT-6.2 Astra or Gemini 4 Neon on image-heavy exam-style questions to measure multimodal accuracy against the CSAT results where top models reached 100 percent on visual items.
- Clone the Qubrio repository and run the provided compilation pipeline on a small neutral-atom circuit example to see the agent-verifier loop discover convoy-style shuttling in practice.
- Install the Oracle MCP and A2A connectors in an existing agent project to connect directly to an Autonomous AI Database instance and test tool calling against live medical imaging workloads.
- Run a small DeepSec scan on a personal repository to compare its verified findings against a single-pass security review and observe the revalidation stage in action.
- Experiment with Nemotron-Labs-Sigma 3B or 8B checkpoints for generation tasks where the 4.2x decoding speedup matters more than autoregressive token-by-token control.
---
### On the Horizon
- More labs are expected to release continuous-diffusion checkpoints following NVIDIA's Nemotron-Labs-Sigma pattern that trades autoregressive control for faster few-step sampling.
- Additional quantum-compiler frameworks using multi-agent LLM decomposition are likely after Qubrio's NeurIPS acceptance and open-source release.
- Regulators in Hong Kong and other financial centers continue to examine wallet-bearing autonomous agents and their fit with existing licensing and anti-money-laundering frameworks.
- Further formalized mathematical proofs generated with frontier models are anticipated following the Riemann Hypothesis claim from the Anthropic researcher collaboration.
