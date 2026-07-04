#!/usr/bin/env python3
"""Operator CLI for The Age of AI guest pipeline.

Usage:
  python scripts/age_of_ai_guests.py list
  python scripts/age_of_ai_guests.py add jane-doe --name "Jane Doe" \
      --angle "teaching high school as AI does the homework" \
      --bio "..." --contact jane@example.com
  python scripts/age_of_ai_guests.py invite jane-doe
  python scripts/age_of_ai_guests.py stage jane-doe accepted
  python scripts/age_of_ai_guests.py questions jane-doe
  python scripts/age_of_ai_guests.py ingest jane-doe --answers answers.md
  python scripts/age_of_ai_guests.py compile jane-doe

The AI drafts outreach; the OPERATOR sends it from their own inbox and
records replies. Consent flags (consent_to_publish / consent_ai_voice) are
edited by hand in shows/guest_queues/age_of_ai.yaml — they record a human
agreement and are never set by tooling. `compile` enforces them.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.interview import (  # noqa: E402
    NEXT_ACTION,
    append_packet_to_topic_queue,
    build_invite_email,
    build_question_set,
    compile_packet,
    get_guest,
    ingest_answers,
    load_guest_queue,
    save_guest_queue,
    set_stage,
)

GUEST_QUEUE = ROOT / "shows" / "guest_queues" / "age_of_ai.yaml"
TOPIC_QUEUE = ROOT / "shows" / "topic_queues" / "age_of_ai.yaml"
OUTREACH_DIR = ROOT / "digests" / "age_of_ai" / "outreach"


def _require_guest(data: dict, guest_id: str) -> dict:
    guest = get_guest(data, guest_id)
    if not guest:
        known = [g.get("id") for g in data.get("guests", [])]
        sys.exit(f"Unknown guest {guest_id!r}. Known: {known}")
    return guest


def cmd_list(_args: argparse.Namespace) -> int:
    data = load_guest_queue(GUEST_QUEUE)
    guests = data.get("guests", [])
    if not guests:
        print("No guests in the pipeline. Add one with `add <id> --name ...`.")
        return 0
    for g in guests:
        stage = g.get("stage", "?")
        consent = []
        if g.get("consent_to_publish"):
            consent.append("publish")
        if g.get("consent_ai_voice"):
            consent.append("ai-voice")
        print(f"- {g.get('id')} — {g.get('name')} [{stage}]"
              + (f" (consent: {', '.join(consent)})" if consent else ""))
        print(f"    angle: {g.get('angle', '')}")
        print(f"    next:  {NEXT_ACTION.get(stage, '?')}")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    data = load_guest_queue(GUEST_QUEUE)
    if get_guest(data, args.guest_id):
        sys.exit(f"Guest {args.guest_id!r} already exists.")
    data.setdefault("guests", []).append({
        "id": args.guest_id,
        "name": args.name,
        "stage": "prospect",
        "contact": args.contact or "",
        "bio": args.bio or "",
        "angle": args.angle or "",
        "why_this_guest": args.why or "",
        "name_pronunciation": "",
        "consent_to_publish": False,
        "consent_ai_voice": False,
        "voice_mode": "quoted",
        "guest_voice_id": "",
        "questions": [],
        "answers": [],
        "notes": "",
    })
    save_guest_queue(GUEST_QUEUE, data)
    print(f"Added prospect {args.guest_id!r}. Next: `invite {args.guest_id}`.")
    return 0


def cmd_invite(args: argparse.Namespace) -> int:
    data = load_guest_queue(GUEST_QUEUE)
    guest = _require_guest(data, args.guest_id)
    draft = build_invite_email(guest, use_llm=not args.no_llm)
    OUTREACH_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTREACH_DIR / f"{args.guest_id}_invite.md"
    out.write_text(draft, encoding="utf-8")
    if guest.get("stage") == "prospect":
        set_stage(guest, "invited")
        guest["invited_date"] = __import__("datetime").date.today().isoformat()
        save_guest_queue(GUEST_QUEUE, data)
    print(f"Invitation draft written to {out.relative_to(ROOT)}")
    print("Send it from YOUR inbox; update the stage when they reply "
          f"(`stage {args.guest_id} accepted` / `stage {args.guest_id} declined`).")
    return 0


def cmd_questions(args: argparse.Namespace) -> int:
    data = load_guest_queue(GUEST_QUEUE)
    guest = _require_guest(data, args.guest_id)
    questions = build_question_set(guest, n=args.count, use_llm=not args.no_llm)
    guest["questions"] = questions
    if guest.get("stage") in ("prospect", "invited", "accepted"):
        set_stage(guest, "questions_sent")
    save_guest_queue(GUEST_QUEUE, data)
    OUTREACH_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTREACH_DIR / f"{args.guest_id}_questions.md"
    body = [
        f"# Interview questions for {guest.get('name')}",
        "",
        "Answer in writing, in your own words — answer what you like, skip",
        "what you don't. Your answers will be used verbatim.",
        "Reply format: keep each `Q:` line, write your answer under an `A:` line.",
        "",
    ]
    for q in questions:
        body += [f"Q: {q}", "A: ", ""]
    out.write_text("\n".join(body), encoding="utf-8")
    print(f"{len(questions)} questions written to {out.relative_to(ROOT)} "
          "(and stored on the guest record).")
    return 0


def cmd_stage(args: argparse.Namespace) -> int:
    data = load_guest_queue(GUEST_QUEUE)
    guest = _require_guest(data, args.guest_id)
    set_stage(guest, args.stage)
    save_guest_queue(GUEST_QUEUE, data)
    print(f"{args.guest_id} → {args.stage}. Next: {NEXT_ACTION.get(args.stage, '?')}")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    data = load_guest_queue(GUEST_QUEUE)
    guest = _require_guest(data, args.guest_id)
    answers_path = Path(args.answers)
    if not answers_path.exists():
        sys.exit(f"Answers file not found: {answers_path}")
    count = ingest_answers(guest, answers_path.read_text(encoding="utf-8"))
    save_guest_queue(GUEST_QUEUE, data)
    print(f"Ingested {count} verbatim Q&A pairs for {args.guest_id}.")
    print("Next: confirm the consent flags in the guest record by hand, "
          f"then `compile {args.guest_id}`.")
    return 0


def cmd_compile(args: argparse.Namespace) -> int:
    data = load_guest_queue(GUEST_QUEUE)
    guest = _require_guest(data, args.guest_id)
    try:
        packet = compile_packet(guest)
        append_packet_to_topic_queue(TOPIC_QUEUE, packet)
    except ValueError as exc:
        sys.exit(f"Cannot compile: {exc}")
    set_stage(guest, "compiled")
    save_guest_queue(GUEST_QUEUE, data)
    print(f"Packet {packet['id']!r} queued in {TOPIC_QUEUE.relative_to(ROOT)} "
          f"(voice mode: {packet['voice_mode']}).")
    print("Produce the episode via the Run Podcast Show workflow_dispatch "
          "(show: age_of_ai) or `python run_show.py age_of_ai`.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="pipeline overview").set_defaults(func=cmd_list)

    sp = sub.add_parser("add", help="add a prospect")
    sp.add_argument("guest_id")
    sp.add_argument("--name", required=True)
    sp.add_argument("--angle", default="")
    sp.add_argument("--bio", default="")
    sp.add_argument("--contact", default="")
    sp.add_argument("--why", default="")
    sp.set_defaults(func=cmd_add)

    sp = sub.add_parser("invite", help="draft the invitation email")
    sp.add_argument("guest_id")
    sp.add_argument("--no-llm", action="store_true")
    sp.set_defaults(func=cmd_invite)

    sp = sub.add_parser("questions", help="draft the question set")
    sp.add_argument("guest_id")
    sp.add_argument("--count", type=int, default=10)
    sp.add_argument("--no-llm", action="store_true")
    sp.set_defaults(func=cmd_questions)

    sp = sub.add_parser("stage", help="set a guest's stage by hand")
    sp.add_argument("guest_id")
    sp.add_argument("stage")
    sp.set_defaults(func=cmd_stage)

    sp = sub.add_parser("ingest", help="record the guest's written answers")
    sp.add_argument("guest_id")
    sp.add_argument("--answers", required=True, help="path to Q:/A: markdown")
    sp.set_defaults(func=cmd_ingest)

    sp = sub.add_parser("compile", help="consent-checked packet build")
    sp.add_argument("guest_id")
    sp.set_defaults(func=cmd_compile)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
