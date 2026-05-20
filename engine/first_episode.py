"""Extra LLM guidance for episode 1 — stronger debut without editing every prompt."""

from __future__ import annotations

_DIGEST_EP1 = """
### FIRST EPISODE (Episode {episode_num}) — DEBUT QUALITY BAR
This is the **first episode** of "{show_name}". Listeners have no prior context.
- Open the digest with a one-sentence welcome: what this show is and who it serves.
- Choose the **strongest** stories in the feed — fewer, clearer beats beat a padded list.
- Define any niche jargon on first use; assume zero prior episodes.
- End with a crisp "what to watch tomorrow" line tied to the show's beat.
- Do NOT reference previous episodes, "as we covered last week", or episode numbers > 1.
"""

_PODCAST_EP1 = """
### FIRST EPISODE (Episode {episode_num}) — DEBUT SCRIPT
This is the **series premiere** for "{show_name}".
- First spoken lines: warm welcome + one-sentence promise of what this show delivers every day.
- Explain WHY this show exists (gap in the listener's day) before diving into news.
- Pick ONE anchor story and give it extra breathing room — this sets the tone for the series.
- Close with an invitation to subscribe / follow the blog and what tomorrow might cover.
- Do NOT say "welcome back" or reference earlier episodes.
"""


def first_episode_digest_appendix(
    episode_num: int,
    show_name: str,
) -> str:
    if episode_num != 1:
        return ""
    return _DIGEST_EP1.format(episode_num=episode_num, show_name=show_name).strip()


def first_episode_podcast_appendix(
    episode_num: int,
    show_name: str,
) -> str:
    if episode_num != 1:
        return ""
    return _PODCAST_EP1.format(episode_num=episode_num, show_name=show_name).strip()
