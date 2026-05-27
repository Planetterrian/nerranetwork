# Models & Agents
> **Anthropic just published concrete sandboxing patterns that let agents scale capabilities without expanding their blast radius.**

**What You Need to Know:** Anthropic released a detailed engineering post on how they contain Claude agents through evolving access controls and sandbox limits. EAGLE 3.1 fixes attention drift in speculative decoding for more stable production inference. Several new agent frameworks and training methods for reasoning agents also dropped today.
---
### Top Story
Anthropic published a new engineering blog post detailing their approach to sandboxing AI agents. The post explains that permissions must evolve alongside agent capabilities, with sandboxing used to limit the scope of potentially destructive actions in their products. This provides practical guidance on containing agents as they gain more autonomy rather than relying on static rules. Builders working with tool-using agents can apply these patterns to reduce risk when granting file system, network, or code execution access. The approach emphasizes starting with narrow permissions and expanding them only as the agent's demonstrated reliability increases. Watch for similar sandbox designs from other labs as agent deployments move beyond prototypes. Source: [anthropic.com](https://www.anthropic.com/engineering/how-we-contain-claude)
---
### Model Updates
**EAGLE 3.1: MarkTechPost**
The EAGLE team, vLLM, and TorchSpec released EAGLE 3.1 to address speculative decoding instability during production inference. The update specifically targets attention drift that previously caused inconsistent draft token acceptance rates. Teams running high-throughput inference pipelines can integrate the new algorithm to reduce variance in latency without changing their base model. The release focuses on production robustness rather than raw speed gains. Builders should test the updated speculative decoding path if they currently see fluctuating acceptance rates on long contexts.

**Self-Verified Distillation: arXiv**
Researchers introduced Self-Verified Distillation, a post-training method where models generate, self-verify, and train on their own solutions using only unlabeled prompts. The approach applies three-stage filtering (cycle-consistency, factuality, correctness) and was tested on Qwen3 models across math, science, and coding domains. Qwen3-4B showed gains of +16.7 points on math benchmarks, +11.1 on science, and +8.3 on coding after the process. The method requires only a single inference call at test time. Teams fine-tuning smaller models should experiment with this self-curation pipeline when labeled data is scarce.

**MicroSpec: arXiv**
MicroSpec introduces a training-free method that builds compact, context-sensitive vocabularies on the fly for speculative decoding. It reduces average vocabulary size by more than 40x (under 3k tokens) while maintaining coverage through temporal locality in generation. The system achieves 51.6% lower draft latency and 1.12-1.32x end-to-end speedup over EAGLE-2 on benchmarks. It works as a plug-and-play addition to existing speculative decoding setups. Inference teams should evaluate it when vocabulary projection is the current bottleneck.
---
### Agent & Tool Developments
**VTCode Rust TUI coding agent: r/LocalLLaMA**
A new open-source Rust TUI coding agent called VTCode uses AST-level chunking and explicit token budget tracking to avoid dumping entire directories into prompts. It supports macOS Seatbelt, Linux Landlock, and seccomp sandboxing plus tree-sitter validation on every generated command. The agent works with any OpenAI-compatible provider and includes a config example for routing through third-party endpoints like DeepSeek V4 Flash. It is MIT licensed. Developers tired of token waste in agent coding sessions should try the repo at https://github.com/vinhnx/VTCode.

**Hyvemind OSS: r/LocalLLaMA**
Hyvemind is a desktop app combining three AI-assisted development modes: focused task planning, concurrent multi-model review (Hivemind), and fully autonomous multi-feature execution (Swarms). It supports a wide range of providers including Anthropic, OpenAI, Ollama, DeepSeek, and NVIDIA NIM. The project is seeking testers before a full public release and is available on GitHub at https://github.com/Unravl/Hyvemind. Users can export and reuse swarm plans across different model compositions. Teams building internal agent workflows should request access via the linked Discord.

**SPEAR prompt optimizer: arXiv**
SPEAR (Sandboxed Prompt Engineer with Active Roll-back) turns automatic prompt engineering into an agentic process with four tools including a Python sandbox for structural error analysis. It outperformed prior methods on 13 industrial LLM-as-judge tasks and seven BBH tasks, with the Python tool providing the largest single contribution on complex judge tasks. Auto-rollback prevents metric regression during optimization. The system is designed for long-horizon prompt improvement without human intervention. Prompt engineers working on evaluation pipelines should test the agentic approach on their judge tasks.
---
### Practical & Community
**Conv-to-Bench evaluation framework: arXiv**
Conv-to-Bench automatically converts real multi-turn user-assistant dialogues into structured, verifiable requirement checklists for model evaluation. Applied to programming tasks, it produces benchmarks that achieve near-perfect Spearman correlation with human-authored sets like BigCodeBench while requiring far less manual curation. The LLM-as-judge component reached substantial agreement with human ground truth (κ = 0.705). The framework reduces the cost of maintaining high-quality evaluation sets as models evolve. Evaluation teams should examine the pipeline for their own domain-specific benchmarks.
---
### Under the Hood: Speculative Decoding Stability
Everyone talks about speculative decoding as a simple speed trick. In practice, it is a delicate balance between draft model quality, acceptance criteria, and attention stability across layers. The core mechanism works by letting a smaller draft model propose multiple tokens that the target model then verifies in parallel, but attention drift occurs when the draft model's hidden states diverge from what the target would have produced at the same positions. This divergence grows with sequence length because each accepted token slightly shifts the key-value cache the target model sees on the next verification step. EAGLE 3.1 and similar fixes add lightweight correction terms or re-normalization steps to keep the draft distribution aligned, at the cost of a small amount of extra compute per verification round. The practical tradeoff is that these corrections buy back 10-20% acceptance rate on long contexts while adding roughly 5-8% overhead to the verification pass itself. When to use the stabilized version: any production workload where tail latency matters more than average throughput; skip it for short, bursty requests where the drift never has time to accumulate.
---
### Things to Try This Week
- Test EAGLE 3.1 in your vLLM setup if speculative decoding acceptance rates have been drifting on contexts over 8k tokens.
- Clone VTCode and run it against a local DeepSeek endpoint to measure token savings on a real refactor task.
- Apply Self-Verified Distillation to a 4B or 8B Qwen3 model on your domain-specific unlabeled prompts before the next fine-tuning cycle.
- Experiment with SPEAR's Python sandbox tool on an existing LLM-as-judge task to see how structural error analysis changes prompt quality.
---
### On the Horizon
- More labs are expected to release detailed sandboxing and permission frameworks as agent deployments move into production environments.
- Additional papers on agent credit assignment and retrieval-aware training are likely following the RICE-PO and SPEAR releases.
- Open-source coding agents with stronger AST-aware context management will continue appearing on GitHub as teams share their internal tools.