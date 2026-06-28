# Models & Agents — Weekly Recap (Week of June 28, 2026)

Pull up a chair, this is Models and Agents, episode 95, for June 28, 2026. Let's see what happened in the AI world today. And trust me, it's been busy.

The week's biggest developments, pulled together — what actually moved, why it matters, and what to watch next.

Open-weight releases from Chinese labs kept landing with little warning while OpenAI pushed multiple GPT updates aimed at security and agent workflows.

Inference techniques such as block diffusion and two-tower designs showed measurable throughput gains on existing hardware.

Agent memory frameworks and environment-simulating models appeared alongside internal reports of longer-running Codex tasks inside OpenAI itself.

GLM-5.2 arrived as the latest open-weight release from a Chinese startup.

Multiple outlets report the model is attracting attention in Silicon Valley for its performance relative to current open families.

The release continues the pattern of rapid iteration from labs such as those behind Qwen and DeepSeek, where new weights appear with minimal fanfare and quickly circulate through developer communities.

Early coverage notes the model is being tested for both research and agent workloads, though concrete benchmark numbers and context length details remain sparse in initial reports.

Builders working on cost-sensitive inference or fine-tuning experiments now have another candidate to benchmark against Llama and Mistral derivatives.

Watch for fast inference integrations and any follow-on fine-tunes that typically appear within days of these releases.

Remember the ongoing story of open-weight models narrowing the gap with closed frontier systems that we tracked through last week.

GLM-5.2 moves that arc forward by giving developers another immediate option without licensing friction.

OpenAI expanded its Daybreak program with GPT-5.5-Cyber, Codex Security, and Patch the Planet.

The release includes a full GPT-5.5-Cyber model for tracing vulnerabilities, validating issues, and generating patches.

A Codex Security plugin runs deep scans and exports to existing tools.

It also adds a Cyber Partner Program and direct work with maintainers via Trail of Bits and HackerOne.

The stack targets authorized defensive work only and keeps human review at the center of every remediation.

Teams can now move from findings to merged fixes inside the same environment they already use for code.

Watch for how security vendors integrate the new model through the partner program and whether open-source projects see faster patch turnaround.

This fits the frontier models thread we have followed since episode ninety-four, where capability gains continue alongside tighter governance rules.

UC San Diego's DFlash replaces standard speculative decoding with a lightweight block diffusion model that drafts entire token blocks in one forward pass.

It conditions on target model hidden features via KV injection and ships with twenty checkpoints plus support for SGLang, vLLM, and TensorRT-LLM.

The approach reports up to six point zero eight times lossless speedup on Qwen three eight B and NVIDIA-measured peaks of fifteen times throughput on Blackwell hardware at fixed interactivity.

Builders working on high-throughput inference pipelines can now test the integration without custom drafting logic.

Watch for community benchmarks on other model families and whether the block-diffusion drafting generalizes beyond the reported setups.

That development lands squarely in the AI compute and inference program we covered last week, where the focus remains on moving the cost curve without new silicon.

Qwen released a thirty-five B parameter mixture of experts model with only about three B active parameters per token.

The model was trained to predict environment states rather than generate chat responses directly.

Two additional AgentWorld variants followed, each focused on simulating tool, terminal, and GUI interactions.

Developers can now fine-tune or prompt these checkpoints to improve agent planning loops before deployment.

The release keeps the open-weight families conversation moving, testing whether environment-specific pre-training closes more of the reliability gap on long-horizon tasks.

OpenAI released an updated GPT-5.5 Instant that improves intent understanding behind questions and adapts responses more reliably to complex constraints.

The update also makes shopping and local recommendations more cohesive.

It is rolling out today to paid users and tomorrow to free users.

Builders should test prompts that previously produced inconsistent outputs on multi-constraint tasks to see whether the new version reduces follow-up clarification turns.

Watch how the update interacts with agentic workflows that chain multiple tool calls.

