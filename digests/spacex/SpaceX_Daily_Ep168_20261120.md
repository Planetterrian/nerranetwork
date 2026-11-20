# SpaceX Daily
> **Orbital AI satellites launching on New Glenn in 2029 will test whether solar arrays can sustain rack-scale TPU workloads without terrestrial grid ties.**

### Top News

1. **Google selects New Glenn for first dedicated Project Suncatcher launch**
   Google booked Blue Origin’s New Glenn rocket for the first heavy-lift launch under Project Suncatcher, scheduled for the first quarter of 2029. Multiple computing satellites will fly, each carrying Tensor Processing Unit capacity roughly equal to one data-center rack. The satellites will enter sun-synchronous orbit to evaluate whether continuous solar exposure can support power-intensive machine-learning operations in space. An earlier prototype, built with Planet Labs and launched on a SpaceX Falcon 9 in October, successfully booted its TPUs and ran the Gemma 4 model to generate and transmit a haiku. Blue Origin’s next New Glenn flight remains delayed until January 2027 following a May explosion that damaged the Florida launchpad. Source: [silicon.co.uk](https://www.silicon.co.uk/cloud/ai/google-blue-origin-ai-632448) Source: [teslanorth.com](https://teslanorth.com/2026/11/19/google-blue-origin-suncatcher-launch/)

2. **Lenders move to restrict SpaceX orbital chip deployments worth $40 billion**
   Lenders are seeking to bar SpaceX from launching an estimated $40 billion in chips into orbit under covenants tied to existing financing agreements. The effort targets the company’s plans to expand orbital compute capacity linked to Starlink-adjacent hardware. No resolution timeline or alternative funding path has been disclosed in the filings. Source: [ft.com](https://www.ft.com/content/33b5643c-2957-4d42-9116-5e34a3c54e29?syn-25a6b1a6=1)

3. **SpaceX scrubs USSF-317 Falcon 9 launch and shifts target to Friday**
   SpaceX scrubbed the Thursday evening attempt of the USSF-317 mission from Vandenberg Space Launch Complex 4 East and now targets a four-hour window opening at 6:32 p.m. PST on Friday. Booster B1100 will fly its eleventh mission and aim for a landing on the droneship Of Course I Still Love You, which would mark the 235th landing on that vessel. The mission carries an undisclosed number of U.S. Space Force satellites on a south-easterly trajectory. Source: [ksby.com](https://www.ksby.com/news/launch-tracker/spacex-targets-thursday-night-for-falcon-9-rocket-launch) Source: [spaceflightnow.com](https://spaceflightnow.com/2026/11/19/live-coverage-spacex-to-launch-classified-payload-for-the-u-s-space-force-2/)

4. **SpaceX confirms Super Heavy booster splashdown and addresses debris reports after Flight 15**
   Recovery teams secured the area immediately after the Super Heavy booster performed a safe abort and splashed down in the Gulf off Starbase. Environmental Health and Safety personnel confirmed that recovered materials pose no chemical, biological, or toxicological risk. Specialists were dispatched to Mexican territory following social-media claims of widespread debris; ground partners reported very little material and none clearly attributable to SpaceX operations. The company described the majority of online reports as fabrications or intentionally misleading. Source: [t.co](https://t.co/ALNcWBQinC)

5. **Musk states colonies belong on Moon or Mars rather than free space**
   Elon Musk posted that building colonies on a substrate such as the Moon or Mars represents a later-stage approach compared with surface-based settlements. Source: [x.com](https://x.com/elonmusk/status/2123616621906596273)

6. **Tesla AI reaches Torment II difficulty in Diablo on AI4 hardware**
   Elon Musk reported that Tesla’s AI running on the AI4 computer has achieved Torment II in the game Diablo. Source: [x.com](https://x.com/elonmusk/status/2123726569206415815)

7. **Relativity Space completes Terran R second-stage hot-fire campaign on first attempt**
   The flight-one second stage finished a 10-second hot-fire test on the A2 stand at NASA’s Stennis Space Center in October, the stand’s first stage-level test since 1970. Teams then configured the stage for a full mission-duty-cycle burn exceeding 400 seconds that included an igniter hot fire and coast demonstration. The Aeon V engine completed the test without holds after propellant and helium loading. Source: [nasaspaceflight.com](https://www.nasaspaceflight.com/2026/11/relativity-update-1116/)

8. **NASASpaceflight releases Starship program update with Max Evans**
   NASASpaceflight published a new video interview with Max Evans covering the latest Starship development status and upcoming test plans. Source: [youtube.com](https://www.youtube.com/watch?v=2fj9-NCgIC4)

### Also Today
**Musk clarifies old Tesla China dance video contains no AI generation:** Elon Musk posted that the widely shared video is authentic footage and not AI-generated content. Source: [x.com](https://x.com/elonmusk/status/2123695317375992288)

**SciGuySpace notes consolidation among launch providers:** The account observed that multiple launch companies now appear to operate under unified structures. Source: [x.com](https://x.com/SciGuySpace/status/2123552053184418215)

## The Counterpoint
Lenders are attempting to block SpaceX from placing $40 billion worth of chips into orbit through financing covenants that predate the current orbital-compute expansion plans. The restriction arrives while Google, SpaceX, and Starcloud all advance concepts for data centers in space, raising the possibility that capital-market terms could slow deployment timelines. Resolution would require either renegotiated loan agreements or alternative financing that explicitly preserves launch rights for compute hardware.

### Engineering Deep Dive
Orbital AI satellites move the power and thermal problem from terrestrial grid constraints and land-use permits to sunlight availability and radiator sizing in vacuum. A sun-synchronous orbit keeps solar arrays illuminated for most of each pass, removing the day-night cycle that forces large batteries on lower orbits and thereby reducing mass that would otherwise be devoted to energy storage. Each satellite carries roughly one data-center rack of TPU silicon, so the mass budget must accommodate both the processors and the radiators needed to reject the heat they generate when running machine-learning workloads. The earlier Falcon 9 prototype already proved the chips survive launch loads and can run a Gemma 4 model, confirming basic functionality before scaling. Scaling to a full rack per satellite therefore hinges on whether the added radiator area and pointing accuracy stay within New Glenn’s payload envelope without driving structural mass beyond the point where solar power remains net positive. If the radiators can be sized to match the TPU thermal load at the expected orbit beta angle, the architecture avoids the ground-based cost of land, permits, and grid interconnection that currently dominate terrestrial AI clusters. The same mass trade also determines whether multiple satellites can be stacked on a single New Glenn flight or whether each requires its own dedicated launch, directly affecting the economics of building an orbital compute network. Blue Origin’s delayed schedule to January 2027 for the next New Glenn flight sets the earliest possible full-scale test window, giving Google additional time to refine radiator coatings and thermal-control algorithms before the 2029 mission.

### Market Watch
No SPCX quote was provided in the briefing.

SpaceX Daily is produced for listeners who track the hardware first.