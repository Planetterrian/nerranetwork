# Market review — Nerra against the 2026 podcast, AI-audio and newsletter market

Operator-directed (Nov 24 2026): deep market research set against the network,
then the fixes that follow. Full write-up with sources (Claude Doc):
https://claude.ai/artifact/AffcWpbwKexB1czjgrpLBg. Register
`market-review-2026-11-24`; guards `tests/test_market_review_2026_11_24.py`.

## Where Nerra stands (Nov 24 nightly)

| Measure | Aug 18 | Nov 24 |
|---|---|---|
| Downloads, 30 d (OP3) | 5,767 | 16,113 |
| SpaceX Daily, 30 d | 2,033 | 5,921 (weekly 1,191 → 1,631) |
| YouTube subscribers (EN/RU/FR) | 498 | 980 (586/307/87); EN channel 5,418 videos |
| Email subscribers | 3 | 5 |
| Paying members / MRR | 0 / $0 | 2 / $13.98 |
| Real site sessions, 28 d | — | 157 (619 bot-like excluded); Google organic 4 |
| Notes-link clicks, 28 d | — | 7 sessions |

Reach tripled; nothing owned or paid moved. Seven shows carry 77% of downloads;
twelve draw under 200 a month each.

## What the market says (sources in the Claude Doc)

- Video and TV now lead podcast use; YouTube is the most-used podcast platform.
- 35–39% of new podcast feeds are AI-made; Inception Point AI (peak ~15,000
  shows) dropped consumer ads and pivoted to B2B services in 2026.
- 47% of listeners would be less likely to keep a favourite show that used AI
  voices; 62% see AI as a credibility threat; 69% approve AI for research.
  Disclosure up front plus checkable sourcing is the defensible position.
- YouTube (Jul 16 2026) withholds monetization from channels with templated or
  repetitive content or AI personas giving finance/health/legal views, judged
  across the last 30 uploads. Spotify added verification badges.
- CPMs $15–40, finance $50–100+; direct sponsors from 5–10k downloads an
  episode, finance earlier. Spotify Partner Program from 1,000 engaged Spotify
  listeners (SpaceX: 629).

## Ranked moves

1. SpaceX Daily as the flagship product (beat, weekly SpaceX email, one
   finance sponsor). Patrick decides.
2. Ask for the email on air. **Shipped here** as an outro-rotation surface.
3. Sunset or pause the shows nobody hears; slow EN YouTube volume (the YouTube
   thread owns the channel work). Patrick decides.
4. Analytics on by default outside the EEA, UK, Switzerland and Quebec, so the
   site can be measured at all. Privacy posture: Patrick decides; not built.
5. Trust promise first in every directory listing; Spotify verification.
6. A music-light SpaceX open (the one Apple review: "hate background music").
   Rehearsal and a listen.
7. Pilot one white-label show for a company (the August plan's C1).
8. SpaceX on Spotify's Partner Program (needs video on Spotify).

## What shipped

`engine.network_promo` gains an `email` surface: one slot in 14 on every
English show, two in 16 on the flagships (both pools coprime with the stride).
It is prompt text for `{closing_block}`, so ⚠️ AUDIO: one listen of the first
episode that airs it before merge (Tesla Nov 26, SpaceX Dec 1 by the rotation).

## Predictions (scored at the Dec 22 readout)

- Email subscribers rise from 5 to at least 25 within four weeks of merge.
- Each airing of the email surface on a flagship is followed by at least one
  signup within 48 h on at least half of the airings.
