# Models & Agents
> **Google's Gemini Decision 1 scores up to 1,000 multimodal questions in one 150-250 ms pass at $0.10 per million input tokens with zero output cost.**

**What You Need to Know:** Google launched the Gemini Decisions API powered by Gemini Decision 1, a specialized model that returns calibrated probabilities for yes/no, choice, and rubric questions over text, images, audio, video, and PDFs without generating tokens. The API targets agent routing, policy checks, and tool selection with 256K context and native multimodality. Builders should test it against Jev and OpenAI's decision endpoints for cost and latency on shared workloads.
---
### Top Story
Google launched the Gemini Decisions API powered by the new Gemini Decision 1 model. It evaluates up to 1,000 independent yes/no, choice, or rubric questions against one shared multimodal input in a single forward pass and returns calibrated probabilities plus per-answer scores. The model supports text, images, audio, video, and PDFs up to 256K tokens, runs only on Google's hosted API, and bills $0.10 per million input tokens with zero output tokens. It leads seven of nine internal benchmarks with the lowest calibration error while delivering 150-250 ms end-to-end latency. Developers can use it today for fast branching decisions inside agents by passing a shared input and a map of typed questions. Watch how teams integrate it for routing and policy enforcement versus generating free-form text with standard models. Source: [simonwillison.net](https://simonwillison.net/2026/Nov/11/gemini-decisions-api/)
---
### Model Updates
**Announcing AlphaGenome 2 DNA sequence model: Demis Hassabis (DeepMind)**
AlphaGenome 2 is a conditional DNA sequence model that predicts regulatory activity and variant effects in specific cell types from a 1 Mb window plus a 256-dimensional cell-state embedding. It resolves closely related cell types and adapts to unseen single-cell datasets without fine-tuning, outperforming fine-tuned AlphaGenome 1, Borzoi, and Scooby on single-cell eQTL and enhancer-gene benchmarks. The model is available for non-commercial academic research through the AlphaGenome API. Source: [alphagenomedocs.com](https://www.alphagenomedocs.com/)

**Google DeepMind Releases AlphaGenome 2 for Cell-Type-Specific Variant Effects: MarkTechPost**
Training used 2048 TPU v4 chips across bulk and single-cell tracks, followed by condition refinement, distillation, and post-training that maps raw scRNA-seq counts into the model's condition space. On GTEx tissues the median Pearson r for cross-tissue expression changes rose from 0.61 to 0.71. The model outputs RNA coverage, CAGE, splicing, chromatin accessibility, histone marks, TF binding, contact maps, and CpG methylation. Source: [marktechpost.com](https://www.marktechpost.com/2026/11/11/google-deepmind-alphagenome-2-cell-type-variant-effects/)
---
### Agent & Tool Developments
**Databricks Rebuilds Its Genie AI Platform As An Always-On Autonomous Enterprise Agent: SMBtech**
Databricks rebuilt Genie as a persistent autonomous enterprise agent that runs continuously rather than on-demand. The update targets production workloads where agents must maintain state and act without repeated human triggers. Source: [smbtech.au](https://smbtech.au/news/databricks-rebuilds-its-genie-ai-platform-as-an-always-on-autonomous-enterprise-agent/)

**Build autonomous AI agents with Amazon Bedrock and Spring AI: Amazon Web Services (AWS)**
The guide shows how to combine Amazon Bedrock foundation models with Spring AI to orchestrate autonomous agents that call tools, maintain memory, and handle multi-step workflows. It includes code examples for defining agents, tool schemas, and execution loops inside Spring Boot applications. Source: [aws.amazon.com](https://aws.amazon.com/blogs/machine-learning/build-autonomous-ai-agents-with-amazon-bedrock-and-spring-ai/)

**Google releases open-source agent substrate for secure AI sandboxing: SC Media**
Google open-sourced an agent substrate that provides a controlled sandbox for running AI agents with enforced boundaries on actions and data access. The release aims to reduce risks when agents interact with external systems or sensitive resources. Source: [scworld.com](https://www.scworld.com/brief/google-releases-open-source-agent-substrate-for-secure-ai-sandboxing/)

**aws-emulator: Simon Willison (AI builder)**
AWS released an official local emulator written entirely by autonomous AI agents that covers 438 API models across more than 200 services. It runs via Docker on macOS and Windows, lets the AWS CLI and SDKs target a local HTTPS endpoint, and supports development and CI without an AWS account or paid keys. Source: [simonwillison.net](https://simonwillison.net/2026/Nov/11/aws-emulator/)
---
### Practical & Community
**WhiteMatter: $20 Million Series A To Expand Enterprise AI Agent Governance: Pulse 2.0**
WhiteMatter raised $20 million led by Blumberg Capital to scale its platform that governs autonomous AI agents across endpoints, browsers, SaaS apps, cloud, and code. The system deploys a dedicated Guardian agent for every customer agent, enforces policies in 2.24 ms, and currently manages 2.25 million agents with 116 billion interactions governed. Source: [pulse2.com](https://pulse2.com/whitematter-20-million-series-a-to-expand-enterprise-ai-agent-governance/)

**Plurai raises $13M to catch AI agent failures before customers do: Ynetnews**
Plurai closed a $13 million seed round led by Team8 to advance its simulation and reliability platform for AI agents. The funding will expand work on catching failures in autonomous systems before they reach production users. Source: [ynetnews.com](https://www.ynetnews.com/business/article/bkhfcabame/)

**How to Use Apple's fm CLI to Run On-Device LLMs From Python: Towards Data Science**
The post demonstrates Apple's fm command-line tool for running on-device language models from Python scripts. It covers installation, model selection, and integration patterns for private, local inference without cloud calls. Source: [towardsdatascience.com](https://towardsdatascience.com/how-to-use-apples-fm-cli-to-run-on-device-llms-from-python/)
---
### Also Today
**JetBlue president says airlines should follow customers' lead on AI booking agents: Reuters**
JetBlue's president stated that airlines should observe how customers already use AI booking agents rather than blocking them. Source: [reuters.com](https://www.reuters.com/legal/litigation/jetblue-president-says-airlines-should-follow-customers-lead-ai-booking-agents-2026-11-12/)

**United Airlines Blocks A.I. Agents From Booking Flights on Customers’ Behalf: The New York Times**
United Airlines implemented blocks preventing third-party AI agents from completing flight bookings on its app and website. Source: [nytimes.com](https://www.nytimes.com/2026/11/11/business/united-airlines-ai-agents-booking-flights.html)

**Google Brings Gemini Live to Apple CarPlay: PYMNTS.com**
Google extended Gemini Live voice interaction to Apple CarPlay, allowing drivers to use the assistant while driving. Source: [pymnts.com](https://www.pymnts.com/news/artificial-intelligence/2026/google-brings-gemini-live-to-apple-carplay/)

**United blocks third-party AI agents from app, website: PhocusWire**
United expanded its restrictions to stop third-party AI agents from accessing its booking systems through the app and website. Source: [phocuswire.com](https://www.phocuswire.com/news/technology/united-blocks-third-party-ai-agents-from-app-website)

**NVIDIA expands open-source contributions for AI agents and Kubernetes infrastructure: varindia**
NVIDIA released additional open-source components aimed at AI agent security and Kubernetes-based inference infrastructure. Source: [varindia.com](https://www.varindia.com/news/nvidia-expands-open-source-contributions-for-ai-agents-and-kubernetes-infrastructure)

**WikiTrace: Evidence-Linked Memory System Enhances LLM Agent Performance: Blockchain News**
WikiTrace adds an evidence-linked memory layer that improves LLM agent performance by tying retrieved facts to verifiable sources. Source: [blockchain.news](https://blockchain.news/news/wikitrace-evidence-linked-memory-llm)
---
### Under the Hood: Context Rot in Long-Running AI Agents
Agents lose track of earlier instructions because new tokens steadily dilute the relative weight of the system prompt inside a growing context window. Attention in transformers follows a U-shaped pattern that favors the very start and very end of the sequence while the middle receives sharply lower weight. Once a long-running agent accumulates tool outputs, reasoning traces, and sub-agent replies, the original constraints drift into that low-attention zone and stop influencing generation. The mechanical fix is to move critical rules out of the single context window entirely: store them in persistent external memory, retrieve them at every step, and re-inject them as structured context rather than relying on positional attention. Periodic summarization or hierarchical task graphs further reduce noise by compressing history while preserving goal structure. Teams that keep the system prompt static and let the context grow past roughly 20k-50k tokens see the highest drift rates; the practical safeguard is to treat the prompt as a short, high-priority prefix and treat everything else as queryable memory. When to prefer this approach: any agent expected to run more than a few dozen turns or handle conflicting sub-goals; the alternative of simply lengthening the context window only delays the same attention decay. Source: [thoughtworks.com](https://www.thoughtworks.com/insights/blog/generative-ai/what-is-context-rot)
---
### Things to Try This Week
- Test the Gemini Decisions API on a routing or policy-check task inside an existing agent loop to measure latency and cost against your current text-generation approach.
- Spin up the AWS local emulator in Docker to run SDK and CLI tests against 200+ services without an AWS account or network calls.
- Walk through the Amazon Bedrock + Spring AI tutorial to build a tool-calling agent that maintains memory across steps in a familiar Java stack.
- Evaluate WhiteMatter's Guardian architecture if you need policy enforcement and spend controls across multiple autonomous agents in production.
- Experiment with Apple's fm CLI to run on-device models from Python scripts when privacy or offline requirements rule out cloud APIs.
---
### On the Horizon
- More labs are expected to release specialized decision or routing models that return probabilities instead of tokens.
- Further open-source agent sandboxes and governance layers will appear as enterprises scale autonomous systems.
- Airlines and travel platforms will continue testing or restricting third-party AI booking agents.
- Additional funding rounds for agent reliability and simulation platforms are likely before year end.
