# SpaceX Daily
> **Four Starshield launches in 43 days from one pad show how quickly the Space Force is scaling its classified constellation.**

### Top News

1. **USSF-385 marks the fourth Starshield launch in 43 days from Vandenberg**
   SpaceX will fly USSF-385 on a Falcon 9 from SLC-4E no earlier than 7:00 a.m. PDT Saturday. The mission follows USSF-366 on August 15, USSF-153 on September 10, and USSF-259 on September 17. The first three flights placed 23 satellites each into orbit while USSF-259 carried 17 satellites to a separate plane. Booster B1100 will fly its tenth mission and land on the drone ship Of Course I Still Love You. The cadence reflects Space Force use of Vandenberg while Cape infrastructure shifts toward Starship operations. Source: [keeptrack.space](https://keeptrack.space/x-report/spacex-brief-2026-09-26)

2. **Cursor releases Security Reviewer and Rollouts bots for post-merge checks**
   Security Reviewer scans code changes for injection flaws, broken authentication, committed credentials, unsafe deserialization, and dependency issues. It supplies severity ratings, attack-path explanations, and one-click fixes. Average review time dropped from 4.8 minutes to 3.8 minutes per session, with developers accepting suggestions 60 to 70 percent of the time. Rollouts builds monitoring plans before merges and compares live signals from Datadog, Grafana, or Honeycomb against baselines after deployment. It can pause rollouts or submit automated reverts when regressions appear. Source: [martincid.com](https://www.martincid.com/technology-sv/cursor-rollouts-security-review-ai-bots-developers/)

3. **Starship Flight 14 wet dress rehearsal completes successfully ahead of planned September 28 attempt**
   Ship 41 was stacked on Booster 21 for the test and then destacked on Friday while remaining at the launch site. Both stages reached full propellant load with no holds at the optional T-minus 60-second point. The count reached just before engine ignition before the launch mount deluge system activated. A near-term manifest lists Flight 15 no earlier than October 19 and Flight 16, carrying Starlink satellites, no earlier than October 30 from KSC 39A. Source: [nasaspaceflight.com](https://www.nasaspaceflight.com/2026/09/flight-14-starships-forward-path/)

4. **xAI plans three waves of 220,000 GB300 GPUs each to reach 1.44 million total chips**
   The first wave of 220,000 GB300 units is scheduled to become operational within days. A second wave follows in November and a third by late December if targets are met. Colossus 1 currently holds 230,000 accelerators while Colossus 2 holds 550,000. The expansion is centered around facilities in Memphis, Tennessee, and Southaven, Mississippi. Source: [remio.ai](https://www.remio.ai/post/spacexai-colossus-gpu-expansion-nears-1-44-million-chips-but-power-is-the-real-t)

5. **NASA adds $946 million to SpaceX crew contract, raising total value to $5.92 billion**
   The modification covers three additional crewed missions to the International Space Station. The updated agreement now spans 17 flights through 2030. Crew-13 remains scheduled for launch this Thursday. Source: [au.finance.yahoo.com](https://au.finance.yahoo.com/news/spacex-spcx-wins-946-million-235804734.html)

6. **Falcon 9 from Vandenberg will be the sixth launch from the site this month**
   The USSF-385 mission will use a southerly trajectory from SLC-4E. Residents in Santa Barbara, San Luis Obispo, and Ventura counties may hear sonic booms depending on weather. Source: [spaceflightnow.com](https://spaceflightnow.com/2026/09/25/spacex-falcon-9-to-launch-classified-mission-for-u-s-space-force-from-west-coast/)

## Community Buzz
Reddit users discussed whether Raptor engine bell metals could serve as heat-shield material given their exposure to higher temperatures than re-entry. The post questions why those alloys are not adapted for the upper stage thermal protection system. Another thread highlighted Scott Manley locating an FAA presentation listing Starship Flight 15 for October 19 and Flight 16 for October 30. Users noted the dates remain provisional and subject to slips. A separate post showed official images of Ship 41 and described the vehicle as science fiction turned into hardware now preparing for its first orbital attempt. Source: [reddit.com](https://www.reddit.com/r/SpaceXLounge/comments/1wq6crq/engine_bell_metals_as_heatshield/) Source: [reddit.com](https://www.reddit.com/r/SpaceXLounge/comments/1wq3wfa/scott_manley_finds_faa_presentation_that_reports/) Source: [reddit.com](https://www.reddit.com/r/SpaceXLounge/comments/1wpz7gv/starship_is_science_fiction_turned_into_reality/)

## The Counterpoint
Power delivery and cooling remain the binding constraints on the planned Colossus expansion to 1.44 million GPUs. Musk noted the final wave depends on whether the team gets lucky with infrastructure timelines. The schedule has not been independently verified and does not specify how many chips will stay continuously available for training versus maintenance. Source: [remio.ai](https://www.remio.ai/post/spacexai-colossus-gpu-expansion-nears-1-44-million-chips-but-power-is-the-real-t)

### AI & Compute

### Engineering Deep Dive
The engineering angle on Cursor’s new bots centers on shifting verification from human review to automated comparison against live baselines. Security Reviewer runs a full-codebase scan for each pull request and surfaces only the categories of flaw that survive ordinary peer review. That produces a measurable drop in review time from 4.8 minutes to 3.8 minutes while raising acceptance of suggested fixes from 45-50 percent to 60-70 percent. Rollouts extends the same principle into production by building an instrumentation map before merge and then comparing Datadog, Grafana, or Honeycomb signals against pre-deployment baselines. When a regression is isolated from an intentional change, the bot can pause the rollout or open a revert pull request before the issue reaches all users. The approach works only when source control, deployment, and observability systems are already connected; teams lacking that stack face setup overhead that can outweigh the benefit. The design therefore trades broad applicability for depth inside environments that already instrument their services at scale.

### Market Watch
SPCX is at $148.68, +0.6% versus the previous close.
