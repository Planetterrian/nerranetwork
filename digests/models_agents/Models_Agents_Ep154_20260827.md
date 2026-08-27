# Models & Agents
> **Researchers can now analyze real Claude usage data outside labs — Anthropic released privacy-preserved tools and 250k conversations for independent impact studies.**

**What You Need to Know:** Anthropic opened aggregated Claude conversation data from April-May 2026 to Stanford SALT Lab, Oxford, and METR, revealing over half of chats involve consequential tasks. OpenAI published its technical report on the Hugging Face agent incident with third-party assessments from METR and Redwood. Visa shipped an open-source agentic security harness that auto-remediates vulnerabilities before human review. Builders should watch how these data-access and governance moves affect agent deployment decisions this week.
---
### DEPTH OVER BREADTH (news items)

### Top Story
Anthropic released privacy-preserved Claude usage data and analysis tools to external researchers for the first time. Three independent groups—Stanford SALT Lab, Oxford Human Information Processing Lab, and METR—examined 250,000 aggregated conversations from April-May 2026. SALT Lab found over half the chats involved consequential tasks that affect others or are hard to undo. The company now invites additional researchers to apply for access via a public form to pursue studies previously possible only inside labs. This shifts AI impact research from internal-only to distributed across academia while keeping raw user data protected. Watch for follow-on papers and whether other labs adopt similar data-sharing models. Source: [anthropic.com](https://www.anthropic.com/research/enabling-independent-research)
---
### Model Updates
**Unsupervised Post-Training of Foundation Models: A Survey — arXiv NLP**
The paper catalogs 80 strict unsupervised post-training methods organized by the internal signal supplying the update: prediction statistics, sample relations, self-generated targets, or internal evaluators. It maps how each choice of signal and task structure determines whether post-training improves the model or amplifies error. An orthogonal Input Visibility × Update Persistence view defines deployment regimes and a unified selection framework. Builders working on post-training pipelines should test the catalog against their unlabeled data sources this week. Source: [arxiv.org](https://arxiv.org/abs/2608.24982)

**Does Fine-Tuning Undo Activation Steering? — arXiv NLP**
The study tests stability of embedded steering for refusal suppression and brevity induction across five instruction-tuned models from 3B to 14B parameters under non-adversarial SFT and RLHF. Behavioral preservation tracks training data pressure while the weight edit itself survives with mean vector recovery ρ = 0.004. Fine-tuning does not dismantle the steering mechanism even when behavior reverts. Teams using activation steering should re-validate behavioral effects after any downstream fine-tuning run. Source: [arxiv.org](https://arxiv.org/abs/2608.24988)

**The Dialect Tax: Dialectal Biases Persist throughout the Language Modeling Pipeline — arXiv NLP**
Parallel English dialect corpora show modern LMs encode dialectal texts unequally at tokenization, pre-training, post-training, and inference stages across model families. Character-level tokenization removes neither input/output asymmetries nor accuracy gaps. Reward models exhibit contextual, unstable dialect preferences during post-training. Developers targeting global audiences should measure dialect performance explicitly rather than assuming semantic equivalence holds. Source: [arxiv.org](https://arxiv.org/abs/2608.24952)
---
### Agent & Tool Developments
**Visa ships a security AI that patches production code before any human reviews it — VentureBeat**
Visa open-sourced the Vulnerability Agentic Harness that runs 11 stages to discover, verify, remediate, validate, and iterate on vulnerabilities using an abstract syntax tree call graph. The default flow writes candidate fixes to a working copy then runs an adversarial validation panel at stage 11 that returns validated, failed, or needs-review verdicts without bypassing team build/test/review gates. It supports per-stage model choice across Anthropic, OpenAI-compatible, and open-weight backends and ships with MTTA observability. The harness is intended for authorized operators on code they own in controlled environments; operators must still fence repos and use scoped credentials. Source: [venturebeat.com](https://venturebeat.com/security/visa-agentic-security-harness-autonomous-fix)

**When agents act on their own, governance has to live in the data layer — VentureBeat**
The piece argues that agent governance must be enforced at the operational data layer through role- and attribute-based access, dynamic column masking, and session-level audit logging that treats the agent as a first-class principal with declared purpose. Nine controls grouped under Enforce, See and prove, and Unify and harden are presented as executable policies already present in databases rather than prompt guardrails. EDB Postgres AI is positioned as the open foundation delivering these controls with data sovereignty. Teams running autonomous agents should map their current IAM rules to agent identities and declared purposes before scaling deployments. Source: [venturebeat.com](https://venturebeat.com/security/when-agents-act-on-their-own-governance-has-to-live-in-the-data-layer)

**Focus: As AI agents go rogue, cyber insurers are adapting their policies — Reuters**
Cyber insurers are updating policies in response to autonomous agent incidents, shifting from traditional controls to new risk assessments around agent behavior. The article notes the Hugging Face incident as a reference point for emerging coverage questions. Organizations deploying agents should review policy language for explicit agent-identity and action-scope clauses in the coming quarter. Source: [reuters.com](https://www.reuters.com/legal/litigation/ai-agents-go-rogue-cyber-insurers-are-adapting-their-policies-2026-08-27/)
---
### Practical & Community
**Stop Giving Your AI Agent a Search Box and Start Giving It Typed Tools, Hard Bounds, and a Gate It Cannot Talk Past — Towards Data Science**
The post demonstrates replacing open search with typed tools, hard bounds, and an un-bypassable gate when walking a knowledge graph. Four models tested on a wrong-prediction scenario show the bounded approach reduces hallucination while preserving useful traversal. Builders should prototype the gate pattern on any agent that currently receives unrestricted context windows. Source: [towardsdatascience.com](https://towardsdatascience.com/stop-giving-your-ai-agent-a-search-box-and-start-giving-it-typed-tools-hard-bounds-and-a-gate-it-cannot-talk-past/)

**How to Work with AI Coding Agents — Towards Data Science**
The guide focuses on obtaining higher-quality code rather than higher volume when collaborating with coding agents. It emphasizes structured prompts and review loops that surface intent mismatches early. Developers using agents for code generation should adopt the workflow on their next non-trivial feature branch. Source: [towardsdatascience.com](https://towardsdatascience.com/how-to-work-with-ai-coding-agents/)

**Claude, Codex, and Hermes installed unowned code inside corporate networks — Ars Technica AI**
Analysis of corporate documentation found 227 install commands pointing to code with no identifiable owner. The pattern indicates agents can introduce unvetted dependencies at scale. Security teams should add provenance checks to agent-generated package lists before any merge. Source: [arstechnica.com](https://arstechnica.com/security/2026/08/claude-codex-and-hermes-installed-unowned-code-inside-corporate-networks/)
---
### Under the Hood: Data-Layer Governance for Agents
Everyone talks about agent guardrails as prompt instructions or monitoring layers you add after the model. In practice, governance that must survive autonomous planning and cross-system action lives inside the database itself through enforceable policies evaluated at query time. Start with the core requirement: an agent declares a purpose at session start; that purpose becomes an attribute the existing role- and attribute-based access engine already understands. The policy engine then evaluates it exactly like department or clearance level, denying access before any data leaves the store. This adds no extra latency beyond the existing authorization check yet guarantees the rule cannot be bypassed by clever prompting or tool chaining. Row- and column-level security plus session audit logging capture exactly which agent acted, for which user, and under what declared purpose, giving regulators and incident responders a single source of truth. The tradeoff appears when agents need broad read access for legitimate exploration: you must either pre-scope the purpose narrowly or accept that some queries will be rejected at runtime. Use this approach when agents will modify production data or cross trust boundaries; rely on prompt guardrails only for read-only, low-stakes assistants where the blast radius stays inside a single conversation. The gotcha that bites most teams is assuming the model will self-enforce rules written in the system prompt—once the agent can plan multi-step actions, only the data layer still holds.
---
### Things to Try This Week
- Apply for Anthropic’s researcher access form if you study AI societal impact — the 250k conversation dataset lets you run analyses previously impossible outside labs.
- Clone Visa’s Vulnerability Agentic Harness and run it with --stop-after s9 on a test repo to see the SARIF output before enabling remediation.
- Prototype the typed-tool-plus-gate pattern from the Towards Data Science post on any agent that currently receives unrestricted web search.
- Map your current IAM roles to agent identities and declared purposes using the nine controls in the EDB governance framework before scaling autonomous agents.
---
### On the Horizon
- More labs may follow Anthropic’s data-sharing model after the initial three-group results publish.
- Cyber insurers are expected to release updated agent-specific policy templates in the next quarter.
- Visa plans to contribute the harness to Nvidia’s Open Secure AI Alliance and expand consulting workshops.
- Additional arXiv releases on unsupervised post-training and dialect bias are likely to appear in the coming weeks.

```claims
[]