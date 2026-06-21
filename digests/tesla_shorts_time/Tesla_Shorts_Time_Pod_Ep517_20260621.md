# Tesla Shorts Time — Weekly Recap (Week of June 21, 2026)

Hey, welcome to Tesla Shorts Time Daily, episode 517. Patrick here in Vancouver. It's June 21, 2026. Here's your Tesla news rundown.

The week's biggest developments, pulled together — what actually moved, why it matters, and what to watch next.

Danish regulators approved Tesla's supervised Full Self-Driving package for public roads this week.

The clearance came after local testing and adds another European Union market for the feature.

At the same time, legal action in Europe over marketing claims versus delivered performance is moving forward.

The case centers on statements about Full Self-Driving capabilities compared with what the system actually provides in those markets.

Fresh reports also showed supervised FSD avoiding animals on roads and completing door-to-door trips without driver intervention in tested scenarios.

Remember, the show last covered FSD unsupervised on episode 516, and this approval moves the supervised expansion forward while the regulatory path for unsupervised operation stays the main open question.

Attentive listeners will watch whether other Nordic countries follow Denmark's lead in the coming weeks.

Upcoming FSD releases will add Grok voice control and stored parking preferences. The system will recall prior parking locations and habits without new driver input. These features aim to reduce repeated manual steps in familiar settings. Development ties into broader software updates for the supervised stack. Owners can expect the changes in a future software branch.

FSD v14.3.4 specifically avoided a squirrel in one documented clip. Separate reports showed the system preventing sideswipes in a dangerous situation. FSD Supervised enables door-to-door autonomous driving in additional tested cases. Tesla FSD Saves Animal Lives appeared in multiple fresh clips this week.

On the product side, the lowest-priced Cybertruck trim at fifty nine thousand nine hundred ninety dollars began reaching early owners this week.

The variant trims range and features compared with higher trims but expands the lineup for more buyers.

Tesla is also validating a longer-wheelbase Model Y for potential U.S. production while Cybertruck volume grows.

A slightly stretched Model Y variant was photographed on roads in San Jose.

The Model Y L is currently built only at Gigafactory Shanghai, and the sighting points to early U.S. validation work.

Elon Musk had indicated a possible year-end U.S. arrival, though he called the timing uncertain.

This connects to the ongoing next-gen vehicle program last reviewed on episode 515, where cost-reduction targets remain the central open question.

Hardware updates like the Model Y L sit alongside deeper software and training infrastructure work inside Tesla.

Tesla filed new patents aimed at improving Dojo training efficiency on imperfect Ethernet networks.

One patent uses on-chip cache and linked lists to retransmit only missing segments instead of restarting entire streams.

A second patent moves flow control and acknowledgments into a custom MAC block for faster hardware-managed links.

These changes target higher training throughput for both Full Self-Driving and Optimus development.

Remember, the show last covered HW5 and Dojo on episode 513, and these filings address the production timeline and scaling questions still open for the next-generation hardware.

Tesla’s WO 2024/039800 patent describes a micro-architecture that stores recent packets in on-chip cache or SRAM as small as 256 KB and uses linked lists to track transmission order. When an acknowledgement fails or a timer expires, hardware pointers identify only the missing segment for replay instead of restarting the stream.

Four pipeline stages handle stream selection, link identification, replay-or-retire decisions, and pointer updates without software intervention. A hardware link timer working with FIFO memory checks multiple links in round-robin fashion and adapts its tick period as the number of active links changes.

This approach keeps Dojo training throughput high even on a controlled but imperfect Ethernet fabric.

Tesla’s WO 2024/039794 patent moves transport-layer functions including flow control, acknowledgements, and replay into a TTP MAC block that operates across OSI layers 2–4. Frames carry a specific EtherType such as 0x9AC6 so standard Ethernet switches can forward them while TTP endpoints manage state in hardware.

Link state machines transition through closed, open-sent, open-received, open, close-sent, and close-received without TCP-style TIME-WAIT periods. Bounded packet transmission plus local storage supports the design.

Tesla suspension patent builds on 1998 Lincoln Mark VIII tech. Tesla’s new design pairs low-rate parallel air springs with series dampers for most ride duties. The active actuator only corrects when needed, cutting energy use compared with fully active systems. The approach draws from the 1998 Lincoln Mark VIII’s air suspension but adds passive-dominant tuning.

This could help preserve range on vehicles that already carry heavy battery packs.

Starlink ran advertisements during the UFC Freedom 250 broadcast on Paramount+.

The placement reached a large live sports audience and overlaps with Tesla's brand exposure through shared SpaceX channels.

Wedbush analyst Dan Ives released a note calling SpaceX's IPO pricing a Goldilocks outcome that avoided draining capital from the broader tech trade.

Ives pointed to continued AI infrastructure spending and named Palantir, Snowflake, and Datadog as beneficiaries.

President Trump confirmed Starlink will equip the next Air Force One.

The Boring Company commissioned its second Prufrock machine, Prufrock MB2, for the Music City Loop in Nashville.

The addition doubles tunneling capacity for the project.

Work continues on the initial airport-area segment.

South Korea let an EV purchase tax incentive expire, raising prices for most models.

