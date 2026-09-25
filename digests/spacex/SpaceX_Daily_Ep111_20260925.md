# SpaceX Daily
> **Google's first orbital AI satellite will test whether chips can shed heat in vacuum aboard a SpaceX launch next week.**

### Top News

1. **NASA names four astronauts for the Crew-14 mission to the ISS in 2027**
   NASA selected Kayla Barron as spacecraft commander, Chris Birch as pilot, JAXA astronaut Makoto Suwa, and Roscosmos cosmonaut Arutyun Kiviryan. Barron previously flew on Crew-3 in 2021 and will return for a second mission. Birch, Suwa, and Kiviryan will each make their first spaceflight. The crew will join Expedition 75/76 and conduct science experiments during a long-duration stay. Source: [starlust.org](https://starlust.org/nasa-announces-four-astronauts-heading-to-iss-on-space-x-crew-14-mission/)

2. **SpaceX completes wet dress rehearsal for Starship Flight 14**
   The company loaded propellants and ran launch-day procedures on September 24 without engine ignition. Flight 14 targets an orbital insertion burn for the upper stage, six Earth orbits, and deployment of 26 next-generation Starlink satellites. The Super Heavy booster is planned to splash down in the Gulf of Mexico while the Ship upper stage reenters in the Pacific west of Chile. The launch window opens September 28 at 5:45 pm IST from Starbase, Texas. Source: [indiatoday.in](https://www.indiatoday.in/science/story/spacex-starship-flight-14-wet-dress-rehearsal-space-elon-musk-nasa-moon-mars-space-rocket-3002617-2026-09-25)

3. **Dragon spacecraft arrives at Cape Canaveral for Crew-13 launch on October 1**
   The refurbished capsule reached Pad 40 and will mate with its Falcon 9 booster. Commander Jessica Watkins will lead pilot Luke Delaney and mission specialists Joshua Kutryk and Sergey Teteryatnikov. The booster is flying its third mission. Docking is targeted for 8 pm EDT on launch day. Source: [starlust.org](https://starlust.org/space-x-dragon-spacecraft-arrives-at-cape-canaveral-for-october-1-launch-of-nas-as-crew-13/)

4. **NASA awards SpaceX nearly $1 billion contract for three flights**
   The award covers three additional crew rotation missions to the International Space Station. It extends SpaceX's role in sustaining the station through at least 2030. Source: [wacotrib.com](https://wacotrib.com/news/local/business/article_701d1b45-f6cc-42df-9792-e7e455f855c2.html)

5. **Google's Project Suncatcher prototype will fly on SpaceX Transporter-18**
   The satellite will test Trillium TPUs in orbit, collecting data on launch vibration, radiation, and thermal performance. It will run Gemini models in 15-minute bursts followed by radiator cooldown periods. A 2027 follow-on mission will test laser links between two satellites. Source: [inews.zoombangla.com](https://inews.zoombangla.com/project-suncatcher-ai-satellite-cooling-test/)

6. **Starlink Mobile launches in Uganda through Airtel partnership**
   The service brings direct-to-cell connectivity to users in Uganda. It expands Starlink's carrier-partner model for mobile coverage in additional markets. Source: [basenor.com](https://www.basenor.com/blogs/news/starlink-mobile-launches-in-uganda-via-airtel-partnership)

7. **SpaceX secures classified orbital tracking contract**
   The award supports national-security tracking capabilities as Starship Flight 14 approaches. Details remain limited due to the classified nature of the work. Source: [ad-hoc-news.de](https://www.ad-hoc-news.de/boerse/news/unternehmensnachrichten/spacex-wins-classified-tracking-deal-as-starship-14-nears-its-debut/70177965)

8. **Transporter-18 rideshare mission is scheduled for next week**
   The mission will carry multiple small satellites, including Google's first Project Suncatcher prototype. SpaceX published the manifest on its launch page. Source: [spacex.com](https://www.spacex.com/launches/transporter18)

## Community Buzz
Reddit users are discussing whether a mid-October drive from Denver to Starbase is worth the time if most hardware has already rolled to the pad. Another thread highlights the October 1 Florida doubleheader featuring Crew-13 at 11:10 a.m. EDT and an NROL-97 Falcon Heavy at 11:53 p.m. EDT, with three booster landings possible in twelve hours. Observers note the potential for a historic single-day cadence at the Cape. Source: [reddit.com](https://www.reddit.com/r/SpaceXLounge/comments/1wpls3v/worth_visiting_this_october/) Source: [reddit.com](https://www.reddit.com/r/SpaceXLounge/comments/1wpbjho/october_1st_florida_doubleheader/)

## The Counterpoint
One thing worth watching is the pace of Starship Flight 14 regulatory approvals. The FAA license remains pending even after the wet dress rehearsal, and any extension would push the first orbital attempt beyond the current September 28 window. Resolution depends on completing the standard safety review without new issues surfacing in the data. Source: [indiatoday.in](https://www.indiatoday.in/science/story/spacex-starship-flight-14-wet-dress-rehearsal-space-elon-musk-nasa-moon-mars-space-rocket-3002617-2026-09-25)

### AI & Compute

### Engineering Deep Dive
From an engineering standpoint, removing air as a heat-transfer medium forces a complete redesign of how processors reject waste heat. On the ground, forced-air cooling moves heat at rates set by fan speed and surface area, but in orbit the only path left is radiation through pipes and deployable panels whose effectiveness scales with the fourth power of temperature. The Suncatcher prototype therefore cycles its TPUs on for fifteen minutes and then idles while radiators shed stored energy, a duty cycle chosen because continuous operation would exceed the thermal mass available before the next eclipse. Early chamber tests already showed the pipes can move the expected kilowatt load, yet orbital data will reveal how micro-vibrations and proton damage alter emissivity over weeks. If the radiators maintain margin, the same architecture could support larger clusters whose power budget comes from near-continuous sunlight rather than ground-based solar farms limited to daylight hours. The next milestone, laser-linked pairs in 2027, will test whether data movement between nodes adds its own heat load that the same radiator set must also reject.

### Market Watch
SPCX is at $148.03, +0.2% vs the previous close.

One-sentence sign-off
