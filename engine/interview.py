"""Guest-interview pipeline for The Age of AI (July 2026).

The Age of AI is the network's AI-hosted interview show: Nerra (the resident
AI host) sets up and conducts interviews with real people. This module owns
the guest-relationship side — a YAML "CRM" of guest records that move through
explicit stages — and compiles a consented, answered interview into a
standard topic-queue packet that the narrative-mode pipeline turns into an
episode.

Two hard rules live here, not in prompts, so they cannot be drifted away:

* ``compile_packet`` refuses a guest without ``consent_to_publish: true``.
* ``voice_mode: ai_voiced`` (guest answers performed by a synthetic voice)
  additionally requires ``consent_ai_voice: true``; anything else compiles
  in ``quoted`` mode where Nerra narrates and attributes the guest's words.

Guest words are treated as verbatim source material end-to-end: this module
never rewrites an answer, and the packet brief instructs the downstream
prompts to keep them verbatim too.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

GUEST_STAGES = (
    "prospect",
    "invited",
    "accepted",
    "questions_sent",
    "answers_received",
    "compiled",
    "published",
    "declined",
)

VOICE_MODES = ("quoted", "ai_voiced")

# What the operator should do next for a guest in each stage (CLI `list`).
NEXT_ACTION = {
    "prospect": "run `invite <id>` and send the draft from your own inbox",
    "invited": "waiting on reply — set stage to accepted/declined when it lands",
    "accepted": "run `questions <id>` and send the question set",
    "questions_sent": "waiting on answers — run `ingest <id> --answers <file>` when they arrive",
    "answers_received": "confirm consent flags in the record, then run `compile <id>`",
    "compiled": "packet queued — dispatch `run_show.py age_of_ai` when ready",
    "published": "done — thank the guest and share the episode link",
    "declined": "no further action",
}


# ---------------------------------------------------------------------------
# Queue I/O
# ---------------------------------------------------------------------------

def load_guest_queue(path: Path) -> Dict[str, Any]:
    """Load the guest queue YAML. Missing file → empty structure."""
    if not path.exists():
        logger.warning("Guest queue file not found: %s", path)
        return {"guests": []}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or not isinstance(data.get("guests"), list):
        logger.error("Guest queue %s missing top-level `guests:` list", path)
        return {"guests": []}
    return data


def save_guest_queue(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(
            data,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=10000,  # don't line-wrap bios/answers
        ),
        encoding="utf-8",
    )


def get_guest(data: Dict[str, Any], guest_id: str) -> Optional[Dict[str, Any]]:
    for g in data.get("guests", []):
        if isinstance(g, dict) and g.get("id") == guest_id:
            return g
    return None


def set_stage(guest: Dict[str, Any], stage: str) -> None:
    if stage not in GUEST_STAGES:
        raise ValueError(f"Unknown guest stage {stage!r} (valid: {GUEST_STAGES})")
    guest["stage"] = stage


# ---------------------------------------------------------------------------
# Outreach drafting (LLM with deterministic fallback)
# ---------------------------------------------------------------------------

_INVITE_TEMPLATE = """Subject: An unusual podcast invitation — an AI would like to interview you

Hi {name},

I'm writing on behalf of The Age of AI, a podcast on the Nerra Network with a
premise we state up front: the host, Nerra, is an AI. The guests are real
people — and the whole point of the show is what real people are actually
living through as AI arrives in their work and lives.

We'd love to interview you about {angle}.

How it works, honestly and completely:
- You receive a written set of questions tailored to you. Answer the ones you
  like, skip the ones you don't, in your own words, on your own time.
- Your answers are used VERBATIM. Nothing is rewritten or invented.
- You choose how your words are presented: quoted by the host, or performed
  by a clearly-disclosed synthetic voice — only with your explicit consent.
- You see nothing published without your consent, and every episode
  discloses that the host is an AI.

If you're curious, just reply to this email and we'll send the questions.

