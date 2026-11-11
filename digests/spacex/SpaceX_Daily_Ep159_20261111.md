# SpaceX Daily
> **SpaceX signed a turnkey heterojunction solar-cell line to scale Starmind satellite output past 100 GW.**

### Top News

1. **NASA Administrator details SLS standardization with stretched Centaur V and ML-2 cancellation**
   NASA Administrator Jared Isaacman said the changes aim to raise SLS flight rates and cut costs until commercial lunar options arrive in the 2030s. The agency dropped the Block 1B Exploration Upper Stage in favor of a near-Block 1 configuration paired with the stretched Centaur V already in production for ULA’s Vulcan. Isaacman noted that industry responses to NASA’s commercial lunar transportation search pointed to the 2030s rather than an immediate replacement. Material testing for the stretched stage is advancing in parallel with ULA, and NASA is helping address production constraints by locating personnel and equipment across its centers. The first use of the new stage remains undecided, with both the Interim Cryogenic Propulsion Stage and stretched Centaur V still listed as options for Artemis IV. Isaacman expects the stretched Centaur V to fly on Vulcan for Department of Defense missions in addition to SLS. Centaur V first flew on Vulcan’s Cert-1 mission in January 2024 and draws on decades of heritage from the broader Centaur family. Source: [nasaspaceflight.com](https://www.nasaspaceflight.com/2026/11/isaacman-sls-2030s/)

2. **FCC accepts SpaceX application for Grain’s 800 MHz spectrum**
   The acceptance opens formal review of SpaceX’s bid to acquire the licenses needed for Starlink Mobile service. The move advances SpaceX’s effort to secure terrestrial spectrum rights currently contested by Verizon and AT&T. Acceptance of the application marks a procedural step forward in the ongoing regulatory contest over the 800 MHz band. Source: [teslarati.com](https://www.teslarati.com/spacex-fcc-verizon-att-approved/)

3. **SpaceX signs major supply contract with SINGULUS for heterojunction solar-cell production equipment**
   The agreement covers a turnkey production line for advanced HJT solar cells to support more than 100 GW of manufacturing capacity at SpaceX’s Bastrop, Texas facility. The first line is scheduled for delivery in the first half of 2027, with additional lines planned under the strategic partnership. SINGULUS will combine wet chemistry, vacuum coating, and thermal processing on a single platform to produce high-performance cells for Starmind satellites. SpaceX provided significant funding to SINGULUS in March 2026 and again in October 2026 as part of a subordinated secured loan. Mike Nicolls, SpaceX Senior Vice President of Starlink, stated that the partnership creates a durable manufacturing path for solar cells at the Texas production facility. Lars Lieberwirth of SINGULUS noted that the platform approach differentiates the company in the market for next-generation solar cell technology. Source: [singulus.com](https://www.singulus.com/2026/11/10/spacex-heterojunction-solar-cells-singulus/)

4. **Cursor launches multiplayer Projects beta for team-wide agent coordination**
   The update gives every teammate and their agents a shared workspace with unified task boards, context, memory, and documents. Agents can now plan around one another, flag conflicts, and hand off work in real time across the team while each person retains a private one-to-one chat with their own coordinator and worker agents. New team members receive pre-configured access to the full project memory, avoiding the need to rebuild context from scratch. Several internal Cursor teams already run on-call rotations inside shared Projects, allowing an incoming engineer’s coordinator agent to resume work immediately after checking the shared state. The shared layer holds requirements documents, diagrams, technical specifications, mockups, and other material that grows with the project. Source: [cursor.com](https://cursor.com/blog/projects-multiplayer)

5. **SpaceX loses appeal to force arbitration on fired workers**
   A court rejected the company’s attempt to compel arbitration in cases involving terminated employees. The ruling keeps those disputes in open court rather than private proceedings. Source: [teslanorth.com](https://teslanorth.com/2026/11/10/spacex-fired-workers-arbitration-appeal/)

6. **BT delays Starlink launch citing Ukraine concerns**
   The UK operator cited ongoing controversy over Starlink use in Ukraine as the reason for holding back service rollout. Source: [teslanorth.com](https://teslanorth.com/2026/11/10/bt-starlink-launch-delay-ukraine/)

7. **Pentagon offers Rocket Lab a $150 million loan to accelerate Neutron**
   The funding aims to speed development of Rocket Lab’s medium-lift vehicle as SpaceX winds down new Falcon 9 rideshare bookings after 2028. Rocket Lab signed eight Neutron missions for roughly $515 million in the third quarter, several at a $70 million base price. Neutron’s first flight remains targeted no earlier than 2027. Source: [mlq.ai](https://mlq.ai/news/pentagon-offers-rocket-lab-a-150-million-loan-to-speed-up-neutron-as-spacex-winds-down-falcon-9/)

8. **US military faces launch supply constraints**
   Reports indicate growing concern inside the Pentagon over available launch capacity for national-security payloads. Source: [arstechnica.com](https://arstechnica.com/space/2026/11/the-us-military-seems-to-be-getting-nervous-about-the-launch-supply-crunch/)

### Also Today
**Starlink Mini 2 launches with 71 Wh removable battery and Wi-Fi 6:** thedigitalbriefnews.com Source: [thedigitalbriefnews.com](https://thedigitalbriefnews.com/starlink-mini-2-removable-battery/)

**SpaceX plans $24B Texas power project for computing ambitions:** Hart Energy Source: [hartenergy.com](https://www.hartenergy.com/technology-and-innovation/he-spacex-gas-power-plant/)

## Community Buzz
Musk recalled that SoftBank’s Masayoshi Son chose a $12 billion WeWork investment over a quarter stake in Tesla that could have helped take the company private. Source: [x.com](https://x.com/elonmusk/status/2120438853928681981)

Musk posted that AI systems “do what they are programmed to do.” Source: [x.com](https://x.com/elonmusk/status/2120432810431537485)

Musk promoted the new Starlink Mini 2 as portable, lightning-fast internet that works anywhere Starlink service is legal. Source: [x.com](https://x.com/elonmusk/status/2120432718639145404)

Vast provided additional detail on the source of a disputed document after a story on the Axiom lawsuit appeared earlier the same day. Source: [x.com](https://x.com/SciGuySpace/status/2120316025149251645)

## The Counterpoint
SpaceX’s loss in its bid to force arbitration for fired workers keeps those cases in open court and exposes internal employment practices to greater public scrutiny. The ruling removes one layer of confidentiality the company had sought and could affect how future disputes are handled. Resolution now depends on the outcomes of the individual lawsuits rather than private arbitration panels. The decision follows an earlier court proceeding in which SpaceX had sought to move the matters into arbitration. Source: [teslanorth.com](https://teslanorth.com/2026/11/10/spacex-fired-workers-arbitration-appeal/)

### Engineering Deep Dive
The SINGULUS contract targets the power bottleneck that limits satellite-based compute. Each Starmind satellite must generate and store enough electricity to run inference or training accelerators while surviving the thermal cycling and radiation of low Earth orbit. Heterojunction technology improves conversion efficiency over standard silicon by stacking layers with different band gaps, capturing a wider portion of the solar spectrum and reducing thermal losses that would otherwise require heavier radiators. The turnkey line combines wet chemistry, vacuum coating, and thermal processing on one platform, cutting the number of handling steps that multiply defect rates during cell fabrication.

At the 100 GW manufacturing target, the line must produce cells whose specific power stays high enough that added array mass does not cancel the benefit of extra electricity. Fewer defects from the integrated process raise yield, which directly lowers the gap between raw silicon wafers and finished, space-qualified cells. SpaceX funded SINGULUS in March 2026 and again in October 2026 through a subordinated secured loan, securing the equipment path before volume production begins.

Once those cells reach orbit, the marginal cost of each additional watt falls toward the cost of the silicon, aluminum, and silver paste alone. That collapse in cost per watt is what makes sustained orbital compute clusters economically plausible rather than a one-off demonstration. The Bastrop facility therefore functions as both a solar factory and the first link in a supply chain that treats kilowatt-hours in space as a manufactured commodity instead of a scarce resource. Delivery of the first line in the first half of 2027 sets the earliest window for initial cell output to feed Starmind satellite builds.

### Market Watch
SPCX is at $143.09, +0.7% vs the previous close.

The engineering that collapses the cost of power in orbit is the same discipline that will collapse the cost of reaching orbit itself.
