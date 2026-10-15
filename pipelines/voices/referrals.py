#!/usr/bin/env python3
"""Guest picks and referrals (Oct 15 2026, Patrick).

Every interview on The Age of AI and Nerra Voices ends with a closing round:
a book, the best advice they were ever given, who inspires them, their answer
to the show's own question, and who Mira should interview next. This job
keeps those answers and acts on the last one.

For every published interview, once:

1. **Picks.** Grok (``grok-latest``) reads the end of the published
   transcript and returns the guest's answers as JSON, stored on the
   episode's record (``episode_records.picks``). They feed the public page
   ``guest-picks.html`` through ``site/data/guest_picks.json``.
2. **Referrals.** Each real person the guest named becomes a row in
   ``guest_referrals``. Anyone already on file as a guest or applicant is
   marked ``known`` and never contacted.

Then, for referrals whose guest's episode is out:

3. **Contact.** Grok with web search looks for an address printed on a
   public page: the person's own, their company's, or the office that handles
   requests for them (a university media office). The address must appear on
   the page it was found on, which this job fetches and checks; anything
   guessed, constructed or unverifiable is not used.
4. **Invite.** Mira emails them, crediting the guest by name, with the
   guest's episode, both show pages and the booking link, copying Patrick
   and Dan. An approved application row (``source=referral``, ``referrer``
   = the guest) means a booking or a reply lands where the Worker and the
   Producer expect it.
5. **Ask.** When no address can be found, or the name is unclear, Mira
   writes once to the guest who named them and asks for an introduction.

Nothing goes out the day a name first appears: the day's report shows
Patrick each message, and it is sent by the next day's run unless he holds
it (status ``held``). An introduction from the guest is sent on the next run.
A guest who answers the request with an address is picked up by the
Producer (pipelines/producer/guest_reply.introductions).

Statuses move on by themselves: a referral whose application books is
``booked``, and one whose episode is out is ``interviewed``.

``--dry-run`` sends no guest mail and writes no referral state beyond the
picks: it emails Patrick a preview of exactly what would go out.
``PRODUCER_MODE=off`` stops all sending, as it does for the Producer.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html as _html
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import requests  # noqa: E402

# get_show from common, never ``import shows``: the repo has a top-level
# ``shows/`` package, and a second copy of the module makes a VoiceShow that
# common's isinstance checks do not recognise.
from common import (  # noqa: E402
    DEFAULT_SHOW, OPERATOR_CC, OPERATOR_EMAIL, ROOT, booking_url, get_show, load_prompt, logger,
    mira_signature_html, parse_json_lenient, render_email, sb_insert, sb_select, sb_update,
    send_email,
)
from pipelines.voices.shows import all_shows  # noqa: E402  (the module common uses)

#: Same rule as the Producer (pipelines/producer/classify.py): never a pinned
#: version for this kind of work.
MODEL = "grok-latest"
MAX_INVITES_PER_RUN = int(os.environ.get("REFERRALS_MAX_INVITES", "6"))
#: A new name is announced to Patrick in one day's report and goes out with
#: the next day's run, so he can stop any of them without being asked first.
NOTICE_HOURS = float(os.environ.get("REFERRALS_NOTICE_HOURS", "20"))
PAGE_DATA = ROOT / "site" / "data" / "guest_picks.json"
CLOSING_MARK = "[Closing session]"
#: People who run the show. A guest naming them is kind, not a lead.
HOUSE_NAMES = {"patrick novak", "dan perra", "mira"}
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+'-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


# ---------------------------------------------------------------------------
# Grok
# ---------------------------------------------------------------------------

def _grok(prompt: str, *, web: bool = False, max_tokens: int = 1800) -> str:
    from digests.xai_grok import grok_generate_text
    text, _meta = grok_generate_text(
        prompt=prompt, model=MODEL, temperature=0.1, max_tokens=max_tokens,
        enable_web_search=web,
        timeout_seconds=float(os.environ.get("NERRA_LLM_TIMEOUT_SECONDS", "240")),
    )
    return (text or "").strip()


def _json(text: str) -> Any:
    try:
        return parse_json_lenient(text)
    except (ValueError, json.JSONDecodeError):
        m = re.search(r"\{.*\}", text or "", re.S)
        if not m:
            raise
        return json.loads(m.group(0))


# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------

_TITLES = re.compile(r"^(?:dr|doctor|prof|professor|mr|mrs|ms|mx|sir)\.?\s+", re.I)


def name_key(name: Optional[str]) -> str:
    """Comparable form of a name (as pipelines/producer/inbox.guest_key):
    titles, post-nominals, punctuation and case removed; empty when there is
    not enough of a name to match safely."""
    text = (name or "").split(",")[0].strip()
    while True:
        stripped = _TITLES.sub("", text)
        if stripped == text:
            break
        text = stripped
    words = [w.strip("'-") for w in re.sub(r"[^\w\s'-]", " ", text.lower()).split()]
    words = [w for w in words if w]
    return " ".join(words) if len(words) >= 2 else ""


def first_name(name: str) -> str:
    text = _TITLES.sub("", (name or "").strip())
    return (text.split() or [""])[0]


# ---------------------------------------------------------------------------
# Picks
# ---------------------------------------------------------------------------

def closing_part(transcript: str, limit: int = 24000) -> str:
    """The end of the interview, where the closing round is. A closing
    session spliced on after the first one is the closing round."""
    text = transcript or ""
    if CLOSING_MARK in text:
        before, after = text.split(CLOSING_MARK, 1)
        return (before[-6000:] + "\n" + CLOSING_MARK + after)[-limit:]
    return text[-max(min(limit, int(len(text) * 0.45)), 8000):]


def _clean(value: Any, limit: int = 400) -> str:
    return " ".join(str(value or "").split())[:limit]


def normalize_picks(raw: Any) -> Dict[str, Any]:
    """Whatever the model returned, in the one shape the page and the
    referrals read. Empty strings and empty objects become null."""
    raw = raw if isinstance(raw, dict) else {}

    def obj(key: str, fields: Tuple[str, ...]) -> Optional[Dict[str, str]]:
        v = raw.get(key)
        if not isinstance(v, dict):
            return None
        out = {f: _clean(v.get(f)) for f in fields}
        return out if out.get(fields[0]) else None

    people = []
    for p in raw.get("interview_next") or []:
        if not isinstance(p, dict) or not _clean(p.get("name")):
            continue
        person = {f: _clean(p.get(f)) for f in ("name", "organization", "role", "why", "note")}
        if person["name"].lower() in HOUSE_NAMES:
            continue
        people.append(person)
    bet = _clean(raw.get("bet"), 600) or None
    return {
        "book": obj("book", ("title", "author", "why")),
        "advice": obj("advice", ("text", "source")),
        "inspiration": obj("inspiration", ("who", "why")),
        "bet": bet,
        "interview_next": people[:6],
        "note": _clean(raw.get("note"), 600),
    }


def extract_picks(transcript: str, guest_name: str, show) -> Dict[str, Any]:
    prompt = load_prompt("guest_picks.txt", show=show, show_name=show.name,
                         guest_name=guest_name, closing_question=show.closing_question,
                         transcript=closing_part(transcript))
    last: Optional[Exception] = None
    for attempt in (prompt, prompt + "\n\nReturn ONLY the JSON object."):
        try:
            return normalize_picks(_json(_grok(attempt, web=True)))
        except Exception as exc:  # noqa: BLE001 — one retry, then give up on this one
            last = exc
    raise RuntimeError(f"picks for {guest_name}: {last}")


def published_interviews() -> List[Dict[str, Any]]:
    """Published interviews, one per episode, each with its application as
    ``app``. When two rows claim the same episode number (a July test
    session of Patrick's is marked published as Age of AI Ep2, which is Dan
    Perra's), the one whose guest the show's own episode list names wins."""
    rows = sb_select("interviews", "status=eq.published&episode_number=not.is.null"
                     "&select=id,application_id,show,episode_number,scheduled_at"
                     "&order=scheduled_at.asc")
    by_episode: Dict[Tuple[str, int], List[Dict[str, Any]]] = {}
    for r in rows:
        if r.get("episode_number"):
            r["show"] = r.get("show") or DEFAULT_SHOW
            by_episode.setdefault((r["show"], int(r["episode_number"])), []).append(r)
    listed: Dict[str, Dict[int, Dict[str, Any]]] = {}
    out = []
    for (slug, number), group in by_episode.items():
        for r in group:
            r["app"] = _application(r["application_id"])
        if len(group) > 1:
            if slug not in listed:
                listed[slug] = _summaries(get_show(slug))
            named = name_key((listed[slug].get(number) or {}).get("guest"))
            match = [r for r in group if named and name_key(r["app"].get("name")) == named]
            group = match or group[-1:]
        out.append(group[0])
    return sorted(out, key=lambda r: r.get("scheduled_at") or "")


def _application(app_id: str) -> Dict[str, Any]:
    rows = sb_select("guest_applications", f"id=eq.{app_id}"
                     "&select=id,name,email,title,organization,publicist_email")
    return rows[0] if rows else {}


def _record(interview_id: str) -> Optional[Dict[str, Any]]:
    rows = sb_select("episode_records", f"interview_id=eq.{interview_id}"
                     "&select=id,picks,picks_at&limit=1")
    return rows[0] if rows else None


def _published_transcript(interview_id: str) -> str:
    rows = sb_select("editorial_packages", f"interview_id=eq.{interview_id}&status=eq.published"
                     "&select=transcript_cleaned&order=created_at.desc&limit=1")
    return (rows[0].get("transcript_cleaned") or "") if rows else ""


def ensure_picks(interview: Dict[str, Any], app: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The interview's picks, extracting them the first time."""
    record = _record(interview["id"])
    if record and record.get("picks"):
        return record["picks"]
    transcript = _published_transcript(interview["id"])
    if not transcript:
        logger.warning("no published transcript for %s", interview["id"])
        return None
    show = get_show(interview.get("show"))
    picks = extract_picks(transcript, app.get("name") or "the guest", show)
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    if record:
        sb_update("episode_records", f"id=eq.{record['id']}", {"picks": picks, "picks_at": now})
    else:
        # The first episodes went out before episode records existed.
        sb_insert("episode_records", {
            "show": show.slug, "interview_id": interview["id"],
            "application_id": interview.get("application_id"),
            "guest_name": app.get("name"), "episode_url": _episode_url(show, interview),
            "picks": picks, "picks_at": now})
    logger.info("picks for %s (%s Ep%s): %s", app.get("name"), show.slug,
                interview.get("episode_number"),
                ", ".join(k for k, v in picks.items() if v and k != "note") or "none")
    return picks


# ---------------------------------------------------------------------------
# Referrals
# ---------------------------------------------------------------------------

def known_person(name: str) -> bool:
    """Already a guest or an applicant: nothing to send."""
    key = name_key(name)
    if not key:
        return False
    last = key.split()[-1]
    rows = sb_select("guest_applications", f"name=ilike.*{quote(last)}*&select=name,status")
    return any(name_key(r.get("name")) == key and r.get("status") != "withdrawn" for r in rows)


_UNSURE = re.compile(r"\b(unclear|misheard|mis-heard|uncertain|unsure|not sure|as heard|"
                     r"hard to (?:make out|hear)|inaudible|could not (?:confirm|identify)|"
                     r"couldn't (?:confirm|identify)|possibly|may be|might be|unverified)\b", re.I)


def unsure(ref: Dict[str, Any]) -> bool:
    """The recording leaves who was meant in doubt: ask the guest, never
    search for a stranger with the same name."""
    return bool(_UNSURE.search(ref.get("note") or ""))


def new_referrals(interview: Dict[str, Any], app: Dict[str, Any],
                  picks: Dict[str, Any], *, dry_run: bool = False) -> List[Dict[str, Any]]:
    """A row per person the guest named, once. In a dry run the rows are
    returned without being written, so the preview shows what a real run
    would send."""
    existing = {name_key(r["name"]) or r["name"].lower() for r in sb_select(
        "guest_referrals", f"recommender_interview_id=eq.{interview['id']}&select=name")}
    added = []
    for person in picks.get("interview_next") or []:
        key = name_key(person["name"]) or person["name"].lower()
        if key in existing or key == name_key(app.get("name")):
            continue
        row = {
            "show": interview.get("show") or DEFAULT_SHOW,
            "recommender_interview_id": interview["id"],
            "recommender_name": app.get("name") or "",
            "name": person["name"],
            "organization": person.get("organization") or None,
            "role": person.get("role") or None,
            "why": person.get("why") or None,
            "note": person.get("note") or None,
            "status": "known" if known_person(person["name"]) else "new",
        }
        row = row if dry_run else (sb_insert("guest_referrals", row) or row)
        existing.add(key)
        added.append(row)
    return added


def _address_on_page(email: str, url: str) -> bool:
    """The address has to be printed on the page it was said to come from."""
    if not url.startswith(("http://", "https://")):
        return False
    try:
        resp = requests.get(url, timeout=20, headers={
            "User-Agent": "Mozilla/5.0 (compatible; nerra-referrals/1.0; +https://nerranetwork.com)"})
    except requests.RequestException:
        return False
    return resp.ok and email.lower() in resp.text.lower()


def find_contact(ref: Dict[str, Any]) -> Dict[str, Any]:
    """``{"email", "via", "source", "route", "topic"}``; ``email`` is empty
    unless it was found printed on a public page and checked there."""
    org = ref.get("organization") or ""
    prompt = load_prompt("referral_contact.txt", show=ref.get("show"),
                         name=ref["name"],
                         organization_part=f" ({org})" if org else "",
                         why=ref.get("why") or "(nothing more)",
                         role=ref.get("role") or "(unknown)")
    try:
        out = _json(_grok(prompt, web=True, max_tokens=900))
    except Exception as exc:  # noqa: BLE001
        logger.warning("contact search for %s failed: %s", ref["name"], exc)
        return {"email": "", "via": "", "source": "", "route": "", "topic": ""}
    out = out if isinstance(out, dict) else {}
    email = _clean(out.get("email"), 200)
    source = _clean(out.get("source_url"), 500)
    found = {"email": "", "via": _clean(out.get("via"), 120), "source": source,
             "route": _clean(out.get("route"), 500), "topic": _clean(out.get("topic"), 300)}
    if (EMAIL_RE.match(email) and str(out.get("confidence")).lower() == "high"
            and _address_on_page(email, source)):
        found["email"] = email
    elif email:
        logger.info("contact for %s not used: %s (confidence %s, source %s)",
                    ref["name"], email, out.get("confidence"), source or "none")
    return found


def _episode_url(show, interview: Dict[str, Any]) -> str:
    return show.post_url(int(interview["episode_number"]))


def _blurbs() -> Dict[str, str]:
    """One line per interview show, the same words the Producer's invites
    use (shows/_producer_policy.yaml, show_blurbs)."""
    import yaml
    try:
        cfg = yaml.safe_load((ROOT / "shows" / "_producer_policy.yaml").read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return dict((cfg or {}).get("show_blurbs") or {})


def network_shows() -> List[Dict[str, str]]:
    blurbs = _blurbs()
    return [{"name": s.name, "url": s.page_url, "blurb": blurbs.get(s.slug, "")}
            for s in all_shows()]


def render_invite(ref: Dict[str, Any], contact: Dict[str, Any], interview: Dict[str, Any]
                  ) -> Tuple[str, str]:
    show = get_show(ref.get("show"))
    recommender = ref.get("recommender_name") or ""
    # referral_invite.j2 is a network template, not a voices_* one: it names
    # every interview show, where a show's own mail names only that show.
    html = render_email(
        "referral_invite.j2", show=show,
        name=ref["name"], first_name=first_name(ref["name"]),
        via=contact.get("via") or "", topic=contact.get("topic") or "",
        recommender_name=recommender, recommender_first=first_name(recommender),
        why=ref.get("why") or "",
        recommender_episode_url=_episode_url(show, interview),
        shows=network_shows(),
        booking_url=booking_url(show),
    )
    subject = f"{recommender} suggested I interview {ref['name'] if contact.get('via') else 'you'} for {show.name}"
    return subject, html


def render_ask(app: Dict[str, Any], interview: Dict[str, Any], refs: List[Dict[str, Any]]
               ) -> Tuple[str, str]:
    show = get_show(interview.get("show"))
    people = [{"name": r["name"], "first_name": first_name(r["name"]),
               "organization": r.get("organization") or ""} for r in refs]
    html = render_email(
        "voices_referral_ask.j2", show=show, first_name=first_name(app.get("name") or ""),
        episode_url=_episode_url(show, interview), referrals=people,
        unclear=any(unsure(r) or not r.get("organization") for r in refs),
    )
    firsts = [p["first_name"] for p in people]
    who = firsts[0] if len(firsts) == 1 else ", ".join(firsts[:-1]) + " and " + firsts[-1]
    return f"Could you introduce me to {who}?", html


def _sending_allowed() -> bool:
    return (os.environ.get("PRODUCER_MODE") or "auto").strip().lower() != "off"


def invite(ref: Dict[str, Any], contact: Dict[str, Any], interview: Dict[str, Any],
           *, dry_run: bool, outbox: List[Dict[str, Any]]) -> None:
    subject, html = render_invite(ref, contact, interview)
    outbox.append({"kind": "invite", "to": contact["email"], "subject": subject, "html": html,
                   "name": ref["name"], "via": contact.get("via") or "",
                   "source": contact.get("source") or ""})
    if dry_run:
        return
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    # Marked before it is sent: a run that dies after the send must never
    # send it again.
    sb_update("guest_referrals", f"id=eq.{ref['id']}", {
        "status": "invited", "invited_at": now, "updated_at": now,
        "contact_email": contact["email"], "contact_via": contact.get("via") or None,
        "contact_source": contact.get("source") or None,
        "contact_route": contact.get("route") or None,
        "attempts": int(ref.get("attempts") or 0) + 1, "error": None,
    })
    send_email(contact["email"], subject, html, cc_operator=True)
    # 'approved', because the invitation carries the booking link: the Cal.com
    # webhook matches a booking only to an approved application (by address,
    # then by name for a booking made from another address), and the
    # Producer answers a reply from an approved guest with what they need.
    via = contact.get("via") or ""
    app = sb_insert("guest_applications", {
        "name": ref["name"], "email": contact["email"],
        # An office that passes requests on is the contact, the way a
        # publicist is on a Producer pitch; the guest books with their own
        # address and the Cal.com webhook matches them by name.
        "publicist_name": via or None, "publicist_email": contact["email"] if via else None,
        "organization": ref.get("organization") or None, "title": ref.get("role") or None,
        "show": ref.get("show") or DEFAULT_SHOW, "source": "referral", "status": "approved",
        "referrer": ref.get("recommender_name") or None,
        "notes": (f"Recommended by {ref.get('recommender_name')} when Mira asked who to interview "
                  f"next: {ref.get('why') or ''}"
                  + (f" Address via {via}." if via else "")
                  + (f" Contact: {contact['source']}." if contact.get("source") else "")).strip(),
    })
    sb_update("guest_referrals", f"id=eq.{ref['id']}", {"application_id": (app or {}).get("id")})


def ask_recommender(interview: Dict[str, Any], app: Dict[str, Any], refs: List[Dict[str, Any]],
                    *, dry_run: bool, outbox: List[Dict[str, Any]]) -> None:
    if not refs or "@" not in (app.get("email") or ""):
        return
    subject, html = render_ask(app, interview, refs)
    outbox.append({"kind": "ask", "to": app["email"], "subject": subject, "html": html,
                   "name": ", ".join(r["name"] for r in refs), "via": "", "source": ""})
    if dry_run:
        return
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    for r in refs:
        sb_update("guest_referrals", f"id=eq.{r['id']}", {
            "status": "asked_recommender", "asked_recommender_at": now, "updated_at": now,
            "contact_route": r.get("contact_route") or None,
            "attempts": int(r.get("attempts") or 0) + 1})
    send_email(app["email"], subject, html, cc_operator=True,
               cc=[str(app.get("publicist_email") or "")])


def refresh_statuses() -> int:
    """Invited, asked or known referrals that have since booked or aired."""
    moved = 0
    for ref in sb_select("guest_referrals",
                         "status=in.(new,invited,asked_recommender,no_contact,known,booked)"
                         "&select=id,name,status,application_id"):
        key = name_key(ref["name"])
        if not key:
            continue
        last = key.split()[-1]
        apps = [a for a in sb_select("guest_applications",
                                     f"name=ilike.*{quote(last)}*&select=id,name")
                if name_key(a.get("name")) == key]
        if not apps:
            continue
        ids = ",".join(a["id"] for a in apps)
        ivs = sb_select("interviews", f"application_id=in.({ids})&select=status")
        status = ("interviewed" if any(i.get("status") == "published" for i in ivs)
                  else "booked" if any(i.get("status") in ("scheduled", "briefed", "editorial_review",
                                                             "guest_review", "approved") for i in ivs)
                  else None)
        if status and status != ref["status"]:
            sb_update("guest_referrals", f"id=eq.{ref['id']}", {
                "status": status, "updated_at": dt.datetime.now(dt.timezone.utc).isoformat()})
            moved += 1
    return moved


# ---------------------------------------------------------------------------
# Page data
# ---------------------------------------------------------------------------

def _summaries(show) -> Dict[int, Dict[str, Any]]:
    try:
        data = json.loads(show.summaries_path.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return {}
    out = {}
    for e in data.get("episodes") or []:
        try:
            out[int(e.get("episode"))] = e
        except (TypeError, ValueError):
            continue
    return out


PUBLIC_REFERRAL_STATUS = {"booked": "booked", "interviewed": "interviewed"}


def export_page_data(path: Path = PAGE_DATA) -> Dict[str, Any]:
    """site/data/guest_picks.json: every published episode's picks and the
    people guests recommended. Invitations are never shown, only whether a
    recommended guest has booked or been interviewed."""
    episodes = []
    by_interview = {}
    for iv in published_interviews():
        record = _record(iv["id"])
        if not record or not record.get("picks"):
            continue
        show = get_show(iv.get("show"))
        app = iv.get("app") or {}
        meta = _summaries(show).get(int(iv["episode_number"]), {})
        item = {"show": show.slug, "show_name": show.name, "episode": int(iv["episode_number"]),
                "guest": app.get("name") or meta.get("guest") or "",
                "url": _episode_url(show, iv), "date": meta.get("date") or "",
                "picks": record["picks"]}
        episodes.append(item)
        by_interview[iv["id"]] = item
    referrals = []
    for ref in sb_select("guest_referrals", "status=neq.skipped&select=name,organization,why,"
                         "status,recommender_interview_id&order=created_at.asc"):
        src = by_interview.get(ref["recommender_interview_id"])
        if not src:
            continue
        referrals.append({"name": ref["name"], "organization": ref.get("organization") or "",
                          "why": ref.get("why") or "", "recommended_by": src["guest"],
                          "show": src["show"], "show_name": src["show_name"],
                          "episode": src["episode"], "episode_url": src["url"],
                          "status": PUBLIC_REFERRAL_STATUS.get(ref["status"], "recommended")})
    episodes.sort(key=lambda e: (e["date"], e["episode"]), reverse=True)
    data = {"updated": dt.date.today().isoformat(), "episodes": episodes, "referrals": referrals}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info("wrote %s (%d episodes, %d recommended guests)", path, len(episodes), len(referrals))
    return data


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _picks_html(found: List[Dict[str, Any]]) -> str:
    """What was read from each new episode, for Patrick to check."""
    rows = []
    for f in found:
        p = f["picks"]
        bits = []
        if p.get("book"):
            b = p["book"]
            bits.append(f"Book: <em>{_html.escape(b['title'])}</em>"
                        + (f" by {_html.escape(b['author'])}" if b.get("author") else "")
                        + (f". {_html.escape(b['why'])}" if b.get("why") else ""))
        if p.get("advice"):
            a = p["advice"]
            bits.append(f"Advice: &ldquo;{_html.escape(a['text'])}&rdquo;"
                        + (f" ({_html.escape(a['source'])})" if a.get("source") else ""))
        if p.get("inspiration"):
            i = p["inspiration"]
            bits.append(f"Inspiration: {_html.escape(i['who'])}"
                        + (f". {_html.escape(i['why'])}" if i.get("why") else ""))
        if p.get("bet"):
            bits.append(f"Closing answer: {_html.escape(p['bet'])}")
        for n in p.get("interview_next") or []:
            bits.append(f"Interview next: <strong>{_html.escape(n['name'])}</strong>"
                        + (f" ({_html.escape(n['organization'])})" if n.get("organization") else "")
                        + (f". {_html.escape(n['why'])}" if n.get("why") else "")
                        + (f" <em>Note: {_html.escape(n['note'])}</em>" if n.get("note") else ""))
        if p.get("note"):
            bits.append(f"<em>Note: {_html.escape(p['note'])}</em>")
        rows.append(f"<li><strong>{_html.escape(f['guest'])}</strong> ({_html.escape(f['label'])})"
                    "<ul>" + "".join(f"<li>{b}</li>" for b in bits or ["nothing found"]) + "</ul></li>")
    return "<ul>" + "".join(rows) + "</ul>"


def _message_html(m: Dict[str, Any]) -> str:
    return (f"<hr><p><strong>{'Invite' if m['kind'] == 'invite' else 'Ask for an introduction'}"
            f"</strong> to {_html.escape(m['to'])}"
            + (f" ({_html.escape(m['via'])})" if m.get("via") else "")
            + (f", address from {_html.escape(m['source'])}" if m.get("source") else "")
            + f"<br>Subject: {_html.escape(m['subject'])}</p>{m['html']}")


def report(outbox: List[Dict[str, Any]], manual: List[Dict[str, Any]], *, dry_run: bool,
           found: Optional[List[Dict[str, Any]]] = None,
           upcoming: Optional[List[Dict[str, Any]]] = None) -> None:
    found = found or []
    upcoming = upcoming or []
    if not outbox and not manual and not found and not upcoming:
        return
    invites = sum(1 for m in outbox if m["kind"] == "invite")
    asks = sum(1 for m in outbox if m["kind"] == "ask")
    if dry_run:
        head = ("Preview: nothing was sent and the page is unchanged. These are the messages "
                "the people guests recommended would get. On a real run each new name is "
                "announced to you first and goes out with the next day's run.")
    else:
        head = f"Sent today: {invites} invitation(s) and {asks} introduction request(s)."
    parts = [f"<p>Hi Patrick,</p><p>{_html.escape(head)}</p>"]
    if found:
        parts.append(f"<p><strong>Read from {len(found)} new episode(s)</strong>"
                     + (" (these go on guest-picks.html; tell me anything to correct)" if dry_run else "")
                     + f":</p>{_picks_html(found)}")
    parts.extend(_message_html(m) for m in outbox)
    if upcoming:
        parts.append(f"<hr><p><strong>Going out with tomorrow's run ({len(upcoming)})</strong>. "
                     "To stop one, ask Claude to hold it, or set its status to held in "
                     "guest_referrals.</p>")
        parts.extend(_message_html(m) for m in upcoming)
    if manual:
        parts.append("<hr><p><strong>No address and no one to ask</strong>; these need you:</p><ul>"
                     + "".join(f"<li>{_html.escape(r['name'])} (recommended by "
                               f"{_html.escape(r.get('recommender_name') or '')})"
                               + (f": {_html.escape(r['contact_route'])}" if r.get("contact_route") else "")
                               + "</li>" for r in manual) + "</ul>")
    parts.append(mira_signature_html())
    tail = f", {len(upcoming)} going out tomorrow" if upcoming else ""
    subject = (f"{'Preview: ' if dry_run else ''}Guest picks and referrals: "
               f"{invites} invited, {asks} introductions asked{tail}")
    send_email(OPERATOR_EMAIL, subject, "".join(parts), cc_operator=False,
               cc=list(OPERATOR_CC), cc_guest_team=False)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def _contact_on_file(ref: Dict[str, Any]) -> Dict[str, Any]:
    """An address someone put on the row (Patrick, or a guest's introduction
    picked up by the Producer): used as it is."""
    return {"email": ref["contact_email"], "via": ref.get("contact_via") or "",
            "source": ref.get("contact_source") or "", "route": ref.get("contact_route") or "",
            "topic": ref.get("topic") or ""}


def _due(ref: Dict[str, Any], now: dt.datetime) -> bool:
    """Announced to Patrick at least a day ago, or introduced by the guest
    (who is waiting for the invitation to go)."""
    if (ref.get("contact_source") or "").startswith("introduced by"):
        return True
    try:
        created = dt.datetime.fromisoformat(str(ref.get("created_at")).replace("Z", "+00:00"))
    except ValueError:
        return False
    return now - created >= dt.timedelta(hours=NOTICE_HOURS)


def _look_up(ref: Dict[str, Any], *, dry_run: bool) -> Dict[str, Any]:
    """The referral's contact: on file, or searched for once and kept."""
    if ref.get("contact_email"):
        return _contact_on_file(ref)
    if ref.get("searched_at") or unsure(ref):
        return {"email": "", "route": ref.get("contact_route") or ""}
    contact = find_contact(ref)
    if not dry_run and ref.get("id"):
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        sb_update("guest_referrals", f"id=eq.{ref['id']}", {
            "searched_at": now, "updated_at": now,
            "contact_email": contact.get("email") or None,
            "contact_via": contact.get("via") or None,
            "contact_source": contact.get("source") or None,
            "contact_route": contact.get("route") or None,
            "topic": contact.get("topic") or None})
    return contact


def run(*, dry_run: bool = False, limit: int = MAX_INVITES_PER_RUN) -> Dict[str, int]:
    outbox: List[Dict[str, Any]] = []
    upcoming: List[Dict[str, Any]] = []
    manual: List[Dict[str, Any]] = []
    counts = {"picks": 0, "referrals": 0, "invited": 0, "asked": 0, "moved": 0}
    published = {iv["id"]: iv for iv in published_interviews()}
    fresh: List[Dict[str, Any]] = []
    found: List[Dict[str, Any]] = []
    for iv in published.values():
        app = iv.get("app") or {}
        try:
            had = bool((_record(iv["id"]) or {}).get("picks"))
            picks = ensure_picks(iv, app)
            if picks and not had:
                counts["picks"] += 1
                found.append({"guest": app.get("name") or "", "picks": picks,
                              "label": f"{get_show(iv.get('show')).name} Ep{iv['episode_number']}"})
            if picks:
                added = new_referrals(iv, app, picks, dry_run=dry_run)
                counts["referrals"] += len(added)
                fresh.extend(added)
        except Exception:  # noqa: BLE001 — one episode never stops the rest
            logger.exception("picks failed for %s", app.get("name"))

    if not _sending_allowed():
        logger.info("PRODUCER_MODE=off: no invitations or introductions this run")
        if not dry_run:
            counts["moved"] = refresh_statuses()
        logger.info("referrals: %s", counts)
        return counts

    # New leads, and any lead that has since been given an address (an
    # introduction from the guest, or Patrick's own).
    queue = sb_select("guest_referrals", "or=(status.eq.new,and(status.in.(asked_recommender,"
                      "no_contact),contact_email.not.is.null,invited_at.is.null))"
                      "&order=created_at.asc&select=*")
    if dry_run:
        queue += [r for r in fresh if r["status"] == "new"]
    now = dt.datetime.now(dt.timezone.utc)
    asks: Dict[str, List[Dict[str, Any]]] = {}
    later_asks: Dict[str, List[Dict[str, Any]]] = {}
    for ref in queue:
        iv = published.get(ref["recommender_interview_id"])
        if not iv:
            continue          # their guest's episode is not out yet
        if counts["invited"] >= limit:
            break
        due = dry_run or _due(ref, now)
        try:
            contact = _look_up(ref, dry_run=dry_run)
        except Exception:  # noqa: BLE001
            logger.exception("contact lookup for %s failed", ref["name"])
            continue
        if contact.get("email"):
            if not due:
                subject, html = render_invite(ref, contact, iv)
                upcoming.append({"kind": "invite", "to": contact["email"], "subject": subject,
                                 "html": html, "name": ref["name"], "via": contact.get("via") or "",
                                 "source": contact.get("source") or ""})
                continue
            try:
                invite(ref, contact, iv, dry_run=dry_run, outbox=outbox)
                counts["invited"] += 1
            except Exception as exc:  # noqa: BLE001
                logger.exception("invite to %s failed", ref["name"])
                if not dry_run and ref.get("id"):
                    sb_update("guest_referrals", f"id=eq.{ref['id']}",
                              {"status": "failed", "error": str(exc)[:500]})
            continue
        if ref.get("status") != "new":
            continue
        ref["contact_route"] = contact.get("route") or ref.get("contact_route") or ""
        (asks if due else later_asks).setdefault(ref["recommender_interview_id"], []).append(ref)

    for iv_id, refs in later_asks.items():
        iv = published[iv_id]
        app = iv.get("app") or {}
        if "@" in (app.get("email") or ""):
            subject, html = render_ask(app, iv, refs)
            upcoming.append({"kind": "ask", "to": app["email"], "subject": subject, "html": html,
                             "name": ", ".join(r["name"] for r in refs), "via": "", "source": ""})

    for iv_id, refs in asks.items():
        iv = published[iv_id]
        app = iv.get("app") or {}
        asked_before = sb_select("guest_referrals", f"recommender_interview_id=eq.{iv_id}"
                                 "&asked_recommender_at=not.is.null&select=id&limit=1")
        if asked_before or "@" not in (app.get("email") or ""):
            # One request per guest, ever. Anything after that is Patrick's.
            manual.extend(refs)
            if not dry_run:
                for r in refs:
                    if r.get("id"):
                        sb_update("guest_referrals", f"id=eq.{r['id']}", {
                            "status": "no_contact", "contact_route": r.get("contact_route") or None,
                            "updated_at": dt.datetime.now(dt.timezone.utc).isoformat()})
            continue
        try:
            ask_recommender(iv, app, refs, dry_run=dry_run, outbox=outbox)
            counts["asked"] += len(refs)
        except Exception:  # noqa: BLE001
            logger.exception("asking %s for introductions failed", app.get("name"))

    if not dry_run:
        counts["moved"] = refresh_statuses()
    try:
        report(outbox, manual, dry_run=dry_run, found=found, upcoming=upcoming)
    except Exception:  # noqa: BLE001 — the work is done; the summary is a courtesy
        logger.exception("referral report not sent")
    logger.info("referrals: %s", counts)
    return counts


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="extract picks, send nothing to guests, email Patrick a preview")
    parser.add_argument("--limit", type=int, default=MAX_INVITES_PER_RUN)
    parser.add_argument("--export-only", action="store_true",
                        help="write site/data/guest_picks.json and stop")
    args = parser.parse_args(argv)
    if not args.export_only:
        run(dry_run=args.dry_run, limit=args.limit)
    export_page_data()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
