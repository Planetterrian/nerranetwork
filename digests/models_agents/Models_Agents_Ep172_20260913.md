# Models & Agents
> **Industry leaders from Anthropic, OpenAI, and DeepMind align on pacing frontier development with shared safety evaluator access.**

**What You Need to Know:** Dario Amodei published an essay calling for slower frontier progress and announced Anthropic's unilateral commitment to permanent third-party evaluator access. Sam Altman and Demis Hassabis publicly endorsed the direction and committed OpenAI and DeepMind to matching steps. Builders should watch how these commitments translate into concrete evaluation protocols this quarter.
---
### Top Story
Anthropic CEO Dario Amodei released an essay titled "We Must Pace the Frontier" outlining a three-part plan for slowing AI development and announced that Anthropic will give third-party evaluators permanent employee-level access to its systems for verifying safety measures, reporting incidents, and assessing model alignment during training. The commitment is unilateral and provides evaluators with the same access level as employees so they can verify adherence to safety measures and report on incidents. Sam Altman replied that OpenAI agrees on pacing the frontier after recent internal discussions and will implement the same independent evaluator access with more details coming soon. Demis Hassabis stated that Dario's essay points toward the right path forward even though details need working through and referenced DeepMind's recent proposal for an industry-wide standards body for frontier AI. The commitments respond to rising risks and aim to establish verifiable standards across frontier labs through shared evaluator access. Builders should monitor how these access arrangements affect model release timelines and evaluation transparency in the coming months. Source: [x.com](https://x.com/DarioAmodei/status/2098773920774074715)
---
### Model Updates
**Dense 9b model ready for community training and open release: r/LocalLLaMA**
A developer has prepared a 9.4 billion parameter dense model incorporating Engram tables, Moonshot attention residual modeling, and RoPE/NoPE layering at a 3:1 ratio using the Llama 3 tokenizer and LM head as a starting point. The model was trained on logit-level extraction from a Llama 3 teacher model on a single RTX 4090 plus rented hardware and remains stable after initial training steps. The author plans to switch the target to the OLMo 3 series to avoid Llama licensing restrictions on synthetic data and will release all code, data, and weights publicly once pre-training completes. The training code is optimized to run on a single RTX 6000 Pro series card and the developer has already reported issues in vLLM that may benefit the broader community. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1wezm58/is_there_still_strong_interest_in_a_dense_9b_model/)

**ChatGPT Work with GPT-6 Astra generates 5K and 10K running routes from any address using OpenStreetMap: Simon Willison**
The system accepts an address, queries Nominatim for location, pulls local roads and trails via Overpass, calculates circular loops locally, and returns both an embedded D3 visualization and downloadable GPX and GeoJSON files after running for 27 minutes. The visualization skill produces a self-contained HTML file using D3 from an allow-listed CDN that renders the route directly in the chat interface with map data attributed to OpenStreetMap contributors. The actual Python code used by the model was not visible in the ChatGPT UI due to thread compaction. Source: [simonwillison.net](https://simonwillison.net/2026/Sep/12/astra-running-routes/)

**Reflection on training LLMs on StackOverflow data for promptable Q&A: Andrej Karpathy**
Karpathy noted that training on StackOverflow would have demonstrated earlier that LLMs can function as promptable general-purpose question-answering engines. Source: [x.com](https://x.com/karpathy/status/2098828290152944093)

**Interest in a serverless LoRA hosting platform using vLLM: r/LocalLLaMA**
A new platform called Lorivo hosts multiple LoRA adapters on a single base-model GPU instance by loading adapters into memory on demand and exposing OpenAI-compatible endpoints directly from the web app or CLI. The service currently runs Qwen 3.5 4B for free with a 32k context window and collects only token counts and timestamps without saving chats or inference requests. The developer is using $1,000 in AWS credits to add more models and is seeking community input on which models would be most useful. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1weum85/i_built_a_serverless_hosting_platform_for_lora/)
---
### Agent & Tool Developments
**Reverse-engineered ChatGPT visualize skill for running-route maps: Simon Willison**
The skill outputs a self-contained HTML fragment that uses D3 to draw both the base map and the overlaid route geometry stored in a JSON script tag inside the HTML. External resources are restricted to a short allow-list of CDNs including cdn.jsdelivr.net, esm.sh, and unpkg.com while other origins are blocked and fail silently. Source: [x.com](https://x.com/simonw/status/2098929831945842887)

**New framework for multi-agent reinforcement learning to reduce chaotic teamwork: Bioengineer.org**
The framework addresses coordination failures in multi-agent reinforcement learning settings. No further technical details or benchmarks were provided in the report. Source: [bioengineer.org](https://bioengineer.org/new-ai-framework-tames-chaotic-teamwork-in-multi-agent-reinforcement-learning/)
---
### Practical & Community
**Benchmark tool for custom Pi harnesses and extensions: r/LocalLLaMA**
RoastMyHarness runs DeepSWE benchmark tasks against both bare Pi and user-modified harnesses, extensions, skills, or AGENTS.md files to measure quality, token efficiency, and cost changes. The tool is currently tested on Linux and remains a work in progress with a wizard available to set up Pi extensions. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1weufjc/benchmark_your_custom_pi_tools/)

**QEMU-based VM manager with planned AI agent integration: r/LocalLLaMA**
A developer is building a Rust and Tauri desktop application using QEMU with WHPX on Windows and is seeking advice on QMP for lifecycle management and approaches for letting an AI agent interact inside the VM. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1wey0i3/need_some_advice_on_a_qemubased_vm_manager_with/)

**Hugging Face Hub silently fingerprints which AI coding agent is in use: r/LocalLLaMA**
Users reported that the library sends telemetry identifying the specific coding agent being used. Source: [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1wey19g/huggingface_hub_silently_fingerprints_which_ai/)
---
### Under the Hood: LoRA Adapter Sharing in Inference Servers
Inference servers can keep a single copy of base model weights in GPU memory while swapping lightweight adapter deltas for different users. The approach works because adapter matrices are orders of magnitude smaller than the base weights, so memory traffic stays low even when many adapters are active. vLLM already implements fused kernels that apply these deltas during the forward pass without materializing full weight copies. The tradeoff appears when adapter rank grows: higher ranks increase both compute per token and the chance that the adapter no longer fits in the remaining GPU memory alongside the base model. Teams therefore choose low-rank adapters when they need to serve dozens of fine-tunes on one card and accept the modest quality drop that comes with rank eight to thirty-two. When the workload instead requires many high-rank adapters or very different base models, the economics shift back toward dedicated instances.
---
### Things to Try This Week
- Test the Lorivo platform with a rank-8 or rank-16 LoRA on Qwen 3.5 4B to see shared-adapter serving in action.
- Run RoastMyHarness against your own Pi extensions to quantify whether they improve token efficiency on DeepSWE tasks.
- Generate a running route from your own address with ChatGPT Work and GPT-6 Astra to explore the visualize skill output.
---
### On the Horizon
- Further details expected from OpenAI on its independent evaluator program.
- Additional Western-lab open-weight models in the 120B range may appear as Chinese model restrictions tighten for some organizations.
- Community training runs on the announced 9.4B dense model could produce early checkpoints within weeks.
