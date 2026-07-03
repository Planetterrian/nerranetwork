# Models & Agents
> **Local browser agents just became practical and private — WebBrain runs entirely in Chrome or Firefox using your own models.**

**What You Need to Know:** WebBrain delivers an open-source, MIT-licensed browser agent that reads pages and automates multi-step tasks via Ask and Act modes. Simon Willison shipped a one-shot CLI coding agent built on his llm library. Safety research introduced ProvenanceGuard and Sigil to catch misalignment before tool calls execute. Builders should watch how local-first agents change the privacy and reliability tradeoffs this week.
---
### Top Story
WebBrain is a free, MIT-licensed AI browser agent for Chrome and Firefox that reads pages, extracts data, and automates multi-step tasks through Ask and Act modes. It runs on local models via llama.cpp or Ollama for full privacy or connects to any cloud API when needed. The tool directly addresses the gap between demo agents and usable daily automation by keeping all page processing inside the browser. Developers gain a concrete starting point for local browser automation without sending sensitive page content to third parties. Watch how the community extends the Ask/Act modes and whether it becomes the default base for custom local agents. Source: [marktechpost.com](https://www.marktechpost.com/2026/07/02/meet-webbrain-an-open-source-local-first-ai-browser-agent-that-reads-pages-and-automates-tasks-in-chrome-and-firefox/)
---
### Model Updates
**RuleChef: arXiv**
RuleChef uses LLMs only at training time to synthesize human-editable rules for classification, NER, and relation extraction from task descriptions and labeled examples. Rules are iteratively patched based on failures on a held-out split, producing a fast, deterministic, inspectable system. The approach bootstraps from any existing model’s input-output pairs and releases under Apache 2.0. Builders working on production NLP pipelines should test whether the generated rules replace brittle prompt chains this week. Source: [arxiv.org](https://arxiv.org/abs/2607.01293)

**Office Comprehension Bench: arXiv**
Office Comprehension Bench evaluates LLMs on native .docx, .xlsx, and .pptx files across structural perception and expert-level domain reasoning in 12 industries. Even frontier systems reach only 59.3% on the domain Q&A track, with deeper thinking yielding little gain while moving to higher product tiers produces modest improvement. The benchmark releases the dataset, tooling, judge prompt, and public leaderboard. Teams building document agents should add it to their evaluation suite immediately. Source: [arxiv.org](https://arxiv.org/abs/2607.01245)

**TokenScope: arXiv**
TokenScope provides an interactive tool for decoder-based LLMs that exposes token-level metrics, attention patterns, and structural information during code generation. It supports token replacement, counterfactual branching, and AST-aware aggregation. Researchers studying LLM code behavior gain a practical way to explore alternative generation paths without post-hoc analysis. Source: [arxiv.org](https://arxiv.org/abs/2607.01235)
---
### Agent & Tool Developments
**Sigil safety guardrail: odaily.news**
Sigil adds a verification step before AI agents sign or execute transactions, replacing blind “Yes” clicks with explicit review. The guardrail targets the common failure mode where agents propose actions that deviate from user intent. Early users report it fits naturally into existing agent loops without major refactoring. Teams shipping agentic finance or crypto tools should evaluate it this week. Source: [Google News](https://news.google.com/rss/articles/CBMiT0FVX3lxTE8zRFpuTjFqOS0wMFE1UHBrX0U4SlBSZWFIWldINHp1djFwYUpyVUNfZF94ZmYtdmU1djJOd1pBYkI5dTlrTFdLRWxJVjd2LWM?oc=5)

**ProvenanceGuard: arXiv**
ProvenanceGuard formalizes misalignment detection as provenance analysis and blocks tool calls unsupported by traceable evidence in the agent’s context. On Agent-SafetyBench it cuts error rate on misaligned traces from 42.9% to 1.8% while lowering unnecessary interventions on successful traces. The multi-stage pipeline works across ten backbone LLMs and adds no statistically significant overhead on aligned actions. Agent developers gain a concrete, auditable alternative to LLM-as-a-judge guardrails. Source: [arxiv.org](https://arxiv.org/abs/2607.01236)

**Simon Willison’s LLM coding agent: Simon Willison**
Simon Willison one-shot a CLI coding agent on top of his llm Python library and documented the full Fable experiment. The agent operates directly on local or remote models through the library’s existing interface. Builders already using llm can replicate the pattern in minutes and extend it for their own workflows. Remember the show covered Agents & Tool Use yesterday — this release shows continued rapid iteration on simple, library-backed agents rather than new frameworks. Source: [simonwillison.net](https://simonwillison.net/2026/Jul/2/llm-coding-agent/)
---
### Practical & Community
**What Breaks When AI Agents Move From Demo to Production: The AI Journal**
The article catalogs concrete failure modes that appear only after agents leave controlled demos, including state management drift, tool schema mismatches, and compounding errors over long horizons. It focuses on production patterns rather than theoretical limits. Teams moving agents into real environments should review the checklist before scaling. Source: [Google News](https://news.google.com/rss/articles/CBMiggFBVV95cUxPYXpnTE9Wc01sRXFaYjRmQXBieHdYeXBucnVBNmdNeDNWT0JJSHZabl85NXFyaXQxbDcycEMySjE1cUdKVFNUbGZXUUNRLUJ5c3NvOTRVVHVISHBCODB4cV8xM200b2Nid0NnTUlMeE90T005RVBnQmJjczBtaGI0VUpR?oc=5)

**Prompt injection search growth: autogpt.net**
Searches for “prompt injection” have doubled in the past year as more teams ship agents. The trend reflects rising awareness of a core agent reliability issue rather than any single new attack. Developers should treat injection resistance as a first-class evaluation criterion alongside task success. Source: [Google News](https://news.google.com/rss/articles/CBMiiwFBVV95cUxNTEY2LV9VN2g5Y1B0V3NqSmc3VkFaTkM1a2Zmb280aTlEbTRSeFl5MFd1cG9jWUNDaHJyMXROUUNlc29FZnBoM0JoZkJvSDk2QVd1Unc4SGFxSTJvdWZ5OWVDSWd1ZU1qbWtoOUxtTlVld2EyOExBU2c3VzZ4SFdJNC1HQXRmeDd6a1FV?oc=5)
---
### Under the Hood: Sliding-Window KV Cache Compression
Everyone talks about KV cache compression as if it is a simple “just drop the unimportant tokens” switch. In practice Kara shows it is a sliding-window decode-time policy that scores recent context with bidirectional attention and then uses a Token2Chunk module to preserve flexible semantic chunks instead of fixed blocks. The threshold-triggered methods it replaces often create information holes or actually lower throughput; Kara avoids both by operating only on the active window and expanding selected pairs into variable-length chunks. The resulting KvLLM implementation on top of vLLM delivers measurable memory reduction and higher output throughput, but the gains depend on how well the bidirectional scorer matches the model’s actual attention patterns. The practical decision is straightforward: use it when long chain-of-thought traces are the bottleneck and you already run on paged attention; skip it if your workloads stay short or if you cannot tolerate any risk of dropping a critical intermediate reasoning step.
---
### Things to Try This Week
- Install WebBrain in Chrome or Firefox and test the Act mode on a multi-step research workflow using a local Ollama model.
- Replicate Simon Willison’s CLI coding agent on top of the llm library if you already maintain Python tooling around model calls.
- Add the Office Comprehension Bench to your document-agent evaluation harness to measure real file-format understanding.
- Run ProvenanceGuard on an existing agent loop to compare misalignment detection rates against your current LLM-as-a-judge setup.
---
### On the Horizon
- More local-first browser agents are expected as the WebBrain pattern spreads.
- Additional provenance-style guardrails will likely appear as teams publish on misalignment benchmarks.
- Continued growth in prompt-injection tooling and evaluation as agent deployments increase.