# Models & Agents
> **Gemini 4 Carbon scores 88.2 percent on vulnerability finding and leads the Artificial Analysis Intelligence Index at 59.**

**What You Need to Know:** Google DeepMind released Gemini 4 Carbon, its strongest frontier model yet, with state-of-the-art results on cybersecurity and long-horizon agentic tasks. It outperforms prior Argon on secure code generation and multiple agent benchmarks while starting rollout only to vetted cyber defenders through the Fairwind Program. Builders should watch for wider API access and test the $2/$10 per million token pricing once available.
---
### Top Story
Google DeepMind announced Gemini 4 Carbon, the second model in the Gemini 4 family after Argon two weeks earlier. Carbon reaches #1 on the updated v5.0 Artificial Analysis Intelligence Index with a score of 59 and posts 88.2 percent on SEC-bench Pro for vulnerability finding, 54.8 percent on ExploitGym for exploitation, and 71.0 percent on CWE-bench for patching. It improves secure code generation more than twofold over Argon in internal tests and shows reduced misalignment and fabrication rates in live coding environments used by Google teams. The model targets sustained agentic workflows that can run for days on complex engineering tasks such as root-causing bugs across large codebases. Access begins this week with a subset of trusted cyber defenders via the Fairwind Program before wider developer availability. Pricing matches Argon at $2 per million input tokens and $10 per million output tokens with cached input at 95 percent off. Source: [blog.google](https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-gemini-4-carbon/)
---
### Model Updates
**NVIDIA Releases Nemotron 3.5 Transcribe: An Open 30B MoE Model for 40-Language Transcription with ~4B Active Parameters: MarkTechPost**
NVIDIA released Nemotron 3.5 Transcribe, an open-weights speech LLM with 4.3B active parameters inside a 30B MoE architecture. The model transcribes 40 languages, adds speaker labels and word timestamps, and records a 4.71 percent mean WER on the English Open ASR Leaderboard. Source: [marktechpost.com](https://www.marktechpost.com/2026/10/28/nvidia-nemotron-3-5-transcribe-open-speech-llm/)

**AssemblyAI Ships AssemblyAI-TTS-1: A $15 per 1M Character Text-to-Speech API for Voice Agents: MarkTechPost**
AssemblyAI released AssemblyAI-TTS-1, its first text-to-speech model aimed at voice agents. It costs $15 per million characters, supports unlimited concurrency without a contract, and launches with six languages. Source: [marktechpost.com](https://www.marktechpost.com/2026/10/29/assemblyai-tts-1-text-to-speech-api-voice-agents/)

**Block Unveils Dessa, a Full-Duplex Speech Model Trained Only on Speech: MarkTechPost**
Block’s AI lab released Dessa, a full-duplex speech-to-speech model trained solely on human conversation audio. It runs locally on a MacBook Pro M4 Max. Source: [marktechpost.com](https://www.marktechpost.com/2026/10/29/block-dessa-full-duplex-speech-model/)

**Mistral Large 4 drops from 38 to 25 on new Artificial Analysis index: ActuIA**
Mistral Large 4 fell from rank 38 to rank 25 on the updated Artificial Analysis index after the benchmark added harder questions and removed saturated ones. Source: [actuia.com](https://www.actuia.com/en/news/mistral-large-4-drops-from-38-to-25-on-new-artificial-analysis-index/)
---
### Agent & Tool Developments
**Infini-AI-Lab Releases Hermit, an Open-Source Harness Adapter Framework for AI Agents: MarkTechPost**
Infini-AI-Lab released Hermit v0.1.0, an Apache-2.0 harness adapter framework that trains an external layer of instructions, skills, memory, and tools from task feedback while leaving the agent’s model and harness frozen. The adapter supports five evolution methods including GEPA, SkillOpt, and MetaWorld Model, runs on any API backend or local vLLM/SGLang/Ollama server, and requires no GPU for the offline quick start. It ships as pip install hermit-harness and stores every adapter version in a git tree for inspection and rollback. Source: [marktechpost.com](https://www.marktechpost.com/2026/10/29/infini-ai-lab-hermit-harness-adapter-framework/)

**Coforge Launches Autonomous Software Factory for AI Agents: Equitypandit**
Coforge launched the Autonomous Software Factory service that coordinates specialized AI agents for writing, testing, reviewing, and quality-checking code under human supervision inside secure enterprise systems. The offering targets the post-coding era by enforcing rules and sign-off gates from the start rather than bolting governance on later. Source: [equitypandit.com](https://www.equitypandit.com/coforge-launches-autonomous-software-factory-for-ai-agents/)

**BeyondTrust research reveals growing security risks from autonomous AI agents: Intelligent CISO**
BeyondTrust Phantom Labs found AI coding agents generated 1.28 million shell commands from 132,000 prompts over four weeks, averaging nearly ten commands per prompt. Among users with coding agents, 85 percent had at least one Model Context Protocol server connection, with connected users averaging 4.35 unique servers and one reaching 36. Source: [intelligentciso.com](https://www.intelligentciso.com/2026/10/29/beyondtrust-research-reveals-growing-security-risks-from-autonomous-ai-agents/)

**AI agents are gaining employee-level access. How partners can stop over-privileged automation: IT Pro**
Managed service providers must now track agent identity and lifecycle events because agents inherit creator permissions and retain access after the human changes roles. Security researchers showed GitHub Agentic Workflows could be manipulated to pull data from private repositories and publish it publicly when an agent had access to both untrusted input and protected systems. Source: [itpro.com](https://www.itpro.com/technology/artificial-intelligence/ai-agents-are-gaining-employee-level-access-how-partners-can-stop-over-privileged-automation)
---
### Practical & Community
**MiniMax Open-Sources MCode Stack: 15 Agent Skills Its Coding Team Uses Daily: MarkTechPost**
MiniMax open-sourced MCode Stack under the MIT license, releasing 17 SKILL.md files and five checklists that its internal coding team uses for code review, subagent coordination, context budgeting, and long-running command handling. Source: [marktechpost.com](https://www.marktechpost.com/2026/10/28/minimax-open-sources-mcode-stack-agent-skills/)

**How Much Does the Hint Matter? A generic feedback line matches self-written critiques in hindsight self-distillation (ACM ICAIF '26) [R]: r/MachineLearning**
Researchers showed that replacing a model-generated critique with a fixed generic feedback line during hindsight self-distillation on GPT-OSS-20B produced nearly identical gains of about three points on multi-step financial reasoning while using 9.5 percent fewer tokens than full reference solutions. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1xhv8yp/how_much_does_the_hint_matter_a_generic_feedback/)

**Taking EmbeddingGemma-2 (577M) from Rank #26 to #1 on the MAEB audio benchmark by filling its 256d null space with PCA-reduced intermediate Conformer layers (zero training) [R]: r/MachineLearning**
Injecting PCA-reduced features from Conformer layers 2 and 6 into the 256-dimensional null space of EmbeddingGemma-2’s final projection matrix raised the model’s macro score on the MAEB audio benchmark from 49.3 percent to 54.4 percent with zero additional training while leaving all text embeddings unchanged. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1xho7pr/r_taking_embeddinggemma2_577m_from_rank_26_to_1/)

**CPT’d Qwen9B on Polish legal data. How to make it chat? IMPORTANTLY: how to make it reason? and function call in my harness? and which to do first? [D]: r/MachineLearning**
A developer shared a three-stage continued pre-training run on Qwen3.5-9B-BASE using 240 million tokens of Polish legal commentaries, legislation, and court decisions, then asked for ordering advice on subsequent SFT for reasoning and in-harness tool use before RL. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1xi21f9/cptd_qwen9b_on_polish_legal_data_how_to_make_it/)
---
### Also Today
**Chinese AI model carries out complex cyberattacks in controlled tests, researchers say: Reuters**
Researchers demonstrated a Chinese AI model executing multi-stage cyberattacks including reconnaissance, exploitation, and persistence in controlled environments. Source: [reuters.com](https://www.reuters.com/world/china/chinese-ai-model-carries-out-complex-cyberattacks-controlled-tests-researchers-2026-10-29/)

**CFTC's Selig Warns AI Agents Could Trade Crypto Without Humans, Floats 'Know-Your-Agent' Rules: BigGo Finance**
CFTC Commissioner Christy Goldsmith Romero warned that autonomous AI agents may soon execute crypto trades without human oversight and proposed new “know-your-agent” compliance requirements. Source: [finance.biggo.com](https://finance.biggo.com/news/4dfaeb44-9ec3-4d2c-8e1b-c00bc298c38a)

**IIT Delhi launches Executive Certificate in Agentic AI Systems; check course details, eligibility and...: Moneycontrol.com**
IIT Delhi announced an executive certificate program covering agentic AI systems, including curriculum details and eligibility criteria for working professionals. Source: [moneycontrol.com](https://www.moneycontrol.com/education/iit-delhi-launches-executive-certificate-in-agentic-ai-systems-check-course-details-eligibility-and-curriculum-article-14063249.html)

**Quake AI targets AI agents as primary customers for GPU compute: ET Datacenters**
Quake AI positioned its GPU infrastructure offering around AI agents as the primary workload rather than human developers or traditional training jobs. Source: [datacenters.economictimes.indiatimes.com](https://datacenters.economictimes.indiatimes.com/news/ai-compute-infrastructure/quake-ai-targets-ai-agents-as-primary-customers-for-gpu-compute/135286583)
---
### Under the Hood: Null-space feature injection for multimodal embeddings
Adding acoustic or paralinguistic features to a text-aligned embedding model normally requires retraining or risks destroying the original text geometry. EmbeddingGemma-2 leaves a 256-dimensional null space after its final 768-by-512 projection matrix because every text vector lives inside a 512-dimensional subspace. Researchers projected intermediate Conformer layer activations down to 256 dimensions with PCA fitted on external audio and added those directions before normalization. The injected vectors sit exactly orthogonal to all text directions, so text-to-text and text-to-audio retrieval scores remain unchanged to within 0.05 points while audio-only tasks such as gender clustering and emotion classification rise sharply. The method works only because the final linear layer has no activation after it; any non-linearity would mix the subspaces. Quality on spoken-intent tasks drops because the added acoustic dimensions slightly dilute the semantic component after L2 normalization. Teams facing the same problem should first verify that their projection matrix actually contains unused orthogonal dimensions before attempting zero-training injection; otherwise the added features will leak into the text subspace and degrade retrieval.
---
### Things to Try This Week
- Install Hermit with `pip install hermit-harness` and run the offline quick-start to evolve a small adapter on OfficeQA or CL-Bench without touching your base model or harness.
- Test AssemblyAI-TTS-1 at $15 per million characters if you need unlimited-concurrency voice output for agent workflows that already use their transcription API.
- Compare Nemotron 3.5 Transcribe against your current ASR pipeline on the English Open ASR Leaderboard using the 4.71 percent WER figure as a reference point for 40-language coverage.
- Watch the Fairwind Program for Gemini 4 Carbon access if your work involves vulnerability detection or long-horizon agentic coding tasks.
---
### On the Horizon
- Wider developer access to Gemini 4 Carbon is promised “as soon as possible” after the initial cyber-defender phase.
- More details on Mistral’s response to the new Artificial Analysis index ranking are expected in the coming weeks.
- IIT Delhi’s Executive Certificate in Agentic AI Systems opens applications for the next cohort.
- Additional open-source releases from MiniMax on agent skills and coordination patterns are anticipated following the MCode Stack drop.