OpenAI stated that agents powered by Codex are now transforming work across every department, handling tasks that are more complex, longer-running, and increasingly cross-functional.

The company positions this internal usage as an early signal of how agentic tools will reshape workflows once they reach broader availability.

No specific benchmarks or model versions were shared, but the emphasis on cross-functional scope suggests agents are moving beyond single-user chat interfaces into multi-step, multi-stakeholder processes.

Builders should note the implied requirements around reliability, state management, and tool interoperability that such deployments demand.

NVIDIA introduced Nemotron-TwoTower, a block-wise autoregressive diffusion model built on Nemotron three Nano thirty B A three B.

The architecture splits context handling from diffusion denoising and delivers two point four two times throughput at near-parity quality.

The design targets the same inference economics questions we tracked earlier in the week.

OpenAI announced the GPT-5.6 family with Sol as the new flagship, Terra for competitive performance at half the cost of GPT-5.5, and Luna as the lowest-cost option.

The family ships with a strengthened real-time safety stack that includes human red-teaming and over seven hundred thousand A one hundred equivalent GPU hours of testing.

Sol sets a new state of the art on Terminal-Bench two point one for complex command-line workflows.

The models introduce explicit cache breakpoints and a guaranteed thirty-minute cache lifetime billed at one point two five times the uncached input rate.

The models are currently restricted to a limited preview for roughly twenty trusted partners after OpenAI shared plans with the US government.

Broader release is expected in the coming weeks.

Builders gain clearer tiered choices for intelligence versus cost on long-horizon tasks.

Anthropic regained limited US government approval to redeploy its Mythos five cybersecurity model to critical infrastructure operators.

A new MRAgent framework cuts long-horizon agent memory costs dramatically versus LangMem.

Simon Willison shipped the sqlite-utils version four release candidate, adding built-in migrations and nested transaction support for developers working with local data.

Temporary Cloudflare accounts now let agents spin up ephemeral Workers deployments in under a minute without an account.

The seven types of agent memory guide and a detailed Matrix Recurrent Units update provide concrete engineering references for builders.

NagaTranslate demonstrates a full translation and voice pipeline for low-resource Nagaland creoles built on Whisper, VITS, and large language models.

If you work with local databases, the sqlite-utils release candidate is worth installing this week to test the new migration commands on a copy of your data.

Developers exploring agent environments can pull the Qwen AgentWorld checkpoints from ModelScope and run a short terminal simulation loop.

Anyone testing inference speedups should add the DFlash integration to an existing SGLang or vLLM setup and measure block-level throughput on Blackwell hardware.

Keep an eye on DevDay twenty twenty-six in San Francisco on September twenty-nine, where the keynote will be livestreamed.

Broader access to the GPT-5.6 family is also expected in the coming weeks.

OK, let's pop the hood on the inference techniques that surfaced this week.

DFlash moves beyond token-by-token speculative decoding by training a lightweight block diffusion model that proposes entire blocks in a single forward pass.

KV injection from the target model hidden states conditions the draft, removing the need for separate drafting logic at runtime.

The reported six point zero eight times lossless gain on Qwen three eight B and fifteen times peak on Blackwell comes from amortizing the cost of the diffusion step across many tokens at once.

Nemotron-TwoTower takes a different route by decoupling autoregressive context encoding from diffusion-based denoising in a two-tower layout.

The split allows the context tower to run once while the diffusion tower iterates only on the denoising task, producing the measured two point four two times throughput at near-parity quality.

When deciding between these approaches, reach for DFlash if you already run SGLang or vLLM and want plug-in speedups without retraining.

Reach for two-tower designs when your workload benefits from explicit separation of context and generation steps on NVIDIA hardware.

Before we go, keep an eye on how the limited GPT-5.6 preview expands and whether follow-on fine-tunes of GLM-5.2 appear in the next few days.