Tesla vehicles retain favorable treatment under existing rules, creating a relative price advantage.

Local analysts expect the shift to steer some buyers toward Tesla in the second half of the year.

Tesla and Ford engineers disassembled Chinese-market EVs to study battery integration and assembly methods that lower production expenses.

The findings are feeding into both companies' own cost-reduction programs.

This competitive analysis work echoes Tesla's ongoing efforts at home to match or beat overseas manufacturing approaches.

Chinese firm Hina Battery has developed sodium-ion cells whose energy density is nearing levels seen in current Tesla packs. The chemistry offers potential cost and supply-chain advantages over lithium-based systems. No deployment timeline with Tesla has been disclosed. Tesla Locks Down "AMAZING ABUNDANCE" Trademark Spanning Robotics, AI Chips & Robotaxi.

The trademark filing covers multiple future product categories in one action.

Now, one thing worth watching is the advancing legal case in Europe over Full Self-Driving marketing claims.

The action focuses on the gap between advertised performance and what supervised systems currently deliver in those markets.

While regulatory approvals like Denmark's expand supervised access, the case highlights the risk that overstated claims could slow broader acceptance.

Tesla's position rests on continued data collection and software iteration to close that gap over time.

The patents on Dojo hardware replay and TTPoE links break down a core training bottleneck.

Standard Ethernet can drop packets, forcing full restarts that waste compute cycles.

By handling retransmission and flow control in hardware with small caches and custom state machines, the designs keep pipelines moving without software overhead.

This matters because Dojo throughput directly affects how quickly new Full Self-Driving and Optimus models improve.

The open question remains how soon these gains translate into measurable training speed increases at scale.

Before we go, keep an eye on whether additional European regulators follow Denmark's supervised FSD approval in the next few weeks.

That's your Tesla news for today. T S L A closed at four hundred dollars and forty-nine cents, up, four dollars and eleven cents, one percent. If you found this useful, a rating or review on Apple Podcasts or Spotify really helps new listeners find the show. You can also find us on X at tesla shorts time. I'm Patrick in Vancouver. Thanks for listening, and I'll see you tomorrow.

And before you go — this show is part of the Nerra Network, a family of daily podcasts covering tech, science, markets, and more. If you enjoyed today's episode, give Modern Investing Techniques a listen: modern strategies for Canadian and U.S. investors. You can explore the whole lineup at nerranetwork.com.

