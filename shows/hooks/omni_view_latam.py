"""Omni View Central & South America hooks — shared desk behaviour in shows/hooks/_omni_desk.py."""

from shows.hooks import _omni_desk

_SLUG = "omni_view_latam"


def pre_fetch(config, *, episode_num=None, today_str=None) -> dict:
    return _omni_desk.pre_fetch(config, _SLUG)


def post_generate(config, *, digest_text="", episode_num=None) -> None:
    _omni_desk.post_generate(config, _SLUG, digest_text=digest_text, episode_num=episode_num)
