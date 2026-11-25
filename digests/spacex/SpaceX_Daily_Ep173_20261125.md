> **Amazon is moving its next Falcon 9 launch to December after losing 40 satellites on a Vulcan failure.**

### Top News

1. **Amazon accelerates Falcon 9 launches after Vulcan failure**
   Amazon told Ars Technica it is moving its next Falcon 9 launch for the Amazon Leo constellation from 2027 to December, with additional flights to follow quickly. The shift follows the November 15 Vulcan failure that destroyed 40 Amazon Leo satellites and the ongoing grounding of ULA’s Vulcan. An Ariane 6 launch on Tuesday added 36 more satellites, bringing the fleet to 432. SpaceX has already flown three batches of 24 Amazon satellites on Falcon 9 and holds ten more reserved flights. Amazon originally booked 108 launches across Western rockets to deploy 3,232 satellites, with seventeen of those flights completed and one failure. Blue Origin’s New Glenn remains grounded since May after a pad explosion, leaving Falcon 9 and Ariane 6 as the only active vehicles for Amazon hardware. Source: [keeptrack.space](https://keeptrack.space/x-report/spacex-brief-2026-11-25) Source: [arstechnica.com](https://arstechnica.com/space/2026/11/amazon-surges-launches-with-rival-spacex-after-ula-fails-to-deliver/)

2. **SpaceX launches USSF-266 classified payload from Vandenberg**
   A Falcon 9 lifted off from Space Launch Complex 4E at Vandenberg Space Force Base carrying a classified reconnaissance payload for the U.S. Space Force. The first stage, on its 29th flight, landed on the Of Course I Still Love You droneship. The mission had been scheduled for the prior day and lifted off after propellant loading began under favorable weather. SpaceX posted video of the ascent and confirmed the booster touched down on the droneship. Source: [spacex.com](https://www.spacex.com/launches/ussf266) Source: [x.com](https://x.com/SpaceX/status/2125342179216261600) Source: [space.com](https://www.space.com/space-exploration/launches-spacecraft/spacex-launches-secretive-spy-satellites-from-california-for-us-space-force-video)

3. **STARLINK-2558 drops 85 km in 89 days**
   The satellite now sits 150 km below its assigned working shell after losing 85 km of altitude over 89 days. Nine Starlink satellites currently carry active reentry predictions, though none appear on the high-risk conjunction list. No Starlink satellites show in the current SOCRATES top-probability conjunction list. Source: [keeptrack.space](https://keeptrack.space/satellite-of-the-day/sotd-2026-11-25)

4. **SpaceX forgoes up to $738 million in BEAD subsidies**
   SpaceX will still serve every rural location awarded under the Broadband Equity, Access, and Deployment program at no cost to the program after declining the federal funds. Reports place the forgone amount between $636 million and $738 million. The company gave up the subsidies but keeps the awarded service locations. Source: [teslarati.com](https://www.teslarati.com/spacex-starlink-rejects-fed-subsidy/)

5. **xAI expects Colossus wastewater plant restart in January**
   The Memphis facility is now projected to resume operations in January after the earlier pause. Local officials are tracking the timeline for the recycling plant tied to the growing compute campus. Source: [neoteo.com](https://www.neoteo.com/en/memphis-expects-january-restart-for-xais-wastewater-plant)

6. **Northrop confirms additional Falcon 9 flight for Cygnus after NG-25**
   Northrop Grumman has booked another SpaceX launch for a Cygnus cargo mission following the NG-25 flight. The new mission will continue the station resupply cadence using Falcon 9. Source: [teslanorth.com](https://teslanorth.com/2026/11/24/northrop-cygnus-spacex-falcon-9-after-ng-25/)

7. **SpaceX plans Sunday Falcon 9 launch of holiday supplies to ISS**
   The company is preparing a Falcon 9 mission from Florida to deliver holiday meals and other cargo to the International Space Station. The flight is listed for this Sunday. Source: [talkoftitusville.com](https://talkoftitusville.com/2026/11/24/spacex-planning-to-launch-supplies-to-iss-this-sunday/)

8. **Goldman Sachs projects sustained U.S. data-center power and gas demand through 2028**
   The bank expects the buildout to keep lifting electricity and natural-gas consumption as new facilities come online. The forecast covers the period through the end of the decade. Source: [idahostatesman.com](https://www.idahostatesman.com/news/nation-world/national/article318244254.html)

### Community Buzz
Elon Musk posted that Grok is so much fun on Tesla road trips. Source: [x.com](https://x.com/elonmusk/status/2125516475712844116)

A report states Musk admits SpaceX cannot compete in certain AI areas and is renting its GPUs to Anthropic and Google. Source: [pasqualepillitteri.it](https://pasqualepillitteri.it/en/news/36623/musk-spacex-cant-compete-rents-gpus)

The Motley Fool argues SpaceX will soon be 40 percent better as a space company. Source: [fool.com](https://www.fool.com/investing/2026/11/24/world-best-space-company-spacex-soon-40-better/)

Newsweek reports Elon Musk’s SpaceX data centers face key votes on the same day in December. Source: [newsweek.com](https://www.newsweek.com/elon-musks-spacex-data-centers-face-key-votes-on-same-day-in-december-12764916)

## The Counterpoint
Barron’s highlights that SpaceX’s valuation faces pressure from Anthropic’s potential IPO and the broader AI funding environment. The piece notes that investor comparisons between the two companies could affect how SpaceX is priced in public markets. The outcome will depend on how quickly Starlink cash flow scales against competing AI capital demands. Source: [barrons.com](https://www.barrons.com/articles/spacex-stock-price-anthropic-ipo-ai-a63c92d3)

### AI & Compute

xAI’s Memphis gas-turbine installation is being cited as an example of off-grid AI data-center design that avoids traditional utility constraints. The approach allows faster scaling of Colossus-class clusters while power infrastructure catches up. Source: [cryptobriefing.com](https://cryptobriefing.com/xai-memphis-off-grid-gas-power-data-centers/)

### Engineering Deep Dive
Falcon 9’s first-stage recovery relies on a single Merlin engine performing what engineers call a hoverslam. The engine cannot throttle below roughly 40 percent without losing the ability to adjust thrust, so the booster must begin its landing burn at 40–70 percent throttle while still moving fast enough for the remaining impulse to bring velocity to zero at the exact moment of touchdown. This single-engine constraint forces a precise, continuous throttle profile with no option to drop to a lower setting mid-burn.

Super Heavy takes a different path. It lights thirteen Raptors to cancel most of its velocity, then reduces to the center three engines for the final approach. Each of those three can still modulate between roughly 40 percent and full thrust, giving the vehicle a near-hover capability the tower arms require for capture. The staged burn therefore trades engine count for finer control authority at the moment of contact.

The difference shows up in hardware choices. Falcon 9 keeps landing legs because a single-engine hoverslam leaves little margin for position error. Super Heavy deletes the legs entirely, saving mass that would otherwise be carried to orbit on every flight. The trade-off is that the catch mechanism must now absorb the final positioning task that legs once handled.

### Market Watch
SPCX is at $125.81, -5.7% vs the previous close.

Back tomorrow with the next engineering update.