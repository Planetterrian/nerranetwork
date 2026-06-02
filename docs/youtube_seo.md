# YouTube SEO & growth — what's automated, and how to enable new shows

This is the operator playbook for YouTube discovery. **No paid "SEO service"
is ever needed** — every lever below is something the pipeline or you already
control. (Cold DMs offering to "boost your SEO/subs" are spam; bought
views/subs get a channel **terminated**. Ignore them.)

## What the pipeline does automatically (every YouTube-enabled show)

All of this lives in show-agnostic code, so **any show with
`youtube.enabled: true` gets it — current and future**:

| Lever | Where | Notes |
|---|---|---|
| **Front-loaded titles** | `engine/video_metadata.py:_build_seo_title` | Leads with the keyword-rich hook (`"<hook> \| <Show>"`), not `Show — Ep N:`. Episode number stays out of the title. |
| **Entity hashtags** | `_build…_metadata` → `shorts_hashtags.extract_hashtags` | First 3 render as clickable topic links above the title. Long-form + Shorts. |
| **Per-episode entity tags** | `shorts_hashtags.extract_entity_phrases` | The day's specific entities (e.g. `tesla cybercab`, `fsd`) lead the tag list, ahead of the show's static `youtube.tags`. |
| **Chapters** | `chapters.json` → description timestamps | Boosts retention + shows in search. |
| **Uploaded captions / transcript** | `engine/youtube.py` caption upload | Makes every spoken word searchable — the most underrated SEO asset. |
| **Playlists** | `youtube.podcast_playlist_id` | Per-show; one-time "Set as podcast" in Studio puts them in YouTube Podcasts + YT Music. |
| **Shorts → long-form funnel** | smart segment selector + end-card CTA | Shorts are the cheapest discovery; the end card drives to the full episode. |
| **UTM links, AI disclosure, custom thumbnails** | metadata builders | Attribution + policy compliance + CTR. |

## The levers that actually grow the channel (operator, ranked)

Metadata gets you **found**; these get you **clicked and watched** — which is
what YouTube rewards:

1. **Thumbnails (#1 by far).** CTR is the biggest multiplier. The auto-generated
   thumbnails are functional but generic; a human face / big-text / high-contrast
   thumbnail on your top videos out-performs them 2–5×. Highest ROI, zero cost.
2. **Lean into Shorts.** For AI-narrated/slideshow content, long-form watch-time
   is a hard sell, but Shorts pull subscribers fast. Bump `youtube.shorts_per_episode`
   (2–3) **after** the quota increase — see below.
3. **Consistency + patience.** Daily uploads compound; don't judge week one.
4. **First 5 seconds** drive retention → everything. The Shorts smart-selector
   already targets engaging beats.
5. **"Set as podcast"** each playlist in Studio (one-time, per channel).

## Enabling a NEW show on YouTube (post quota-increase) — checklist

> ⚠️ **Quota gate (landmine #20):** the `@NerraNetwork` channel has a 10k
> units/day YouTube quota; each `videos.insert` = 1,600 units. Today only Tesla
> + MAB are enabled (≈9,600/day at 2 Shorts each). **Do not enable a 3rd
> English show until the quota increase lands** — `youtube_quota_preflight.py`
> and the `test_only_tst_and_mab_enable_youtube` drift guard will flag it.

When the increase is granted, for each show you turn on:

1. **Raise the drift guard.** Update `tests/test_schedule.py::test_only_tst_and_mab_enable_youtube`
   to the new allowed set (or generalise it to "≤ quota-allowed count").
2. **Update the quota math** in `scripts/youtube_quota_preflight.py` headroom and
   the `shorts_per_episode` comments in each show YAML.
3. **In the show's `shows/<slug>.yaml` `youtube:` block:**
   - `enabled: true`, `privacy_status: public`, correct `channel` (`en`/`ru`).
   - `category_id` (27 Education / 28 Sci-Tech / 25 News, etc.).
   - `image_queries:` — curated, disambiguated phrases (landmine #14; the
     `test_every_show_yaml_has_image_queries` guard blocks go-live without them).
   - `podcast_playlist_id:` — create the playlist + ID (see `youtube_playlist_add_brief.md`).
   - `tags:` — 5–10 evergreen show tags (per-episode entity tags are added
     automatically on top).
   - `shorts_start_mode: smart`, `shorts_per_episode: 2` (or 3 if quota allows).
4. **One-time in Studio:** "Set existing playlist as a podcast" (landmine #15;
   no API for this flag).
5. **Verify the first upload:** front-loaded title, hashtags above the title,
   chapters, burned-in captions, custom thumbnail, playlist-add.

Everything in "What the pipeline does automatically" then applies to the new
show with **no further code** — the SEO logic is all show-agnostic.

## Optional future code levers (not yet built)

- LLM-written, keyword-optimised description opener (the `youtube.description_prompt_file`
  hook already exists — drop a template in to use it).
- A short, punchy **thumbnail headline** distinct from the full-sentence hook
  (more readable at small sizes) — design-sensitive, worth an A/B.
- Auto end-screen "next video" targeting the show's most-watched upload.
