# Tesla Shorts Time
**REAL-TIME TSLA price:** $371.70 ▲ $17.60 (5.0%) (Intraday)
> **Tesla delivered four hundred eighty-six thousand five hundred thirty-two vehicles in the third quarter while deploying thirteen point seven gigawatt hours of energy storage.**
---
### Top 12 News Items

1. **Tesla Q3 2026 Production, Deliveries, and Energy Storage Update** — [@Tesla](https://x.com/Tesla)
   Tesla produced four hundred sixty-four thousand three hundred ninety-one vehicles and delivered four hundred eighty-six thousand five hundred thirty-two in the third quarter. Energy storage deployments reached thirteen point seven gigawatt hours. The full company update streams live on X on October twenty-one at four thirty pm CT. The production total came in below the prior year figure of four hundred ninety-seven thousand ninety-nine deliveries. Sequential growth from the second quarter of four hundred eighty thousand one hundred twenty-six deliveries shows continued recovery momentum. Source: [ir.tesla.com](https://ir.tesla.com)

2. **Tesla's E7M7 Numeric Format Explained (Patent US 2026/0299533 A1)** — TSLAming (X)
   Tesla filed patent US 2026/0299533 A1 for an E7M7 fifteen-bit numeric format that uses seven exponent bits and seven mantissa bits. The format preserves full training precision while enabling direct conversion to INT8 hardware through integer monotonicity and operator fusion with an fscale sixty-four instruction. It targets reduced heat and battery drain when running multi-billion-parameter networks on vehicle edge chips. Standard BF16 formats allocate eight bits to exponent range rarely needed by vehicle cameras. The E7M7 approach keeps all seven precision bits intact to avoid train-test mismatch during real-world driving. Peak activation detection happens via native integer comparisons after stripping the sign bit. Source: [x.com](https://x.com/tslaming/status/2106026165378925055)

3. **Tesla might charge you up $25,000 if you use its latest feature** — Electrek
   Tesla introduced Emergency Drive Away that allows drivers to shift into Drive and pull away while still plugged into a Supercharger. The feature can cause up to twenty-five thousand dollars in damage to the Supercharger and requires a mandatory service visit for the charge port. Tesla confirmed the feature works on V2, V3, and V4 stalls but not on home chargers and stated deliberate misuse will invoke additional penalties. The launch followed a shooting incident at a Supercharger site two months earlier. Glycol coolant leakage in the demonstration video requires cleanup during the mandatory service visit. Tesla has not specified who pays for repairs in genuine emergency use cases. Source: [electrek.co](https://electrek.co/2026/10/02/tesla-emergency-drive-away-25000-supercharger-damage-who-pays/)

4. **The Tesla Model 3 Gets A Range Bump And A New Screen In The U.S.** — InsideEVs
   American Model 3 vehicles receive a range increase and a new screen. The update does not include vehicle-to-load functionality that was added in China. Source: [insideevs.com](https://insideevs.com/news/810593/tesla-model-3-us-screen-range-update-2026/)

5. **Tesla to produce over 1,000 Optimus robots a week, but hand troubles keep most in testing** — The Cool Down
   Tesla plans to produce more than one thousand Optimus robots per week. Hand dexterity issues continue to limit most units to testing rather than deployment. Source: [thecooldown.com](https://www.thecooldown.com/green-tech/tesla-optimus-robot-production-challenges/)

6. **Tesla’s UK Registrations Nearly Double in September to 15,875** — eletric-vehicles.com
   Tesla registrations in the UK nearly doubled in September to fifteen thousand eight hundred seventy-five. Source: [eletric-vehicles.com](https://eletric-vehicles.com/tesla/teslas-uk-registrations-nearly-double-in-september-to-15875/)

7. **STIF stock plunges 56.5% in a single session, abandoned by Tesla over Megapack 3** — Ideal Investisseur
   STIF stock fell fifty-six point five percent after Tesla moved away from the supplier for Megapack 3 components. Source: [ideal-investisseur.fr](https://www.ideal-investisseur.fr/en/stock-news/stif-stock-plunges-56-5-in-a-single-session-abandoned-by-tesla-over-megapack-3/26354.html)

8. **Tesla moves forward on Wireless Charging for vehicles** — Teslarati
   Tesla published a new patent for wireless charging that detects foreign objects on the pad under varying temperatures. The filing was submitted in March. Source: [teslarati.com](https://www.teslarati.com/tesla-moves-forward-wireless-charging-vehicles/)

9. **Homeowner plans 2 Powerwalls with 4.2-kW solar, and Reddit calls the array a 'rounding error'** — The Cool Down
   A homeowner outlined plans for two Powerwalls paired with a four point two kilowatt solar array. Online discussion described the solar portion as a rounding error relative to storage capacity. Source: [thecooldown.com](https://www.thecooldown.com/green-home/homeowner-plans-tesla-powerwall-solar-array/)

10. **Rivian Jumps 4% After Delivering 19,248 Vehicles and Reaffirming Full-Year Guidance; Tesla Rises 2%** — 24/7 Wall St.
    Rivian delivered nineteen thousand two hundred forty-eight vehicles and reaffirmed full-year guidance. Tesla shares rose two percent on the same day. Source: [247wallst.com](https://247wallst.com/investing/2026/10/02/rivian-jumps-4-after-delivering-19248-vehicles-and-reaffirming-full-year-guidance-tesla-rises-2/)

11. **Discussing VLA 2.0 vs. FSD on Ludicrous Feed** — CleanTechnica
    A panel on Ludicrous Feed compared an XPENG L03 with VLA 2.0 against a Tesla Model 3 with FSD. The discussion also covered recent EV market developments in Australia. Source: [cleantechnica.com](https://cleantechnica.com/2026/10/02/discussing-vla-2-0-vs-fsd-on-ludicrous-feed/)

12. **Musk Says AI Chip Memory Cuts Won't Hurt Optimus** — Dataconomy
    Elon Musk stated that reductions in AI chip memory specifications will not affect Optimus performance. The changes aim to support higher production volumes. Source: [dataconomy.com](https://dataconomy.com/2026/10/02/musk-says-ai-chip-memory-cuts-wont-hurt-optimus/)
---
### Tesla X Takeover
Tesla X Takeover - What's breaking in the Tesla world today! Here are the most interesting, fresh Tesla developments that have everyone talking.

1. **SpaceX Had Three Falcon Launches Yesterday** — [@Teslarati](https://x.com/Teslarati) (X)
   SpaceX completed three Falcon launches in a single day including the Crew-13 mission to the International Space Station. The launches originated from Cape Canaveral. Source: [x.com](https://x.com/Teslarati/status/2106017019485454475)

2. **Tesla’s newest feature lets you floor it out of a Supercharger while plugged in** — Teslarati
   The Emergency Drive Away feature permits drivers to accelerate away from a Supercharger while the cable remains connected. Tesla noted the action will damage both the vehicle and the charger. Source: [teslarati.com](https://www.teslarati.com/tesla-emergency-drive-away-supercharger/)
---
## Short Spot
---
### Tesla First Principles

Edge AI inference on vehicles faces a fundamental tension between numerical precision and power consumption that standard floating-point formats were never designed to resolve. Conventional BF16 allocates eight bits to exponent range that vehicle cameras rarely require while leaving only seven bits for the mantissa that actually determines driving accuracy. Tesla's E7M7 patent reallocates those bits into seven for scale and seven for precision inside a fifteen-bit word, then exploits integer monotonicity so the processor can locate peak activation values with native integer comparisons instead of floating-point scans.

The conversion step that normally inserts millions of bias additions per frame is collapsed by a single fscale instruction applied once outside the loop. That fused operation frees the main execution units to feed dedicated INT8 multiply-accumulate circuits that occupy far less die area and draw substantially less current than equivalent floating-point hardware. The result is that compressed tensors stay resident in fast on-chip SRAM rather than shuttling repeatedly through slower memory hierarchies.

For Tesla the economic implication is direct: every watt saved on inference extends vehicle range or reduces the size and cost of the battery needed to maintain a given range target. The same efficiency gain also lowers the thermal load that would otherwise require larger heat sinks or more aggressive throttling, both of which add mass and expense. In short, the numeric format choice is not merely an implementation detail but a lever on the vehicle's bill of materials and its real-world operating economics.
---
And that's everything worth knowing about Tesla today from a Canadian perspective.
