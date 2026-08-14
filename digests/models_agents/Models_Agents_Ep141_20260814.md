# Models & Agents
> **Gemini 3.7 Flash delivers major upgrades for coding and web work at half the prior Flash price, giving builders a faster, cheaper frontier option right now.**

**What You Need to Know:** Google released Gemini 3.7 Flash with targeted gains in software engineering and knowledge tasks plus a halved introductory price. OpenAI added Computer History to the ChatGPT desktop app so the model remembers activity across sites and apps, and launched an Ultrafast inference mode via Cerebras hitting 750 tokens per second. DeepMind also shipped SL2T, a sign-language-to-text model built with the Deaf community. Watch how these pricing and speed moves shift daily tool choices this week.
---
### Top Story
Google released Gemini 3.7 Flash with major upgrades for software engineering, web development, and knowledge work. The model runs noticeably faster than prior Flash versions while carrying an introductory price set at half the original 3.6 Flash cost. Demis Hassabis highlighted the speed gains and positioned the release as immediately usable for builders. This directly addresses the ongoing frontier-model question of capability gains versus cost trajectory that was active yesterday. Teams working on coding agents or web tooling should test the new pricing tier first to see where it beats existing options. Source: [x.com](https://x.com/demishassabis/status/2087950102455271765)
---
### Model Updates
**Gemini 3.7 Flash speed and pricing: Demis Hassabis (X)**
Demis Hassabis separately noted that Flash 3.7 is lightning fast in addition to the capability upgrades. The combination of speed, engineering focus, and lower price creates a practical daily driver for many workflows. Builders should compare it directly against current GPT and Claude Flash-class options on their own coding and retrieval tasks. The release also received coverage noting 40 percent faster performance alongside multimodal improvements and reduced cost. Source: [x.com](https://x.com/demishassabis/status/2087995995694960670)

**SL2T sign-language-to-text model: Demis Hassabis (X)**
DeepMind launched SL2T, a sign-language-to-text model that lets users sign directly to phones for the first time. The model was developed in close collaboration with the Deaf community. It demonstrates a clear accessibility win from current multimodal training techniques. The launch marks the first time a production-grade system supports direct signing input on consumer devices without intermediate translation steps. Source: [x.com](https://x.com/demishassabis/status/2087885303855944001)

**DeepSeek price increase: WSJ**
DeepSeek raised prices on its flagship models by a factor of four. The move reverses earlier aggressive discounting and will affect cost calculations for teams relying on the open-weight family. Enterprises that had built workflows around the previous pricing must now re-evaluate total inference spend. The change applies across the company’s main model lineup and takes effect immediately. Source: [Google News](https://news.google.com/rss/articles/CBMiggFBVV95cUxQd0hZUGVrZmdGTmVpTkVseXpHNzFmZ1cxaUdrT0I0C1ZVYjFlVnZPdDFUZkV4RWdjMEpoUGxyQ0xEeHJ2VWVKZ0ZLZHc4bURlcEJyVWpUaWZXT0xqR3ljTmZXLXJjZ3FDaHFmRkVkanF1MHhRTlU3dTRtLWxJbDBFVTVB?oc=5)

**Gemini 3.7 Flash coverage in Latent Space: Latent Space**
A dedicated analysis from Latent Space frames the Gemini 3.7 Flash launch as bringing Google DeepMind back to the forefront of the frontier-model race. The piece examines how the combination of speed, engineering focus, and price reduction positions the model against competing offerings. Readers following closed-model competition can use the article to track shifting capability and cost dynamics. Source: [latent.space](https://www.latent.space/p/ainews-gemini-37-flash-brings-gdm)
---
### Agent & Tool Developments
**Computer History in ChatGPT desktop app: [@OpenAI](https://x.com/OpenAI) (X)**
OpenAI added Computer History to the ChatGPT desktop app, allowing the model to remember activity across apps and websites on the user’s computer. The feature builds on the earlier Chronicle preview with lower token usage and added privacy controls including timeline view, selective clearing, and app/website exclusions. Users on Pro, Business, and Enterprise plans can opt in via Settings → Integrations on Mac, with EEA rollout coming later. The system also supports pausing and resuming history collection directly from the menu bar. Source: [x.com](https://x.com/OpenAI/status/2087996496088297746)

**Ultrafast inference mode via Cerebras: [@OpenAI](https://x.com/OpenAI) (X)**
OpenAI released an Ultrafast mode powered by Cerebras that reaches up to 750 tokens per second on its most intelligent model. The offering targets real-time voice, customer support, coding, design, financial research, and security workflows where latency matters. It is positioned for enterprise use cases that need frontier intelligence without waiting on slower generation. The mode is available to businesses where faster frontier intelligence creates a measurable advantage. Source: [x.com](https://x.com/OpenAI/status/2087947724725665908)

**ChatGPT timeline and privacy controls: [@OpenAI](https://x.com/OpenAI) (X)**
A new timeline view lets users review past work and identify frequent tasks for skill-building. Controls allow pausing history, excluding specific apps or sites, and clearing partial or full records directly from the menu bar. The implementation reduces overall token consumption compared with the prior Chronicle preview while maintaining personalization benefits. Source: [x.com](https://x.com/OpenAI/status/2087996497908609389)

**Opt-in process for Computer History: [@OpenAI](https://x.com/OpenAI) (X)**
To activate Computer History, users select the feature under Settings → Integrations inside the ChatGPT desktop app on Mac. The rollout is currently global for Pro, Business, and Enterprise tiers, with access in the EEA, UK, and Switzerland scheduled for the coming weeks. Source: [x.com](https://x.com/OpenAI/status/2087996499263369267)
---
### Practical & Community
**Markdown SVG renderer with thinking levels: Simon Willison (X)**
Simon Willison shared a live Markdown-to-SVG renderer that accepts a gist URL and renders at high, medium, and low thinking levels. The tool exposes how different reasoning budgets affect output quality on the same prompt. Developers working on visual generation pipelines can test it immediately at the linked demo. The renderer also surfaces browser-specific rendering differences that affect final output. Source: [x.com](https://x.com/simonw/status/2087975521296728348)

**Pelican bicycle generation at high thinking: Simon Willison (X)**
Willison posted a high-quality pelican-riding-a-bicycle image produced only when the model ran at the highest thinking level. Lower levels produced visibly weaker results on the same prompt. The example illustrates the practical value of spending extra test-time compute on creative visual tasks. The image link appears in the same thread as the renderer tool. Source: [x.com](https://x.com/simonw/status/2087975473427128526)

**SVG rendering differences across browsers: Simon Willison (X)**
Willison documented that Firefox and Chrome render certain SVGs differently from Safari due to a spec-compliance bug that Safari ignores. The observation matters for anyone shipping SVG output from models to web users. The difference appears consistently across multiple test prompts. Source: [x.com](https://x.com/simonw/status/2087988362401742956)

**Pelican transcript links: Simon Willison (X)**
Willison also posted direct links to the full transcripts for the high, medium, and low thinking runs so others can inspect the exact reasoning traces. The transcripts are hosted on his own tools site and linked from the original thread. Source: [x.com](https://x.com/simonw/status/2087975521296728348)
---
### Under the Hood: Activation Bottlenecks in Constraint Reasoning
Everyone talks about LLMs “knowing” a rule when accuracy rises, yet the actual mechanism is often just surface-level pattern matching rather than internal routing of the constraint. In practice the model encodes the constraint symmetrically whether the prompt contains it or not, but only sometimes activates that encoding during the final decision step. When activation fails, the model defaults to a conservative answer even though the constraint was represented in the hidden states at above 88 percent probe accuracy. Activation patching can restore the correct behavior in one failure mode, lifting log-probability by roughly 6 nats, while the second mode shows almost no repair. The distinction matters because prompt-based interventions only inflate conservative bias through a single mediation path; they never open the blocked routing channel. A quartet of diagnostic tests run across fourteen models confirmed two distinct failure modes rather than a single uniform deficit. Teams building agents that must respect implicit feasibility constraints therefore need to measure routing success, not just final accuracy, and should prefer architectures or fine-tuning regimes that strengthen the activation step rather than adding more surface instructions. The same pattern appears in both open-weight and closed models, indicating the bottleneck is architectural rather than training-data specific. When the constraint is present but not routed, downstream repair via donor activations succeeds in only one of the two observed modes, suggesting future work should target the routing circuitry directly. Practical takeaway: before deploying an agent on tasks with hidden feasibility rules, run the four-condition diagnostic to determine whether accuracy shortfalls stem from missing knowledge or from failed activation.
---
### Things to Try This Week
- Test Gemini 3.7 Flash on a current coding or web-dev task to see whether the halved price and speed gains change your daily model choice.
- Enable Computer History in the ChatGPT desktop app if you work across multiple sites and want the model to retain context without repeated explanations.
- Run Simon Willison’s SVG renderer on a visual generation prompt at high versus medium thinking levels to observe the quality jump for yourself.
- Compare the new Ultrafast Cerebras-backed endpoint against your current inference setup on a latency-sensitive workflow such as real-time support or code completion.
- Review the SL2T model announcement to explore multimodal accessibility applications that may apply to your own user-facing projects.
---
### On the Horizon
- Further regional rollout of ChatGPT Computer History to EEA, UK, and Switzerland users in the coming weeks.
- Continued price and speed experiments across frontier Flash-class models as labs respond to the Gemini 3.7 Flash move.
- More sign-language and accessibility multimodal releases following the SL2T pattern of community-collaborative training.
- Additional open-weight price adjustments as DeepSeek’s fourfold increase influences competitor strategies.