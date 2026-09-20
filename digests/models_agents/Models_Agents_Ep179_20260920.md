# Models & Agents
> **Local neural programs compiled from English descriptions now run entirely on CPU without external APIs.**

**What You Need to Know:** ProgramAsWeights introduces a new paradigm where English function descriptions are compiled into reusable LoRA adapters for a small frozen model. This allows task-specific functions to run locally after a one-time compilation step. Developers should watch how this affects agent design and local deployment strategies this week.
---
### Top Story
ProgramAsWeights allows users to describe a text function in English, compile it into a reusable neural program, and run it locally on CPU. The system uses a finetuned Qwen3-4B to generate a LoRA adapter for a frozen Qwen3-0.6B interpreter. On FuzzyBench it reaches 73.4% exact-match accuracy. It separates compilation from inference so the task stays fixed while inputs change. The project is open source with code and model weights available. A higher-accuracy mode called Compile by Training finetunes the adapter for 100 steps and reaches 83.6% semantic accuracy on FuzzyBench-Hard. The interpreter remains frozen throughout, so only the generated adapter changes per task. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1wl13eu/programasweights_compile_english_function/)
---
### Model Updates
**China AI startup Naive AI bets on mid and post-training to compete in LLMs: 디지털투데이**
Naive AI is focusing on mid and post-training stages to build competitive LLMs. The startup aims to close the gap with larger players through specialized training techniques. Source: [digitaltoday.co.kr](https://www.digitaltoday.co.kr/en/view/105607/china-ai-startup-naive-ai-bets-on-mid-and-post-training-to-compete-in-llms)

**Anonymizing prompts cuts OpenAI's GPT-4o mini retrieval score by 60%: PPC Land**
Anonymizing prompts reduces the retrieval performance of GPT-4o mini by sixty percent. This highlights privacy techniques' impact on model capabilities. Source: [ppc.land](https://ppc.land/anonymizing-prompts-cuts-openais-gpt-4o-mini-retrieval-score-by-60%)
---
### Agent & Tool Developments
**Raindrop Raises Series A Funding For AI Agent Reliability Platform: pulse2.com**
Raindrop raised Series A funding led by CRV, bringing total funding to fifty million dollars. The platform focuses on improving reliability for AI agents in production. Source: [pulse2.com](https://pulse2.com/raindrop-raises-series-a-led-by-crv-bringing-total-funding-to-50-million-for-ai-agent-reliability-platform/)
---
### Practical & Community
**Trained tiny LLM years ago, now runs good local LLMs on 8GB RAM: Simon Willison (AI builder) (X)**
Simon Willison notes that he trained a tiny LLM years ago and now runs good local LLMs using approximately eight gigabytes of RAM. Source: [x.com](https://x.com/simonw/status/2101458801568416175)

**datasette-auth-github 1.0: Simon Willison**
The datasette-auth-github plugin reached version 1.0 after fixing cookie expiration issues for longer authenticated sessions. Source: [simonwillison.net](https://simonwillison.net/2026/Sep/19/datasette-auth-github/)

**Experimenting with hypersurface-constrained dynamic weight updating: r/MachineLearning**
A researcher shared results from a side project using hypersurfaces to generate weight deltas for a single decoder block iterated multiple times. The approach reduces parameter count to about sixteen percent of a standard twenty-four layer transformer while maintaining competitive loss. The model uses a triangular wave function set and a context vector from Gated Linear Attention to modulate weight updates. Source: [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1wksamz/experimenting_with_hypersurfaceconstrained/)
---
### Under the Hood: Token Routing in Mixture-of-Experts Layers
The gap between advertised expert utilization and actual routing behavior often surprises practitioners. A router network predicts which experts to activate based on token embeddings, but the prediction itself adds a small feed-forward pass before the main computation. In practice this routing decision can be cached across similar tokens to save compute, though accuracy drops when the cache window exceeds a few hundred tokens. The quality gain from adding more experts plateaus once the router begins to under-utilize the additional capacity, typically around sixty-four experts for models under thirty billion parameters. When the router is trained with an auxiliary load-balancing loss, the distribution across experts becomes more uniform but the primary task loss can increase by up to two percent. Teams should prefer this architecture when token diversity is high and inference batch sizes stay above eight; for smaller batches the overhead of the router outweighs the sparsity benefit. The router is usually a lightweight two-layer network whose parameters are learned jointly with the experts, yet its output distribution directly controls which expert weights are loaded into memory during the forward pass. Caching the router output for tokens whose embeddings fall within a small cosine distance of a previously seen token can cut router FLOPs by roughly thirty percent on repetitive text, but the same cache quickly degrades on highly varied inputs such as code or multilingual data. Load-balancing losses are typically scaled by a small coefficient so they do not dominate the main language-modeling objective; increasing that coefficient beyond 0.01 often produces the two-percent regression mentioned earlier. In production systems the router decision is made once per token at the start of the layer and then reused for the remainder of the block, which keeps the added latency to a few microseconds on modern accelerators.
---
### Things to Try This Week
- Try ProgramAsWeights for defining reusable local functions from English descriptions on your own machine.
- Experiment with anonymized prompts when testing retrieval tasks with GPT-4o mini to measure privacy tradeoffs.
- Check out the hypersurface weight update experiment if you are exploring parameter-efficient training methods.
---
### On the Horizon
- Further results from Naive AI on their mid-training approaches expected in coming weeks.
- Potential updates to agent reliability tools from Raindrop.
- New local inference optimizations from the open-source community.
