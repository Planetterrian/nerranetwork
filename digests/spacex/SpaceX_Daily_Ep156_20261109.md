# SpaceX Daily

> **Starship Flight 15 targets the first catch of both stages next week.**

### Top News

1. **NASA is altering its lunar spacesuit design because of Artemis IV schedule pressure**
   The change comes two months after the prior update on the same topic. NASA is shifting the approach to keep the overall lunar landing timeline intact. The adjustment addresses concerns that the original suit development path would slip the crewed landing target. Reports indicate the redesign aims to reduce development risk without altering the core requirements for lunar surface operations. No specific new suit architecture details have been released publicly yet. Source: [arstechnica.com](https://arstechnica.com/space/2026/09/wary-of-artemis-iv-timeline-nasa-is-changing-lunar-spacesuit-design/)

2. **Starship Flight 15 will attempt tower catches of both the Super Heavy booster and the Ship**
   The mission is targeted no earlier than November 13 from Starbase with a 75-minute window opening at 4:45 p.m. CT. Booster 22 and Ship 42, both Block 3 vehicles, are assigned to the flight. The booster is scheduled to return for catch about 6 minutes 35 seconds after liftoff. The Ship will deploy 26 Starlink V3 satellites into a roughly 275 km orbit, perform 14 orbits, and attempt a return catch only after systems checks confirm readiness for reentry and landing burn. Three of the satellites carry cameras to inspect the heat shield. Each Starlink V3 satellite adds 1 terabit of capacity, so the full set equals roughly 10 Starlink V2 Mini launches on Falcon 9. The booster return marks the first catch attempt for a Super Heavy V3 vehicle. The Ship return would be the first time an upper stage has been caught after reaching orbital velocity. Source: [keeptrack.space](https://keeptrack.space/x-report/spacex-brief-2026-11-09)

3. **Elon Musk stated that SpaceX’s Anthropic compute contract works both ways on termination**
   Either party can exit on 90 days’ notice. Musk noted that if compute becomes plentiful and cheap, SpaceX revenue would drop. The contract runs through May 2029 at $1.25 billion per month. The same termination terms appear in later SpaceX compute deals with Google and Reflection AI. Political shifts in Texas, including the incoming governor’s call for a data-center moratorium, form the backdrop for recent discussion of the clause. Musk emphasized symmetry: no party should expect one-sided gains if market conditions change. Source: [teslarati.com](https://www.teslarati.com/spacexs-anthropic-deal-has-a-catch-and-elon-musk-just-addressed-it/)

4. **SpaceX revenue this quarter is projected to exceed NASA’s full fiscal 2027 budget request**
   The figure tops the $18.8 billion NASA request. NASA also selected Starship to launch lunar communications satellites in 2028. Deutsche Bank reaffirmed its Buy rating on SPCX, citing political retaliation risks as larger than near-term business risks. SpaceX plans to begin launching Nvidia-co-designed StarMind computers in Q3 2027, with deployment ramping in 2028 and 2029. Source: [tradingview.com](https://www.tradingview.com/news/tradingview:f8dc8a3b4be05:0-key-facts-revenue-tops-nasa-budget-ai-data-leases-nasa-picks-starship/)

5. **SpaceX plans a $24 billion supercompute center and gas plant at Starbase**
   The 444-acre facility near the Port of Brownsville would use up to 35 temporary gas turbines for an initial 748 MW output. A December public hearing is scheduled on tax abatements and economic development agreements. The site already has applications for mass grading and air-quality permits covering the turbines. Job postings reference the “Starbase supercomputer” and its on-site power generation model. The project forms part of a broader push toward 13 GW of total AI compute capacity by the end of 2027. Source: [cryptobriefing.com](https://cryptobriefing.com/spacex-24-billion-ai-supercomputer-starbase/)

6. **A Falcon 9 launch from Vandenberg SFB is planned for Monday evening**
   The mission remains on the current manifest with no payload details released. The launch would mark another step in the record 2026 cadence from the California site. Source: [ksby.com](https://www.ksby.com/news/launch-tracker/spacex-falcon-9-launch-planned-for-monday-evening-out-of-vandenberg-sfb)

7. **Elon Musk highlighted Starlink’s role in a mountain rescue in Kazakhstan**
   Five people stranded in snowy terrain were reached because Starlink provided connectivity where no cell towers existed. The incident shows the system’s value for emergency response in remote areas. Source: [teslarati.com](https://www.teslarati.com/elon-musk-spotlights-the-starlink-rescue-that-got-through-where-no-cell-tower-could/)

8. **SpaceX is no longer selling commercial Starship launches**
   There is no clear path for traditional payloads on the vehicle at present. The shift reflects internal priorities around rapid iteration and Starlink deployment rather than external commercial sales. Source: [x.com](https://x.com/SciGuySpace/status/2119474443441377488)

## The Counterpoint
NASA’s decision to redesign the lunar spacesuit this late in the Artemis IV cycle highlights how suit development has become a pacing item for the overall program. Any further iteration risks pushing the first crewed landing beyond the current target date. The change also underscores that hardware qualification timelines remain difficult to compress even when the launch vehicle itself is ready. Historical parallels with earlier NASA suit programs show repeated schedule pressure from certification requirements that cannot be fully parallelized with vehicle development.

### AI & Compute
SpaceX plans to lease data-center capacity to other companies before Grok needs it while outlining AI-chip facilities in Texas. The company is tracking toward an annualized revenue rate above $100 billion in December with a best guess of $500 billion by December 2027, driven in part by AI infrastructure. Musk stated that SpaceX is “getting 50 billion a year for 35 billion dollar investments” and can bring a data center online in eight or nine months. The Anthropic contract alone represents nearly $45 billion over its term at the current rate. Source: [tradingview.com](https://www.tradingview.com/news/tradingview:f8dc8a3b4be05:0-key-facts-revenue-tops-nasa-budget-ai-data-leases-nasa-picks-starship/) Source: [teslarati.com](https://www.teslarati.com/spacexs-anthropic-deal-has-a-catch-and-elon-musk-just-addressed-it/)

### Engineering Deep Dive
Starship’s choice of 33 Raptor engines on the Super Heavy booster follows directly from the physics of lifting a roughly 5,000-ton vehicle while preserving full reusability and engine-out capability. Each Raptor 3 produces between 230 and 250 metric tons of thrust at sea level, so the full set supplies the 18 million pounds of thrust required at liftoff. Using many smaller engines instead of a few very large ones avoids the combustion instability and fabrication limits that historically constrained single-chamber designs such as the Saturn V’s F-1. The same engine count also enables the booster to shut down a subset of engines for boostback and landing burns without losing control authority. Production of smaller engines at high volume further reduces per-unit cost and allows rapid iteration on turbomachinery and chamber materials. The net result is a first stage that can return to the launch site, be caught by the tower, and fly again with minimal refurbishment.

Super Heavy is 9 meters wide and carries separate liquid oxygen and liquid methane tanks separated by a common bulkhead, a structural approach also used on the Saturn V’s S-II and S-IVB stages. The booster’s current Block 3 configuration stands 72.3 meters tall. This layout keeps the vehicle’s center of mass manageable during ascent and return while allowing the 33 engines to be arranged in a pattern that supports both full-thrust liftoff and partial-thrust landing profiles. The design trades some added plumbing complexity for the ability to lose multiple engines and still complete the mission profile.

Raptor itself is the first full-flow staged combustion engine to reach flight. It burns liquid methane and liquid oxygen at a total propellant flow rate of 650 kilograms per second. Sea-level versions produce 230 to 250 metric tons of thrust while vacuum-optimized versions reach 258 to 275 metric tons. The engine’s reusability target aligns with airline-level reliability goals, which in turn supports the economic case for catching both stages rather than expending them. These parameters together determine why 33 engines, rather than a smaller number of larger units, became the baseline for the Super Heavy booster.

### Market Watch
SPCX is at $134.27, +8.6% vs the previous close.

That's SpaceX Daily for November 9.