That's Models and Agents for today. If you found this useful, share it with someone who's trying to keep up with all these changes, and subscribe so you don't miss tomorrow's update. The AI world moves fast. We'll help you keep up. See you tomorrow. And if you'd rather watch than listen, find us on YouTube at Nerra Network — link's in the show notes.

And before you go: this show is part of the Nerra Network — a family of daily podcasts on tech, science, and markets, each one a short, sharp briefing you can finish on the commute. If today earned its place in your feed, here's your next listen — Tesla Shorts Time, your daily deep dive into everything Tesla. Find every show, free, at nerranetwork.com.

## Sources
- [Google News](https://news.google.com/rss/articles/CBMivgFBVV95cUxPNWkycHBOUjlrWnhpclpDd0hJZ3gxR0VTVmtkMG1LWlJLOG1UZ09mWkpBZmpnMFNwVF83aGFRQ3Q3WVZaME5ReDIyNHJaNm5hTm1aZUZtc1lZM3FkR2wzUW1la2tvdmltZFZOSUFfLURaT0ROSl85Z1dJOUhDclBoQ0dMNGg5QUN5ajhtQlR1eUwxdUVFOHJYYzhDbjZJWk5DckRWa2IxMnZMRi12NEphUk8wWWZXdVVrdjhoaG5B0gHEAUFVX3lxTFBCUk9yUjJkNHFJNmJ0VHNKZ0J2M1RNWUN3TVZNSWdGZkNheTZIRlg4a3hRcm92SmFlZEZsVnRWWDduUE1MWkZZU2pYNEYwdmY5QkZXX3c4MmgtbTMwUm0zMGdfYWxVYkhIdE9MVFZvcVBkWmw4TGd6Q1ZTTUhITjFZM0pZT19UQmV1UFVKRHBqUDEtRTItTUhXN3B3T2NPOXlNczAxWUVFRXZiMkE1RlZJdVR3OWVxUEtuMTVHMUFtNmdjamw?oc=5)
- [Google News](https://news.google.com/rss/articles/CBMikAJBVV95cUxPb2VFemhTNEc1YXQycGY5LWV6RGpkSXZpWmt3NjBHTnlTbDdMdUsxWlZCN0xRNmhYN255M1lKd0J1ZExlRlhiQklOZExBNTEzWC1Ea2Y2djNoRTZtZDFxcGRjT3hwV2NMUVpva3JLemtWSGpWdkFtQ2VXd1QwU2xXNklnRVJkaFE4YmhKQVVIc2FpYmFlajdxOWpRM0xJLU9PU2VCbjQ5RjFDbXZiRzhVNXFDRjdyRl9ieDFWVXBlSnNXRnd6dmtaXzBLeGt0bkhLYktvR0hKZW1Kd1JfZjdNeXNIaTVVRmMtRW9YZ2lGNE5hU3gtMkFTbURGaHF1MEgtdVFkbkJvOHAwTzB4d3BlUw?oc=5)
- [simonwillison.net](https://simonwillison.net/2026/Jun/21/temporary-cloudflare-accounts/#atom-everything)
- [x.com](https://x.com/simonw/status/2068840530465952121)
- [marktechpost.com](https://www.marktechpost.com/2026/06/21/the-7-types-of-agent-memory-a-technical-guide-for-ai-engineers/)
- [towardsdatascience.com](https://towardsdatascience.com/tool-calling-explained-how-ai-agents-decide-what-to-do-next/)
- [x.com](https://x.com/OpenAI/status/2069104283824640023)
- [venturebeat.com](https://venturebeat.com/technology/alibabas-ai-video-model-rises-to-no-2-in-global-rankings-as-openais-sora-and-bytedances-seedance-fall-away)
- [venturebeat.com](https://venturebeat.com/orchestration/no-claude-fable-5-no-problem-sakana-achieves-frontier-performance-with-new-fugu-multi-model-auto-synthesis-system)
- [Google News](https://news.google.com/rss/articles/CBMickFVX3lxTE9HZVZpcGFXaTZVX2pPb0QxLUx4c1dESXFpMkZ0d3g4NHpHTVQzbVg0aW1SUTRSeUV4em5zbVhDYU1BRFJ0QnpBbXNQa0VrSkUydGNvMUxraTB4QktwdGJCYmdMdWlpbHJBMlFkVkNWUUtpZw?oc=5)
- [devblogs.microsoft.com](https://devblogs.microsoft.com/agent-framework/meet-your-agent-harness-and-claw/)
- [venturebeat.com](https://venturebeat.com/orchestration/researchers-introduce-self-harness-a-framework-that-lets-ai-agents-rewrite-their-own-rules-boosting-performance-up-to-60)
- [x.com](https://x.com/simonw/status/2069213084305301903)
- [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1ucm508/some_new_updates_to_papers_with_code_p/)
- [marktechpost.com](https://www.marktechpost.com/2026/06/24/dflash-speculative-decoding-drafts-whole-token-blocks-in-parallel-for-up-to-15x-higher-throughput-on-nvidia-blackwell/)
- [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1ue5149/qwenagentworld35ba3b_a_3bactive_moe_trained_to/)
- [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1ue51uk/unlimitedocr_is_now_on_modelscope_a_33b/)
- [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1ue56em/qwenagentworld397ba17b/)
- [arxiv.org](https://arxiv.org/abs/2606.23693)
- [x.com](https://x.com/karpathy/status/2069547676849557725)
- [x.com](https://x.com/karpathy/status/2069601818540392669)
- [Google News](https://news.google.com/rss/articles/CBMixwFBVV95cUxQUm5tMzgtaFNlcWVPY3oxSGZMdzNFQWRXTDRFbGpXU3dXYUxRR2pmRXZpQXVKZndPSkljRXhOd0NXaHVLVjlKS3ZYV3BrcVFESDQ5djNKb1dCZHpPdDZOd3RiQ0NUQ3hwdGYwaGVqMnFCYVNfNmlONVVULXd3a3hPNm1ZUEQ0dERzTXZWRm13MTRqeTZ2MWtuTlQ2VHI0QkhwRy1CTmR3aUp0VVBBSGZpSGJlUHBVMTZfM0xxcENNSnZIMnE2NV9n?oc=5)
- [x.com](https://x.com/OpenAI/status/2069483224158646739)
- [reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1ue5fgm/pcie_50_16x_split_into_2x8_with_riser_cable/)
- [arxiv.org](https://arxiv.org/abs/2606.23694)
- [x.com](https://x.com/OpenAI/status/2069843083701915755)
- [x.com](https://x.com/OpenAI/status/2069770172802773292)
- [arxiv.org](https://arxiv.org/abs/2606.25331)
- [arxiv.org](https://arxiv.org/abs/2606.24973)
- [arxiv.org](https://arxiv.org/abs/2606.24893)
- [arxiv.org](https://arxiv.org/abs/2606.25556)
- [arxiv.org](https://arxiv.org/abs/2606.25338)
- [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1uf53un/i_stopped_trusting_model_benchmarks_and_started/)
- [arxiv.org](https://arxiv.org/abs/2606.25152)
- [arxiv.org](https://arxiv.org/abs/2606.25442)
- [x.com](https://x.com/OpenAI/status/2070196105745518913)
- [arxiv.org](https://arxiv.org/abs/2606.26493)
- [arxiv.org](https://arxiv.org/abs/2606.26120)
- [arxiv.org](https://arxiv.org/abs/2606.26466)
- [arxiv.org](https://arxiv.org/abs/2606.26101)
- [Google News](https://news.google.com/rss/articles/CBMingFBVV95cUxPSHVxb2xWQXM4bndWaWl6T2NQdXNvbks3Rm00bzI5dnhwNV9TczQ0U2dzVkhMYWRzNUp0OWtFNFBJbTd5ZGFpX2hEMFJUMmRGX0lQTE85dTdfWXI5RjJEYnJoNjl4RFZzc2lYSnl0MXREUGdFWENMYkszX0txVzlWaGpXY0dTWkxaOEZhQWMyY2ZrMW9ub1ZnTWNqMDFCQQ?oc=5)
- [Google News](https://news.google.com/rss/articles/CBMiuAFBVV95cUxQamVpdXNveVRPb2tzU0s1UmloU0hEUTNXM0ZVbzBiLWhaU3pUdkRyTDZKTldaUXc4d0NEZE9zOHJ1cm43cXpVM0VBOXFjVnBOQlVJeV8xN09uUE5ZWHN5cnZveXM0SHFFNURqeHRwTkpIdVlZVEE3ckpnRHF3aGZUZ3NLSHdMQnpra1RfZV9qd2hDYjBfcEF1TzBacnhScEtFclhFOEZhUVZtUHFIMFhiQXNTNC1pR21G?oc=5)
- [arxiv.org](https://arxiv.org/abs/2606.26511)
- [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1ufyuph/howre_you_deploying_llms_in_production_nowadays/)
- [arxiv.org](https://arxiv.org/abs/2606.26105)
- [venturebeat.com](https://venturebeat.com/technology/openai-unveils-gpt-5-6-sol-terra-and-luna-models-but-only-accessible-to-limited-preview-partners-for-now-per-us-gov)
- [simonwillison.net](https://simonwillison.net/2026/Jun/26/openai/#atom-everything)
- [x.com](https://x.com/AnthropicAI/status/2070665903440871779)
- [x.com](https://x.com/sama/status/2070609922631537024)
- [x.com](https://x.com/sama/status/2070612055225483692)
- [venturebeat.com](https://venturebeat.com/orchestration/new-agentic-memory-framework-uses-118k-tokens-per-query-langmem-burns-through-3-26m)
- [Google News](https://news.google.com/rss/articles/CBMilAFBVV95cUxNcEdZalZjbEdrbFdRMDJOXy1kYWItYmRSRk02TnNCT0pOYXhpbjc5R05MaC01TDVaQy1tV2phUVRfQkxDVld0dDN5RWYtZDVjb0xtdDhiUUlLV3ptbTJWekpOZDR1bDI2UG00bUxKTlJBMEJQUUExRzVNaXJpa3QyRmQ1RkpkdWpQVHZ5R1hSSjlYQnFI?oc=5)
- [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1ugv7u3/i_silently_break_training_codes_or_configs_so_i/)
- [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1ugwrmz/showcase_building_ml_models_that_watch_mma_fights/)
- [news.google.com](https://news.google.com/rss/articles/CBMiS0FVX3lxTE4tYk9BVUJMNXBiUkREYjZ5UFVGV1poSDhhVWVndEhRMlRIMWoxbTJkYW1pMk1ZRDE3emlWTW5MaW1JLXpiVkRJTDJ4VQ?oc=5)
- [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1uhlvjv/nagatranslate_building_a_translation_and_voice/)
- [venturebeat.com](https://venturebeat.com/infrastructure/claude-code-turned-every-engineer-into-three-now-companies-need-more-product-thinkers)
- [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1uhatw8/mathformer_testing_whether_symbolic_math_is/)
- [news.google.com](https://news.google.com/rss/articles/CBMibkFVX3lxTE1pMGxZLUw3bTF3a1NyRDU3U3BtN0IzUW9oelFxT1VrbURaNWM3eVBmTzR3My03YzRfVmE5Q1RYNDk3UTd4NXR4X19uR3M1eEFlNmRidzRBYnEyZkhpa25tMzFBZDVrTl9zdXNzeTV3?oc=5)
- [reddit.com](https://www.reddit.com/r/MachineLearning/comments/1uh61uw/hiding_messages_in_the_least_significant_mantissa/)