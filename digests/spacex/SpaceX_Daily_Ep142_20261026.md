# SpaceX Daily

> **SpaceX fired all 33 Raptor engines on the Super Heavy booster for a full-duration static fire, clearing the immediate next step for Starship Flight 15.**

### Top News

1. **SpaceX completes full-duration static fire of all 33 Raptor engines on Super Heavy booster**
   The test ran the complete set of engines for the planned duration ahead of Starship Flight 15. SpaceX posted video confirming ignition and sustained operation on the launch mount. The booster remained secured throughout the burn. This marks the immediate next step after earlier cryo-proof testing on Booster 23 and Ship 43. The full-duration run validates engine performance, propellant feed systems, and ground support equipment under flight-like conditions before the vehicle moves to the pad. Source: [x.com](https://x.com/SpaceX/status/2114444137067844004) Source: [x.com](https://x.com/MarioNawfal/status/2114527431143174314/video/2)

2. **NASA reaffirms 2028 crewed Moon landing target with back-to-back docking tests**
   NASA Administrator Jared Isaacman stated the Artemis 3 mission will spend 14 to 17 days in low Earth orbit next summer practicing sequential docking of Orion with prototype landers from SpaceX and Blue Origin. The agency cited concerns over potential schedule slippage relative to China as the reason for accelerating private-company participation. Jeremy Parsons, head of the Artemis program, described the test as the first time NASA will launch three spacecraft separately and verify integrated operations. The plan shifts Artemis 3 from an immediate landing attempt to a risk-reduction docking rehearsal while Artemis 4 targets the 2028 landing. Earlier fuel leaks and helium-flow anomalies on the Artemis 2 launch vehicle prompted the revised timeline. Source: [finance.biggo.com](https://finance.biggo.com/news/46fcb266-0251-49f5-833e-2d38a9f07b48) Source: [biz.chosun.com](https://biz.chosun.com/en/en-science/2026/10/26/N3HVBL7IENAS5FZCPK443TALCM/)

3. **SpaceX applies to expand Roberts Road campus at Kennedy Space Center**
   The company seeks to grow the site from 167 acres to nearly 400 acres to support Starship operations ahead of Flight 16. Plans include a new Gigabay, Project Ignition ship static-fire stands, a Payload Processing Facility, and a connecting road to NASA Parkway. Existing Hangar X-2 currently handles Dragon processing, Starlink payloads, and tile production while the first Gigabay is already under construction. The expansion would also add a Starfactory and additional infrastructure to handle multiple Starship vehicles simultaneously at the Florida site. Source: [nasaspaceflight.com](https://www.nasaspaceflight.com/2026/10/roberts-road-expansion-flight-16/)

4. **Boeing begins Starshield installations on Air Force C-17 Globemaster III aircraft**
   Technicians at Port San Antonio have completed work on nine jets under two contracts totaling $13.5 million. The program will equip 19 aircraft by March, with the Air Force intending to outfit its full fleet of 222 Globemasters. Starshield provides the communications link for the Airlift/Tanker Open Mission Systems suite, enabling mission-data sharing during global cargo and troop transport. Sierra Nevada Corp. supplies the Starshield and ATOMS equipment kits used in the upgrades at the 1.6-million-square-foot Boeing facility. Source: [hoodline.com](https://hoodline.com/2026/10/boeing-wires-spacex-tech-into-air-force-jets-at-port-san-antonio/) Source: [expressnews.com](https://www.expressnews.com/business/article/boeing-starshield-air-force-port-san-antonio-22488178.php)

5. **Ship 43 moves onto Highway 4 at Starbase under moonlight**
   The upper stage was observed turning onto the highway, continuing ground transport operations at the Texas site. The move follows completion of cryo-proof testing and positions the vehicle for further processing ahead of Flight 15 or 16. Source: [x.com](https://x.com/NASASpaceflight/status/2114572229958574344)

6. **SpaceX raises $40 billion in debt financing**
   Elon Musk disclosed the debt deal and predicted consolidation among competing cloud providers. The financing supports ongoing capital needs across launch, satellite, and infrastructure programs. Source: [thestandard.com.hk](https://www.thestandard.com.hk/finance/article/346486/Musk-says-SpaceX-raised-US40-billion-in-debt-deal-predicts-neocloud-shakeout)

7. **T-Mobile and Verizon urge FCC to delay Starlink Mobile approvals**
   The carriers filed comments opposing accelerated licensing while SpaceX advances plans for terrestrial cell towers supporting the direct-to-cell service. The filings argue that additional review is needed before the FCC grants further spectrum or operational authority for the mobile offering. Source: [notebookcheck.net](https://www.notebookcheck.net/T-Mobile-and-Verizon-press-FCC-to-slow-Starlink-Mobile-as-SpaceX-plans-cell-towers.1433915.0.html)

8. **Erste Group Bank raises SpaceX earnings estimates**
   The bank increased its projections for the company following recent operational updates. The revision reflects stronger visibility into launch cadence and Starlink subscriber trends. Source: [marketbeat.com](https://www.marketbeat.com/instant-alerts/estimates-spacex-stock-earnings-estimates-lifted-by-erste-group-bank-2026-10-26/)

### Also Today
**Lift to catch height completed on Starship tower:** NASASpaceflight reports the tower arms reached full catch height during recent operations at Starbase. Source: [x.com](https://x.com/NASASpaceflight/status/2114575721012052294)

## The Counterpoint
Ukrainian officials rejected Elon Musk’s assertion that commercial Starlink terminals were used for offensive drone strikes, stating that speed limits and geographic restrictions already prevent such missions and that satellite-dependent operations rely instead on the government-controlled Starshield system. Kyiv maintains the service restrictions disrupted air-defense and drone coordination before speeds were restored. The episode has prompted Ukrainian and European partners to explore alternative satellite communications networks, including a proposed Nokia and ICEYE collaboration. Source: [abc45.com](https://abc45.com/news/nation-world/ukraine-disputes-elon-musk-claim-starlink-was-used-for-offensive-drone-strikes)

### Engineering Deep Dive
The 33-engine static fire on the Super Heavy booster tests the vehicle’s ability to tolerate engine failures without losing the ascent trajectory. Early flight data established that liftoff remains achievable with three engines out, leaving thirty operational, because excess thrust margin grows as propellant mass decreases during the burn. Isolation valves and independent turbopump controls prevent a single chamber failure from propagating to adjacent engines, preserving the remaining thrust vector. This redundancy directly reduces the probability of an early mission abort and supports the program’s goal of recovering both stages on the same flight. The test also validates the hold-down hardware and flame trench under full-duration loads, confirming that the pad systems can manage the thermal and acoustic environment for the full propellant load. As propellant is consumed, the thrust-to-weight ratio rises, allowing later engine losses to be tolerated even if they occur higher in the atmosphere where aerodynamic forces are lower. These margins are the reason SpaceX can accept a higher engine count than historical boosters while still targeting first-stage recovery on every flight.

The same engine-out tolerance carries implications for the upper-stage Ship once it separates. With fewer engines but a lighter vehicle, the Ship can accept single-engine failures during its own burn profile because the remaining Raptors still deliver sufficient delta-v to reach the required orbit or deorbit target. The static-fire data from the booster therefore informs software limits and abort triggers that apply across both stages. Engineers use the test results to refine the thrust-vector-control authority margins, ensuring the vehicle can steer even when one or two chambers are offline. The full-duration hold-down also stresses the propellant tanks and feed lines at flight pressures, exposing any micro-leaks or valve timing issues before they reach the pad. This ground-test approach collapses the cost of discovering problems compared with an in-flight anomaly, because the hardware stays on the mount and can be inspected immediately.

The tower catch system itself benefits from the same static-fire campaign. The mechanical arms must withstand the acoustic and thermal loads of a full 33-engine burn at close range, and yesterday’s test confirmed the flame trench and water-deluge systems can protect both the booster and the tower structure. With the arms now at catch height, the next integration step is verifying the load path from the booster’s hard points through the tower legs into the foundation. Each additional static fire reduces uncertainty in the catch loads, moving the program closer to the first attempted recovery of both the Super Heavy booster and the Ship upper stage on the same flight.

## The Counterpoint Source: [abc45.com](https://abc45.com/news/nation-world/ukraine-disputes-elon-musk-claim-starlink-was-used-for-offensive-drone-strikes)

### Market Watch
SPCX is at $147.49, +1.9% vs the previous close. SpaceX disclosed a $40 billion debt raise in parallel with the earnings estimate revision.

SpaceX keeps pushing the hardware forward—one test, one pad, one vehicle at a time.