## Sources
- [reddit.com](https://www.reddit.com/r/teslainvestorsclub/comments/1u6awog/weekly_tesla_brief_jun_8_jun_14_2026/)
- [x.com](https://x.com/tslaming/status/2066847254393073723)
- [x.com](https://x.com/tslaming/status/2066828406008979792)
- [x.com](https://x.com/tslaming/status/2066787688343314557)
- [x.com](https://x.com/Tesla/status/2066625079824494908)
- [Google News](https://news.google.com/rss/articles/CBMiqAFBVV95cUxQR0NhR0NwVmNzT0g1dTVDdXVZSEV6Uld3Z0NwTGNTMWFjZ2t1NVdmR2I0SXNDWUMzYkNfRlBOeWF1VnoyckszMmoxdEc5eVdaOVBVOGR6QXJuakR5T251UFZuNGdDR1UxSno4SzFfN1dQM1lkcTdfT3pkZFQwMFZzUlJFMFZIX0g4R0t5bFFPaHNWVGlwX2ZSeTFpbnpQZk5XT1ptMVRTcjY?oc=5)
- [notateslaapp.com](https://www.notateslaapp.com/news/4299/over-100-tesla-cybercabs-spotted-staging-at-giga-texas)
- [notateslaapp.com](https://www.notateslaapp.com/news/4282/tesla-to-build-pre-assembled-megachargers-for-tesla-semi)
- [Google News](https://news.google.com/rss/articles/CBMi0gFBVV95cUxOSFVSS05saXZ6a2lERWZSS2hzR25ZMXc3eFl0bThsZ2xnWWltams0MUVJNGpfMzEza2tjTm1LWWRXYlV2OEZfa214SHViNzY3VU0tam9ZRG5fTUdPSEwwWlhQTE9tLTlkMnc3QmZscGR0NG5IcElaLXhicW1QaVhEbXBjVUFxUHFCOTFtbFNPcGRVMFU5N3hHMndGZkVQZFFETDFDRDZ3NUpPbWVVM2xwalFQc2hNbUlucERfMTZTWjJ2LXl4UzUtdzViVTJSU1prQ3c?oc=5)
- [teslarati.com](https://www.teslarati.com/spacex-soars-first-launch-public-company-new-era/)
- [Google News](https://news.google.com/rss/articles/CBMiiwFBVV95cUxQNjlCREFvVUlkZjdkOFFNWEZLRDFNZUdEU0VnTHdmaW1pdEJLaUVkQWlwdEk2VkRmMWtWWGotLUlwQk04YmxTUjBBZUJfNEZUVTc5OGZfNDVWazNkSEI6clRwdU)
- [Google News](https://news.google.com/rss/articles/CBMimAFBVV95cUxNNDk2aWlfT1FzandkdUV0WVNELWZ2SlNmZWkwVFFmMVRGeFRrTzRmWnlOZnhOVEdKNTZOTVdYTG1aT1FaZlhna0cwc0diTlg0dEs3cEZwR3JDMTF4OS1IMlI3QnRWd0pEOVhJYnpfajNXMkFjNUt0bFQxZ2NqcXlRQ0V3bkF0Z1otTm5mYXFMMDhuUFhYV21LdQ?oc=5)
- [Google News](https://news.google.com/rss/articles/CBMi5gFBVV95cUxPZG9HR3RWcDRxaU4yeXhCTENONVdMQWtmUlJZX05iQU1kUHpiTXpHSWpIVmlCbl9TQmh4STVmc0hQdmF2VjQzcy1Md3QwZ3JoXzljRjdYNmR0RURIeXZ1Y0l3NlZ2TFFYc1BnU0xTQzk4WjFtaWdITmp5M0hjQU1NX0prS19VM0hkM1gxbkZ3anhqWlBxemM0T0JRZTVPdEZWWkJEY2toZ2VVbnh3dm1BdkkzSEtOR2taWlQ2c0tWbmctQUdfY0N2NkxMTlpkWGxVYkVsR1I2ZExxd2M3Z19FSEhEZGdMUQ?oc=5)
- [x.com](https://x.com/Teslarati/status/2066663090914013276)
- [x.com](https://x.com/Teslarati/status/2066632090121130480)
- [Google News](https://news.google.com/rss/articles/CBMikwFBVV95cUxQY0tyMUdYWTdqY244b0JmWV9MZUJ5UmpLMVFaVkVBb1VmZTRWRi1OV3Jvb0JXV1h3YlVIU2FqS1ZGTUZBendFM0g5MkRoY1JzRGRvY2d3NEEtY0NzSkdlREp0OE1vcVQtWkU2Qmk2YUlrZF9jRkhYWVpSYWpMLVVRWnIxRDY3ZjVGTW5relVmVFM4dVU?oc=5)
- [Google News](https://news.google.com/rss/articles/CBMikgFBVV95cUxPMnRyNmFWaGh2WER0bEgxejVmbGRxZXNHUlZEVmNZd2U5NUpmejlQdUlEZmdZTHhhQWNsaEFOSWdNWkJXNW0yZXB5SVFBSmlhdFlEZkhXZFpsME1YM2NnemNBMUdxSkd0b0lJajVCMy0xRTBabWRBOEJWWGYwQmRCVEtBczJWOWRxZExZQ1FENzlFZw?oc=5)
- [Google News](https://news.google.com/rss/articles/CBMikAFBVV95cUxQenZ5cElkWmFYdGlPQU5KMERaNDF0NzNrSlZ5R3h3Vjk5MG1DVFFZSlpGMEVpc2h6ZmVlMDBqSGhZbzFYYnNUQ1cwZFRpbTZZbVNtYWJFTU5LM0FQQkdBUzJHNTJMQS1XNG5SR2diWVUybWhaQm5zYXZPUmJZMFhaZ29mUl9Uem9WQV9jTm8xS0rSAZgBQVVfeXFMTzhGTFg3Z1dMVFJSeGpfRnRLdm44LUZjekFuZEROSWVPSU9FcWJ2YXdYWjFhU0FZZm12M195WEZfU1JNdHZkTDBBWW9xc0tuSDBLelVQbkw0MlhNVGJIWXpNOXBqYVRwX3JaQ2VIU09rdElTTmRZT2NMZDlPa2J5MVJUc1k3TGZxaGRLN2tfakhnTFhCMVJwenA?oc=5)
- [teslarati.com](https://www.teslarati.com/tesla-urges-new-jersey-owners-to-oppose-new-bill-block-robotaxi/)
- [x.com](https://x.com/Teslarati/status/2067006995450720659)
- [teslarati.com](https://www.teslarati.com/boring-company-prufrock-mb2-music-city-loop/)
- [Google News](https://news.google.com/rss/articles/CBMiggFBVV95cUxNdzdpYzMzMGNoTDF3U3ludWpzamlzNFRLMENMVE1CY2ZyWC1kNV9fZXUzQTRkb0ZDS1d1cW14X1FKaEpickNBVmRtV1Axb3pEZkNOcldJb1FaeXBPc2dnS2J2U1Y1OGxlYWNic1FQaThLNVdWOFk1STVYelNLVThURENR0gGWAUFVX3lxTE5XUE1PRG5wUE14MS0xZTRtLXVmV29KZHJCeE9jUTFpWWtEVWRseEtHUHNtakcteVFSOVdrY1JPMXZ2MlhuaWtiRExVbUtwY3YtaUxOcjVQS05iNDBtNElnZ0FCcGhYcjhRWmVUNjRnMWtmbElRWkRwR19IaXk0VEZ2c2lvT25sT3lQRXNQOHlBM0ZwZXR3dw)
- [insideevs.com](https://insideevs.com/news/798906/lucid-cosmos-patent-images/)
- [insideevs.com](https://insideevs.com/news/798968/mobileye-robotaxi-us-launch-2027/)
- [Google News](https://news.google.com/rss/articles/CBMilwFBVV95cUxQN1hIaWppT19ubWNqZlFXN0dJYkJXWG1zd3dacWs0QTFlUDZ0elRzeTJNV0FDa29UdEt1dTNlVjBZa3VEcjRfV3RzUWVoMDNQVlRGUlJpV1NfU2xTT2E1bzcwY1ZqMzVCbXgzZXE2X3NfUEhxSmhzbVdXMmZuWWJsaXVoam9yQnRPeGVIRGlEX01qMnJqQi1v)
- [teslarati.com](https://www.teslarati.com/tesla-cybertruck-driver-pickup-seized-legitimate-concerns-uk/)
- [Google News](https://news.google.com/rss/articles/CBMixgFBVV95cUxOckxBUEZDOTE5XzJ4MFFNWTVBTDBQbVViQTRGR251b2UwRG8wWGxOcDZWVVd0b09xYmVvbUdCaTBFM29lOVZtdlpvRVFGYzFrVWtOUEhMVndrRXJEMmJfVkVoNmMydWxvSnRWNWZkS1lzaHRxbXIweFk4MGVkV2JUQWtRSFA2dmdFRjBMbUd3aXYzc2MzQjY0ZWk0TnBjUEJKeDhWQzRXQVZwUDZrWnNSdnpwQ3lvWGRpOEpEem1xMFo0SmRWWmc)
- [Google News](https://news.google.com/rss/articles/CBMiY0FVX3lxTE56NFJtaGlrbWsyYnFOWGVWcUh2Qk4ya1ZFSzRRYllTNHlsYVJrRmVIaW5MVzl4eTFhTkZDNXYwS3hGSDVDTGZtMTZ1N0tyZVktZEJENzByR2k3Z1EtNWNsVGY5Yw)
- [notateslaapp.com](https://www.notateslaapp.com/news/4302/costco-branded-tesla-semis-spotted-in-arizona)
- [Google News](https://news.google.com/rss/articles/CBMigwFBVV95cUxQb2Rkanh1SHVJTFJNTW1TM0llek5aM1FOX0FkNUp1Z1ZnVGRJU2JhYkdBZjNNRzl5aEZSXy1LaWl6RzhsdExnR2xNVkRVNkpVOExhR08tbVZIMDBqV1NsODh5M21rS09FUE1LUXlydGtYZkltZ0tYa28yT1luX05EcWlGRQ)
- [x.com](https://x.com/Teslarati/status/2067025083575545956)
- [Google News](https://news.google.com/rss/articles/CBMiwAFBVV95cUxPcnc2M2NSVnFia0JQM21tbS1nNW0xaFd5ZUp3MUF4b2hHdGxlVDE2OU1oX3VieXNGOF8zTTRtSWJQamRyLTlxbGRlb2pkOWN0ejNQbWx5cGlqeWlSVTVrMThMWHlZaGs1MTlnSEVUNGwyZ2UxcHY1VnE3V3c1XzB0a1hxeTdpNFhHVnRiOTV4VngwUjl3dXJVUnRUR2dnQUFNUmgtSXprRU45UklhNFdaaWNFMTZKQXc1aWU5LW0xcnQ)
- [Google News](https://news.google.com/rss/articles/CBMipgFBVV95cUxQcC13a2lic1dUMV9ZRmp4Y1Z0YlJHQjBiWWJNNkVvQWljZjJWN2hBcHRzaWstdzB4WkNXZEI2Unhib0QtS0g1cEFacWR0eVM0ZURzSnhrbUZMQWFZVzRmRmN0aS04WEc4UGhjQnVTS2NWWEhnOHB6NWlFZmFmUW9lUWhJa08yMmtxdTdJQlJUT01hMTd3ZjFGX0RhTGRCcmFsdlhjUWV3)
- [x.com](https://x.com/tslaming/status/2067171624877719983)
- [Google News](https://news.google.com/rss/articles/CBMitAFBVV95cUxQWUVDZTE4TWlJWEZzbXJ6bXZlNEZSZHdKMHRhXzdPdXhpUENEbExhYnNmNjhvVkNXMGZON0VnWVRjTWQ5b0wxamhNNXdGdlI5OC1SaGFVZ2pSa2czZGNFU1V3bVJTTUlkbE9kdGFHVFh1b3VHRG5lRG1xNWllc011NC1ab2ZHMVMyWUpyNEI5c0otUWhyWGwwaWo2cXpPM1ZPei1CaU0tc2c4S29YQmFoT0NWT1I)
- [Google News](https://news.google.com/rss/articles/CBMiowFBVV95cUxNWmk4eV9TOGJUbGNNWUZZckF4RnVhMWFMWUc2c0YxVWYtLUxqUHdnZ2xMQk9TMzJvNC1fZzRNdk5rdS1GaHo4dWxGZFc2SmJ4ZmR5WHc0UHc5eVVlbWJ1a0ZZRkRwWEUxWlpVX0l3eW01dURxQ3NvdWZBRTVvZlhyTmd0SFctU25MdHZnNFZlVUZTZnRQRUNZNkljMDB4bXl0Szhv?oc=5)
- [Google News](https://news.google.com/rss/articles/CBMilwFBVV95cUxPcHRjczZnUnBpZ1EwZ01iM1otb1QtbHVneFd0MURqRHp6S19MQXpfdFhQVXM0dE1GWnpsY2J3NjFXd0NaV3F6TWhjMmpmUU55ZnhTSFV3eXJDOUVtd1RUU0J6VE52ZzEzRldIV3VSa19ib0lrSEhQZ2hJRFM1VGhlSTFtZC1tVGQwb2RKRjUwZmI3VFMtZThz?oc=5)
- [Google News](https://news.google.com/rss/articles/CBMidEFVX3lxTFAwNjQta1p6SGJWS1lLZ0hzWUxfVGFSWHp3WlZ4VjZxaml4dHBWTlRXbFd6ZU03SWY2clVlM3FZX2l4YXlET2VNeXQzbThRb2M1U0IxZ3o0M0dLTE4wRTZ1aklNdU1CQnV4TWhaM2dHbWllaHpv?oc=5)
- [insideevs.com](https://insideevs.com/news/799110/rivian-r2-tesla-model-y-efficiency-epa/)
- [Google News](https://news.google.com/rss/articles/CBMirAFBVV95cUxNWXhVSV9IUmJDR3VmOE9iR2gtd09UZG43TU1DUjlnQnpiWk82ZnJaZjFQd2djNGYxRHBmcE1JcGhLcV9yRTlnbDhaYXFxYkw5YWhwT2xYbHN0SGxOVF9HbzZFdDNpbFBhWnlQRTlaR2VkS2xsMk80bl9IX21INWRCemVkcjhqM1J3bUVSdG9PQWtZVW55VEs5blRPUXFxTUk1Q2xweHB4ZWE3all6?oc=5)
- [Google News](https://news.google.com/rss/articles/CBMiggFBVV95cUxPS3lhdnJsbXdaX0x1YVllSkpydTJRSzhibXdTMFZyZ05DZGZUa2Z3Y3JHYk1MVnlmZUtPVThPUnl6RXZxSU9SYmxFblhycmtpUFBjejlhT1V1OTNqTHhmWnJGUS1tcTRibUZfR0V0MnlEVW5kUjVRNUtGVXlWMXkzNlZR?oc=5)
- [Google News](https://news.google.com/rss/articles/CBMihgFBVV95cUxNTnplc0tIeWZxOWZheDdTaVdQUjF6b3pqSWY1RXhYNjJ5UW5tTWh5Q181Q2NGMkNGcjVpdXNwNnM3RVJOWEd3SjlWLUdZZmJPY0ttTzBqMkpQXzd5VHBsQ2dQU3FUSVYtNk1lZHVFZDR2cDJGaUJlUFg3bHFwQUgzVzRCS2lQUQ?oc=5)
- [Google News](https://news.google.com/rss/articles/CBMihgFBVV95cUxQNVF0X2lZUW5yM1BjVFJObWtPVHF5Z2lZVGp3T1hRTWR2SHlEVHRGWF9QaVRER0RXX0lnbWV0ZEdxV0piNE5PTXRFaEhXWldPZjVMc3FVNXBQWHk4MG1CTi1WU0JPaWlYejQyWThxclA1R3Eya0c3NzBTM0EtQnJvUVN0cEU1dw?oc=5)
- [teslarati.com](https://www.teslarati.com/elon-musk-tesla-options-spacex-merger/)
- [Google News](https://news.google.com/rss/articles/CBMi1gFBVV95cUxNWmdES2ZuWUVUelBBMDRiYmtnWWgwQU5qX0tlNG1NYnM5X1pTZmR3bl9zZUFPRjlId3NFSEVFZG5XM28wbkotR25RN2U4RG85Q1NKTml5Q3V2NGlHcDYyUUEzeGdMYkpiQjVFRUZnTDdRR2NHZ1ZveV9uSHNtajRWX21fLTJrUWpVQ0pReE0tbkFfcDQ1TS1SQXA2YUJ5d2hYZ0JlakVPYjl0eUpXcE8wTHZWcmsta1REbzQzRzhUbUJla1BFNHFNTzhxeGJDSFBnWlJSNHVB?oc=5)
- [Google News](https://news.google.com/rss/articles/CBMilwFBVV95cUxPMGJJSFRfUTVsZThoR25tb2x3Sng5cERCMmJKZU1ETmFvd0ltay1JNkUxWkJ1amlSWU1hZHlHNEpNaXFMbVhrbGxDU1ppN2tvY25ZRnNvLTMwZk9MV1RPLXZuNGM4aWlzMEdoSlQtajRNbDlrUDRBb1FGSTZwb045NjVZOWkzdEhqempNUy10UjB6b19BOG5r?oc=5)
- [notateslaapp.com](https://www.notateslaapp.com/news/4313/former-tesla-exec-is-building-the-home-heat-pump-musk-promised)
- [Google News](https://news.google.com/rss/articles/CBMinwFBVV95cUxMb3VGSVZic0tTcWU1Qkg5VlJ1RF9vZXRWeElXeHZqaEtNWkZHdDloY0ZWb0VzeWdHX3pQZEVqTl96ZzMybG51ME1mODUwTy1XdzViNHIxbE11Z1lkdlItRkJRMHdtM2ctUUlQYzd1QVI5TEhMZzM0dUd3U0JiYWMzV1JYd2NoZ2RQdE8xTEpTdnI4aEZJX2JYZ3Rma2NpNnc?oc=5)
- [Google News](https://news.google.com/rss/articles/CBMixgFBVV95cUxOd2NoVzZaX1Ayc3VfTmRaallDZ2VCc1hpR3htYmtsLTJ6S1l4UVVlMW9sOW83VmRyXzRJN3R2N3R3eDhDX2ctNDNQZVFPRzNMUklWbWZDa1NxZ0d4eXhERHB1WC1LU0hWclNBeXRiVnd0SjFjaVd4Rm4teGRKNmhDeXVyU0hGeVdGOHN6Y0JHbVYzNWpqd3cwR0QwaWZiMmNJYXVJY3ctR1BYaEJ5ckhzQVJyUThGMS1SU1JjUWxucExfeXRFbFE?oc=5)
- [notateslaapp.com](https://www.notateslaapp.com/news/4312/exclusive-teslas-android-app-is-getting-live-activities-style-charging-notifications)
- [notateslaapp.com](https://www.notateslaapp.com/news/4314/tesla-starts-adding-free-car-vacuums-to-superchargers)
- [insideevs.com](https://insideevs.com/news/799037/stellantis-uber-robotaxi-wayve-global/)
- [x.com](https://x.com/Teslarati/status/2067673905532191120)
- [x.com](https://x.com/tslaming/status/2067927614057263561)
- [Google News](https://news.google.com/rss/articles/CBMihAFBVV95cUxPaGMxMUpSVWpkUjFIVmo2V0FWdTFkaHA5Um4zYTd5enkxS013bmE5YWx0U0Y1dmROUW9sWE95YVFkSlBMeFhXZGgwN1VkRHhyY2RSME9uQmh2ajIyYUpIUW56aHJOOUg5UFY2UVBVNXJKbFJldWpzWktNS0JFbUlzeTAxRDY?oc=5)
- [evannex.com](https://evannex.com/blogs/news/teslas-most-affordable-cybertruck-yet-is-hitting-driveways-this-week)
- [carbuzz.com](https://carbuzz.com/lucid-cosmos-design-patent-images/)
- [Google News](https://news.google.com/rss/articles/CBMisAFBVV95cUxPRDczWHhjSWlleHNBNHU5ODUyLURnaXppbmR4dzN2UmVKZUg5eV9IU2NGTWJYYnQ0Yl8xdHJjR3JPU2dUWEY4QS1yWG9UUGtXQllHZEplXzhoQ1l6UWFYekhMNDZicEtMYmtPUlA2dFlFa3pqbi1BQ1AzemI0TTJuelpPYm44SUtOb0dCUzlsUHFxdGwtUkR5RW9sSGFKdXpZSkx0LWNEbVdrUGsxSVliUg?oc=5)
- [Google News](https://news.google.com/rss/articles/CBMi5AFBVV95cUxNUGIxV2xFc1lPSTZnSVBPLTYwcmN0eDl4NjJXVEdSSS1PRDU5eWtlTFMzOEoxSWVTS2JlWDZyV09HTm1FYkNsaEk5WXZzZG1MblZTbU05TV9FMjI5ZWViRmw5MGRJUTRmY3J2RUdkMGFvMTVxcTNRRzdReF9IdnlBZTN2UDVFWkd1bmFTakFTZzRqNk9xYk5fZWFtWjl6dm1BUWxVV1M1LXA0dmNtWTA0ZnQzOXRPT2NvYWpXWlRKZWxKX3cyNndCUHU2dVM4LXN3TV9Ld1lhYmdYcjEzckRzTEl2QkHSAeoBQVVfeXFMUEltZ2RoVXMyMXlGRDlWWmxPV3lieTB0MS1QWGFnWF9JXzhrM1NCdDh5dWx0MlFWZ09FYXlVZXY2Y1FseFdTVDVyRUtCLXhlOVVFUl83V19RUnRDdDNxVVcxZkZDdERrZ0ZGdlNIcnd1cWJVT1h3OS13Y1dEbkRoVDluUXhWclNuLWVBdkJpYzBwVDZNa3VvTnJlQ0dLYjlON2dFVzVRWFMzcU1NUThHWjNWbElNb0E4aEZTYnBMTnZId0hRNEtBWXZzdzlIeTVrQ2hWaml6cUotZVBjTjhOOGNuRWNILWdkc1lB?oc=5)
- [notateslaapp.com](https://www.notateslaapp.com/tesla-app-updates/version/4.58.0/release-notes)
- [Google News](https://news.google.com/rss/articles/CBMipAFBVV95cUxPMmRueVFvS2VROFpOUDJxZjBzV3NZWlNpTEZZNW9QMmRHUVRveFB1SXNVZVV2OUFwNHhLaHBOVm81NGZuU3dUYWE5cURUZ1l6dkdXUDYwVmNZRElRS1dYYWNLdGkxVE5NSE5WRi1aVkdwTlpYV0FISmtFVGliNUMycnA2czQzNXFOem1WcEZmS243ZGNOVVlYalItR2ZaZHJKZGE2Sg?oc=5)
- [Google News](https://news.google.com/rss/articles/CBMilwFBVV95cUxPMGF6TWVBNGd1MUEtWXdaQ3pGQmlMYVgtd3FGMHJVUEhwSEdLMEhhRF95ZW5kR202akNiOWVvdm5DUHZ2dGJyMDRtLWVxZ2xWMDA2RXhEMVZiYmtLcVZQdTViX0JqTmpjM2dxc1M2aFpKT21RMm9FMUFJbWFtaXFRdzQ2Zi1PU25ydGtSb09URWVfUWxELTVB?oc=5)
- [Google News](https://news.google.com/rss/articles/CBMiwgFBVV95cUxPekozbFpUQnhTUlFuT1pvN3VrUEhhZFlLZzdZMDllMVpHZ29lZmNpMXlOMHZmLU1xaVp0OF80ZUsyYU5nY3ZYc2JtNHhtRTZkTDgzQWlZZXozN19reGVzV2lkYUVZTTdKNXdySXBPcjJ6QWRmNHd2QUZPYWlyMzhVZ1d2Vk16bGlkZENRMDVRNm53WDhSX3NUbHlGMlQybG01ck1PWFZIZFowSDIyb0puOWFBS3AzbFVidkZSNmFwck1PUQ?oc=5)
- [Google News](https://news.google.com/rss/articles/CBMimgFBVV95cUxPWjFhX0g4VkJ3bVl2dVI3S1R2WmJadUxjTzZpbmR4enE2YndqY2I2dVE1MWxwdk8tVFdzNTlHOFI4RUdfNnFPVXIyaUlzb0VJR3NWRUtSaXZhRlZuSndIR2lVYktMcmQwdURZS0J0dHlWNUJBVi05Rm9UeXYyYk9RMHhoVEQzUnBZNmNSc0RvUzNhSTRIZlZZUE1n0gGuAUFVX3lxTFBTTHhJWDRKaE9BWWZnb1dVVFphRGEtVVhEckFDdjVFQ0ZOTlNHcERwLWVtb0Rkb0hFT1ZkV3NIcnRiQUsySHVxaGJCekFRT2pOaXhpSUJ1UGw3OGNiQ2tjZ3g3UUlpUnBrOVZUd0Rjend5TEtMVk5iZEZpRHdPc2ROWkRoaFZRdjd3SndLS2Z2V3JUQy11Q2c1RThYR0ZsdW5TemhOdTA5d29kaTNIQQ?oc=5)
- [x.com](https://x.com/Teslarati/status/2067759214802416022)
- [x.com](https://x.com/Teslarati/status/2067642249681211868)
- [x.com](https://x.com/tslaming/status/2067941616766369932)
- [Google News](https://news.google.com/rss/articles/CBMimAFBVV95cUxOd1VHWGw1dTBRNk5TMnVyMnBaMDdlMFYwLV9WYzlKdVlReDhnSHNEUzNLYnJfbGhPc2pScWhwMWVCMmZENjhUTzEzMEJaT1JLU2Q2NmhMTDJ3cHZCYmZONmxSS053bTRjWHBLMm96ME5Ya3Q2amJsSWd0ZXotMi12enl2a3R1M3NFcDhudGFIWEtpNUNWdGxCbQ?oc=5)
- [notateslaapp.com](https://www.notateslaapp.com/news/4319/musk-exercises-stock-options-worth-114b-now-owns-more-of-tesla)
- [teslarati.com](https://www.teslarati.com/president-trump-touts-new-air-force-one-musk-technology/)
- [Google News](https://news.google.com/rss/articles/CBMipwFBVV95cUxPVUtqQlJ5eVNyd1lCVzdpQjB3NG9EMGNnb2RuWW5fbUF6TWp5UjE3ZnVpZWc0WjF5MEphWlBKQ3JFQXYyUmk4SUEzU3hlSjF0TVp6LTJDM2s1VzlNeEZuLUFOSmRiQWwweDQ2cF9vT2pxaHFGVDVuYjhwU0xMN1BuMW5RRFZ0R2ZvZ2tiQUdsOG5ERkM2cnVvc0N6enl3dzUzVXRIWUhta9IBowFBVV95cUxOQkJLVXFkNkNWbERHQWJqQ1c5TEh2eUhJVG1kQmxnZHZkVGdBWktsb0xQMHZleVdYZnFlU1VZQ1lvQTNrUEZNdnhDUHQwb0hfZmVfbHctbWVDVUN3b25EVzZLTXE2eW12WEtON3puOTMtaVJQMWZPMm8wT28zOGt5U2hPZHZubWVrUG9uN0dkeVlVVld4V2RiOWxTZFUwdldhSnFR)
- [Google News](https://news.google.com/rss/articles/CBMilwFBVV95cUxNRldxSkJiOGpjU0o5dU16bEVKZHJ0R2pYLU5SSkRjOWlGMUxpWUtVMzQ0VVRNbnJVdmh4NklUemdvMUZfOHV4Ri1WWndWaV81dXdJSy1DRXFDTHNWZW1uY3hiVlRpVlRLZF91Z1dNRXdseEQ2dXptcHZnUFVMVzlic3R5bWlWMWdmUEpzdUQxR2JRWUV1Nnpv)
- [Google News](https://news.google.com/rss/articles/CBMi8wFBVV95cUxNOE8xaHN0NHNrTTRENmh3YVNPTEppMlJoSDdFamx3QjFCNmVQT1JRTHhLdWk5N0hkNE0yNzF2bzJtQkFBdnZRUTd5VFhUdWI2Y25lc3pwdzVCYXhtakhrVEFoaERDOUN3UU5DM2pfdjdkZVpkWXBrN00xRWNVYXk4QU5UX3JXYTB2aGFLdDBtdkE0Qk9zSVJmVk8yRjhkLW5DcnhlSTNZaEFTV1VSOGN1X1ctTWFxbmkyTkVVTFpBZUxDRm93TjZ4LW05X2FFdC1qRzFmNGdyOW5URXJ0aGhEY2gwSjRLTUN1WFA4T3VldlVMSVk)
- [insideevs.com](https://insideevs.com/news/799342/tesla-model-y-lfp-degradation/)
- [Google News](https://news.google.com/rss/articles/CBMimgFBVV95cUxNamttNTNENWlJLVdNMkVUdlRzSWUxOVNWUzJZUnFyUmphc2dDeFUyZ0I4Y19iVFN4Sm1YWVQyR1hONGF6VGhMQkl2VTdXbUtuLUxZT2NDU0c4aThjREZkeFZmaG9mOVIycXFUSGN3ZFNKWWotMVJRcmlOalJiWk1xM2RJeF9HUEZlV0V0bzBuMzNzWjFUZnlfb0l3)
- [cleantechnica.com](https://cleantechnica.com/2026/06/19/despite-all-the-smack-talk-tesla-copied-byd/)
- [Google News](https://news.google.com/rss/articles/CBMiogFBVV95cUxOVl9CeUx4cE0yelAxUmo5U1pheVhJWmRaZFFpYVhRTV8zUkZLM1IyaEV1Y3V1WE1hNzVhT3JXbjhEbDJYVnZlbkxUU3l6ZXVhTk5mTzQ4dnU5bW9nY0ZOYTFaTS01MHVHa1BZd21TNTdsU0xzSWc3ZE5iMXBxSExvNzNDRnBEYlFNcW4xS09uMTFYblJlN284TTk0NmZLZzl4NFE)
- [notateslaapp.com](https://www.notateslaapp.com/news/4325/tesla-spotted-testing-cybercab-front-bumper-blind-spot)
- [teslarati.com](https://www.teslarati.com/tesla-gives-biggest-signal-yet-that-cybercab-launch-imminent/)
- [Google News](https://news.google.com/rss/articles/CBMidEFVX3lxTFB6TlhxVm42bWZkcFBlb0h3WHVYckE5STJudllWa1BrTkdKS2gtbTRBamdETnhpTjNhOUFCTjZ5T1M1eFctVnhLLWoyVVhJa2tSeVhFS01lUnk0VVBqa2RhcFVPQzkwc3pqT25KRnB5VXdFZ2Nu)
- [Google News](https://news.google.com/rss/articles/CBMiwAFBVV95cUxObVBIdU5RSDltbVFYeGxObnEyLTlEd0xiU2dLRFpuQkNJNTlORWU1QVhNWUR6a3h1Uk9TWFhKZnVPLXhyTXdBYk5QdllvZFYwS2g0UHJuTU9feTJuT052SFh5eDVjRTVlQ2JhYW1wNU04V0cyb3BvYmtnYy1PSW1zWTNpZk53cnBHby1jRnV0dVM2dVltVXNyTjF1ZmtMVlRVbmRSVW5sc193eEo5Q2FFVWllVm8xYlVscVNQbldfSXg)
- [x.com](https://x.com/Teslarati/status/2068301160876818498)
- [x.com](https://x.com/tslaming/status/2068353255646933265)
- [Google News](https://news.google.com/rss/articles/CBMihgFBVV95cUxPMGNqNVZIcGEyYklXYTZXcHNWTDVUTFY0Z25WX1ZGVnZJdTNJM3hYYXhzOWkzM0F3OGJkM2ZjTVdZMm5KVVRObFE2M0pMYUVYRUhXSVpBWWlyeTAxbllkOEprYUxZSFo2dW1FOVdOOXRMZXRPY0tvcWJnZEVET1BoVjdhdk9odw)
- [Google News](https://news.google.com/rss/articles/CBMitgFBVV95cUxQMjVWZnlYb3B4X3U4X1dRMkllS3NWRnhNUjNMOGp6T1gyS3dnYWYyYnFEZTEzNHRiaTI3dndMdlpFdlhfcDJYblNZeGc1R3BKMHNIUGhaRDhSemhmZV9ubFdSdmlIS0RCcmtYbEMxdFdfLTYzREp3S0dVY3hRRTJldWp3Tk1iWUpyQl8tVVlWQkE2RGRkNXBianYxNnhJeUZSTUhfRDJLbEpJYzRIbHVEaTQ4UUM5UQ)
- [x.com](https://x.com/Teslarati/status/2068408726420078599)
- [x.com](https://x.com/Teslarati/status/2068349876371362151)
- [x.com](https://x.com/tslaming/status/2068599425711419891)
- [x.com](https://x.com/Tesla/status/2068519225623466074)
- [x.com](https://x.com/Tesla/status/2068502229993299985)