Thanks for considering it,
{sender_name}
Producer, The Age of AI — Nerra Network
"""

_FALLBACK_QUESTIONS = [
    "Before AI entered the picture, what did a good day in your work look like?",
    "When did you first notice AI actually changing your field — not the headlines, your own week?",
    "What's one thing AI already does in your world that genuinely surprised you?",
    "What's one thing everyone assumes AI can do in your field that it really can't yet?",
    "What has it changed about how newcomers learn your craft?",
    "What do you refuse to hand over to automation, and why?",
    "Has AI changed how you're valued — by clients, employers, or yourself?",
    "What would you tell someone entering your field in the next two years?",
    "What's your honest best guess about your field five years out?",
    "And what would have to happen for that guess to be completely wrong?",
]


def _grok_available() -> bool:
    import os
    return bool(os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY"))


def _grok_text(prompt: str, *, temperature: float = 0.6, max_tokens: int = 1600) -> str:
    import sys
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from digests.xai_grok import grok_generate_text
    text, _meta = grok_generate_text(
        prompt=prompt, temperature=temperature, max_tokens=max_tokens,
    )
    return (text or "").strip()


def build_invite_email(guest: Dict[str, Any], *, sender_name: str = "Patrick",
                       use_llm: bool = True) -> str:
    """Draft a personalized invitation. Deterministic template when no LLM
    key is available (or drafting fails) so the operator is never blocked."""
    fallback = _INVITE_TEMPLATE.format(
        name=guest.get("name", "there"),
        angle=guest.get("angle") or "your experience of the AI transition",
        sender_name=sender_name,
    )
    if not (use_llm and _grok_available()):
        return fallback
    try:
        prompt = (
            "Draft a short, warm, honest podcast invitation email (subject "
            "line + body, under 250 words). The show is 'The Age of AI' on "
            "the Nerra Network; its premise is that the HOST is an AI named "
            "Nerra and the guests are real people. The email MUST state that "
            "plainly, explain the written-Q&A format, promise verbatim use "
            "of their words, and explain the two voicing options (quoted by "
            "the host, or a disclosed synthetic voice only with explicit "
            "consent). No hype, no flattery padding.\n\n"
            f"Guest: {guest.get('name')}\n"
            f"Who they are: {guest.get('bio', '')}\n"
            f"Interview angle: {guest.get('angle', '')}\n"
            f"Why this guest: {guest.get('why_this_guest', '')}\n"
            f"Sign as: {sender_name}, Producer, The Age of AI — Nerra Network"
        )
        text = _grok_text(prompt)
        return text or fallback
    except Exception as exc:  # noqa: BLE001 — drafting must never block
        logger.warning("Invite drafting via Grok failed (%s) — using template", exc)
        return fallback


def build_question_set(guest: Dict[str, Any], *, n: int = 10,
                       use_llm: bool = True) -> List[str]:
    """Draft a tailored question set. Falls back to the generic bank."""
    if use_llm and _grok_available():
        try:
            prompt = (
                f"Write exactly {n} interview questions for a written podcast "
                "interview. One question per line, no numbering, no preamble. "
                "The interviewer is an AI (Nerra) interviewing a real person "
                "about living through the AI transition — the questions "
                "should be specific to THIS guest, concrete over abstract, "
                "curious rather than leading, and answerable in writing. "
                "Include at least one question only an AI interviewer could "
                "credibly ask (about the guest's relationship to systems "
                "like the interviewer itself).\n\n"
                f"Guest: {guest.get('name')}\n"
                f"Who they are: {guest.get('bio', '')}\n"
                f"Interview angle: {guest.get('angle', '')}"
            )
            text = _grok_text(prompt, temperature=0.7)
            lines = [
                re.sub(r"^\s*(?:\d+[\.\)]|[-*•])\s*", "", ln).strip()
                for ln in text.splitlines()
            ]
            questions = [ln for ln in lines if ln.endswith("?")]
            if len(questions) >= max(5, n // 2):
                return questions[:n]
            logger.warning(
                "Question drafting returned %d usable questions — using the "
                "fallback bank", len(questions),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Question drafting via Grok failed (%s) — using bank", exc)
    return list(_FALLBACK_QUESTIONS[:n])


# ---------------------------------------------------------------------------
# Answer ingestion
# ---------------------------------------------------------------------------

def parse_answers_markdown(text: str) -> List[Dict[str, str]]:
    """Parse a ``Q:`` / ``A:`` markdown transcript into ``[{q, a}, …]``.

    Format (forgiving on whitespace/markdown emphasis):

        Q: How did you get started?
        A: I fell into it sideways...
        (blank lines and multi-paragraph answers are fine)

    Everything after an ``A:`` line up to the next ``Q:`` line belongs to
    that answer, so guests can write long multi-paragraph answers.
    """
    pairs: List[Dict[str, str]] = []
    current_q: Optional[str] = None
    answer_lines: List[str] = []
    q_re = re.compile(r"^\s*(?:\*\*)?Q(?:\d+)?[:.\)](?:\*\*)?\s*(.*)$", re.IGNORECASE)
    a_re = re.compile(r"^\s*(?:\*\*)?A(?:\d+)?[:.\)](?:\*\*)?\s*(.*)$", re.IGNORECASE)

    def _flush() -> None:
        nonlocal current_q, answer_lines
        if current_q is not None:
            answer = "\n".join(answer_lines).strip()
            if answer:
                pairs.append({"q": current_q, "a": answer})
        current_q, answer_lines = None, []

    in_answer = False
    for line in text.splitlines():
        qm = q_re.match(line)
        am = a_re.match(line)
        if qm:
            _flush()
            current_q = qm.group(1).strip()
            in_answer = False
        elif am and current_q is not None:
            in_answer = True
            if am.group(1).strip():
                answer_lines.append(am.group(1).strip())
        elif in_answer:
            answer_lines.append(line.rstrip())
    _flush()
    return pairs


def ingest_answers(guest: Dict[str, Any], answers_text: str,
                   *, today: Optional[str] = None) -> int:
    """Store parsed verbatim answers on the guest record. Returns pair count."""
    pairs = parse_answers_markdown(answers_text)
    if not pairs:
        raise ValueError(
            "No Q:/A: pairs found — answers must use the 'Q: …' / 'A: …' "
            "markdown format (see docs/age_of_ai_plan.md)."
        )
    guest["answers"] = pairs
    guest["answers_date"] = today or _dt.date.today().isoformat()
    set_stage(guest, "answers_received")
    return len(pairs)


# ---------------------------------------------------------------------------
# Packet compilation (the consent gate)
# ---------------------------------------------------------------------------

def resolve_voice_mode(guest: Dict[str, Any]) -> str:
    """The effective voicing mode after consent gating.

    ``ai_voiced`` is honoured only with ``consent_ai_voice: true``; every
    other combination degrades safely to ``quoted``.
    """
    requested = str(guest.get("voice_mode", "quoted") or "quoted").lower()
    if requested not in VOICE_MODES:
        logger.warning("Unknown voice_mode %r — using 'quoted'", requested)
        return "quoted"
    if requested == "ai_voiced" and guest.get("consent_ai_voice") is not True:
        logger.warning(
            "Guest %s requested ai_voiced without consent_ai_voice: true — "
            "compiling in quoted mode", guest.get("id"),
        )
        return "quoted"
    return requested


def compile_packet(guest: Dict[str, Any], *, today: Optional[str] = None) -> Dict[str, Any]:
    """Build a topic-queue packet from a consented, answered guest record.

    Raises ``ValueError`` on any missing precondition — the caller (CLI)
    surfaces the message to the operator. Never mutates the guest record.
    """
    gid = guest.get("id") or ""
    if not gid:
        raise ValueError("Guest record has no id")
    if guest.get("stage") not in ("answers_received", "compiled"):
        raise ValueError(
            f"Guest {gid!r} is at stage {guest.get('stage')!r} — compile "
            "requires answers_received (ingest their answers first)."
        )
    if guest.get("consent_to_publish") is not True:
        raise ValueError(
            f"Guest {gid!r} has not consented to publish "
            "(set consent_to_publish: true in the guest record only after "
            "the guest has explicitly agreed)."
        )
    answers = guest.get("answers") or []
    if not answers:
        raise ValueError(f"Guest {gid!r} has no recorded answers")

    voice_mode = resolve_voice_mode(guest)
    name = guest.get("name", gid)
    angle = guest.get("angle") or "living through the AI transition"

    qa_lines: List[str] = []
    for i, pair in enumerate(answers, 1):
        qa_lines.append(f"Q{i}: {pair.get('q', '').strip()}")
        qa_lines.append(f"A{i} (VERBATIM — {name}'s own words): {pair.get('a', '').strip()}")
        qa_lines.append("")

    brief = "\n".join([
        f"GUEST: {name}",
        f"WHO THEY ARE: {guest.get('bio', '').strip()}",
        f"INTERVIEW ANGLE: {angle}",
        f"NAME PRONUNCIATION HINT: {guest.get('name_pronunciation', '') or '(standard)'}",
        f"VOICE MODE: {voice_mode}",
        "",
        "FIDELITY RULES (binding on every downstream stage):",
        "- The answers below are the guest's own written words. Use them",
        "  VERBATIM in the episode — light spoken-flow edits only (dropping",
        "  fillers/false starts). Never paraphrase into new claims, never",
        "  merge answers into statements the guest didn't make, never invent",
        "  a single word for the guest.",
        "- You may SELECT and ORDER which answers to feature; selection is",
        "  editing, rewriting is fabrication.",
        "",
        "INTERVIEW TRANSCRIPT (written Q&A, verbatim):",
        "",
        *qa_lines,
    ]).strip()

    packet: Dict[str, Any] = {
        "id": f"interview-{gid}",
        "title": f"{name} on {angle}",
        "category": "interview",
        "brief": brief,
        "guest_id": gid,
        "voice_mode": voice_mode,
        "produced": False,
        "episode_number": None,
        "produced_date": None,
    }
    guest_voice = str(guest.get("guest_voice_id", "") or "").strip()
    if voice_mode == "ai_voiced" and guest_voice:
        packet["guest_voice_id"] = guest_voice
    return packet


def append_packet_to_topic_queue(queue_path: Path, packet: Dict[str, Any]) -> None:
    """Append *packet* to the show's topic queue. Refuses duplicate ids."""
    data: Dict[str, Any] = {"queue": []}
    if queue_path.exists():
        data = yaml.safe_load(queue_path.read_text(encoding="utf-8")) or {"queue": []}
    data.setdefault("queue", [])
    if any(isinstance(e, dict) and e.get("id") == packet["id"] for e in data["queue"]):
        raise ValueError(
            f"Topic queue already has an entry {packet['id']!r} — a guest "
            "compiles once. Remove the stale entry first if this is a redo."
        )
    data["queue"].append(packet)
    queue_path.write_text(
        yaml.safe_dump(
            data,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=10000,
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Episode-side helpers (used by shows/hooks/age_of_ai.py)
# ---------------------------------------------------------------------------

def build_guest_dossier(packet: Dict[str, Any]) -> str:
    """The `{guest_dossier}` prompt block for the upcoming episode."""
    voice_mode = str(packet.get("voice_mode", "quoted"))
    if voice_mode == "ai_voiced":
        voicing = (
            "VOICING: ai_voiced — write the script as NERRA:/GUEST: labeled "
            "dialogue turns. The GUEST turns must be the guest's verbatim "
            "answers (light spoken-flow trims only). The closing MUST "
            "disclose, in Nerra's voice, that the guest's answers are their "
            "own written words performed by a synthetic voice with their "
            "permission."
        )
    else:
        voicing = (
            "VOICING: quoted — single narrator (Nerra). Do NOT use speaker "
            "labels. Nerra narrates the interview and quotes the guest's "
            "written answers directly with clear attribution (\"I asked… "
            "and they wrote back:\"). Quotes must be verbatim excerpts."
        )
    return "\n".join([
        "UPCOMING INTERVIEW (this episode's material):",
        f"Guest: {packet.get('title', '')}",
        voicing,
    ])


def mark_guest_published(guest_queue_path: Path, guest_id: str,
                         episode_num: int, produced_date: str) -> bool:
    """Advance a guest to ``published`` after their episode ships."""
    data = load_guest_queue(guest_queue_path)
    guest = get_guest(data, guest_id)
    if not guest:
        logger.warning("mark_guest_published: guest %r not found", guest_id)
        return False
    set_stage(guest, "published")
    guest["episode_number"] = episode_num
    guest["published_date"] = produced_date
    save_guest_queue(guest_queue_path, data)
    logger.info("Guest %s marked published (episode %d)", guest_id, episode_num)
    return True
