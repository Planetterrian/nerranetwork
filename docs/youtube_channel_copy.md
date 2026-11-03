# YouTube channel copy — @NerraNetwork, @NerraRU, @NerraFR

**Written Nov 3 2026.** The text a viewer sees on a channel page before any
video: the banner's two lines, the channel description (YouTube Studio →
Customisation → Basic info → Description), and the links. Every sentence a
viewer reads is either `engine.brand`'s own string or is written from it; a
guard (`tests/test_sponsor_ready_2026_10_11.py::TestYouTubeChannelCopy`)
reads this file and the three banner SVGs against the brand module and the
network's banned vocabulary. **Paste from here; never retype.**

Why this file exists: on Nov 3 2026 the live @NerraNetwork banner still
promised the free shows carried no advertising and listed a fourth language
track — the first claim was retired on every free surface on Oct 18, the
track was switched off on Oct 9, and the corrected PNG had been sitting in
the repo since Oct 18 with its upload step never run. The @NerraRU
description named a text-to-speech vendor the network retired in May 2026
and called the channel "finance and language" when 96% of its views are
SpaceX, astronomy and Tesla dubs.

Rules that bind this copy (the guard enforces them):

- no show count — the count is computed on the site and the outro card
  (`generate_html._public_shows`); a typed number ages;
- no language list or language count — a track that switches off ages it;
- no promise that the free shows carry no advertising (sponsorship is
  coming to them; the paid tier's copy lives in `engine.brand`);
- no TTS vendor and no model identifier — the disclosure names the fact
  (an AI voice), never the supplier;
- no dialling: there are no telephone interviews (a guest joins a room in
  the browser).

The banners are rendered from the same strings:
`python scripts/build_youtube_banners.py` writes
`brand-refresh-2026/assets/nerra-youtube-banner{,-ru,-fr}.svg` and exports
`brand-refresh-2026/assets/png/youtube-banner{,-ru,-fr}-2560x1440.png`
(needs `pip install cairosvg`; the site's bundled fonts are used, so a
laptop and a runner draw the same bytes). The operator uploads the PNGs in
YouTube Studio → Customisation → Branding → Banner image.

---

## @NerraNetwork (English)

### Banner (`youtube-banner-2560x1440.png`)

> Feed your curiosity, not your anxiety.
>
> SPACE · AI · MARKETS · WORLD NEWS · SCIENCE  ·  SOURCES NAMED

### Channel description

Feed your curiosity, not your anxiety.

Free news and ideas on space, AI, markets, world news, science and more. Every story is sourced, every claim is checked against its source, and you can read the article or hear the episode it came from.

This is the video channel of Nerra Network, an independent podcast network made in Vancouver, Canada. Every day it carries the full episodes and the Shorts of the network's free shows — SpaceX Daily, Tesla Shorts Time, Fascinating Frontiers, Models & Agents, Omni View, Modern Investing Techniques and the rest — each with its sources named in the description and the full article at nerranetwork.com.

The hosts are AI voices and every episode says so: Patrick Novak's shows are read by an AI voice trained on his own, and Mira, who reads the world desks and interviews guests on The Age of AI, is an AI. How the network is made, how every claim is checked, and how to report an error: nerranetwork.com/ai-disclosure.html

### Links (Studio → Basic info → Links)

- Website — https://nerranetwork.com/
- Every show — https://nerranetwork.com/explore.html
- How the shows are made — https://nerranetwork.com/ai-disclosure.html
- Checked claims, in public — https://nerranetwork.com/claims.html

---

## @NerraRU (Russian)

### Banner (`youtube-banner-ru-2560x1440.png`)

> Питайте любопытство, а не тревогу.
>
> STARSHIP · TESLA · АСТРОНОМИЯ  ·  ИСТОЧНИКИ НАЗВАНЫ  ·  ПО-РУССКИ

### Channel description

Питайте любопытство, а не тревогу.

SpaceX, Tesla и астрономия — по-русски, каждый день. @NerraRU — русскоязычный канал Nerra Network, независимой подкаст-сети из Ванкувера (Канада): русская озвучка SpaceX Daily, Tesla Shorts Time и Fascinating Frontiers — тот же выпуск, тот же день, другой язык — и наши собственные подкасты на русском, «Привет, Русский!» и «Финансы Просто».

Каждая история — из названного источника, каждое утверждение проверено по источнику; статью можно прочитать, а выпуск — послушать на nerranetwork.com/ru/.

Голоса — синтезированные: русскую озвучку читает ИИ-голос, и каждый выпуск об этом говорит. Как делается сеть и как сообщить об ошибке: nerranetwork.com/ai-disclosure.html

### Links

- Nerra Network по-русски — https://nerranetwork.com/ru/
- SpaceX по-русски — https://nerranetwork.com/ru/spacex.html
- Как делаются выпуски — https://nerranetwork.com/ai-disclosure.html

---

## @NerraFR (French)

### Banner (`youtube-banner-fr-2560x1440.png`)

> Nourrissez votre curiosité, pas votre anxiété.
>
> STARSHIP · TESLA · ASTRONOMIE  ·  SOURCES NOMMÉES  ·  EN FRANÇAIS

### Channel description

Nourrissez votre curiosité, pas votre anxiété.

Starship, Tesla et l'astronomie — en français, chaque jour. @NerraFR est la chaîne francophone de Nerra Network, un réseau de podcasts indépendant basé à Vancouver, au Canada : SpaceX Daily, Tesla Shorts Time et Fascinating Frontiers, le même épisode que l'original anglais, traduit et lu en français le jour même.

Chaque histoire vient d'une source nommée, chaque affirmation est vérifiée contre sa source, et l'article complet se lit sur nerranetwork.com/fr/.

Les voix sont synthétiques : la version française est lue par une voix d'IA, et chaque épisode le dit. Comment le réseau est fabriqué, et comment signaler une erreur : nerranetwork.com/ai-disclosure.html

### Links

- Nerra Network en français — https://nerranetwork.com/fr/
- Comment les épisodes sont faits — https://nerranetwork.com/ai-disclosure.html

---

## Operator steps (Studio; no API exists for any of these)

1. @NerraNetwork: upload `brand-refresh-2026/assets/png/youtube-banner-2560x1440.png`; paste the English description and links.
2. @NerraRU and @NerraFR: upload the RU/FR PNGs; paste the descriptions and links; set the channel trailer to the newest Fascinating Frontiers hook Short on that channel (the channels' best-earning surface).
3. The outro card now burns for 3 s (`shows/_defaults.yaml outro_card_duration_seconds`), so an end-screen template (Subscribe element + "Best for viewer" video) applied to the Tesla and SpaceX long-forms has its 5–20 s; read `traffic_sources` END_SCREEN in `api/youtube_stats.json` against the other shows after 14 days.
4. When a line here changes, change it in `engine/brand.py` first (the tagline, `youtube_banner_lines`), rebuild the banners, then update this file — the guard fails CI while they disagree.
