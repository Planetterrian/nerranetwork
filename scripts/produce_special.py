#!/usr/bin/env python3
"""Produce a members-only limited series (see engine/specials.py).

Per episode: research -> dossier + claims ledger -> claims gate (flag mode)
-> blocking lints -> script -> TTS in the host show's voice -> spoken-text
gate -> music -> PRIVATE upload. Then the trailer (public bucket, not yet in
any feed). Nothing reaches a public surface here; scripts/release_special.py
does that after the operator has listened.

    python scripts/produce_special.py --series spacex-tesla-merger            # every unproduced episode + trailer
    python scripts/produce_special.py --series peptides-deep-dives --episode bpc-157
    python scripts/produce_special.py --series spacex-tesla-merger --text-only # research + writing, no audio

Exit status: 0 when every requested episode produced, 1 when any failed
(the others are kept; re-running skips what is already produced).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import specials as S  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    stream=sys.stdout)
logger = logging.getLogger("produce_special")


def _host_config(series: S.Series):
    from engine.config import load_config
    return load_config(str(ROOT / "shows" / f"{series.host_show}.yaml"))


def _r2_env(config) -> Optional[Dict[str, str]]:
    st = config.storage
    env = {k: os.environ.get(getattr(st, attr, default), "")
           for k, attr, default in (("endpoint", "endpoint_env", "R2_ENDPOINT_URL"),
                                    ("access", "access_key_env", "R2_ACCESS_KEY_ID"),
                                    ("secret", "secret_key_env", "R2_SECRET_ACCESS_KEY"))}
    return env if all(env.values()) else None


# ---------------------------------------------------------------------------
# Text stages
# ---------------------------------------------------------------------------

def write_episode_text(series: S.Series, ep: S.Episode, config, catalog: dict,
                       today: dt.date) -> Dict[str, Any]:
    """Research, dossier, claims, script. Writes the episode directory and
    returns the episode's catalog fields. Raises SpecialsError."""
    from engine.claims import extract_claims_block

    out_dir = S.episode_dir(series, ep)
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("[%s] research: %d questions", ep.id, len(ep.questions))
    articles = S.research_episode(ep)
    (out_dir / "sources.json").write_text(
        json.dumps(S.sources_record(articles), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    if len(articles) < series.min_sources:
        raise S.ThinResearch(
            f"{ep.id}: {len(articles)} readable sources fetched, the series requires "
            f"{series.min_sources} — not produced (never written from memory)")

    system = series.rules_text() or None
    prompt = S.dossier_prompt(series, ep, articles, today=today, catalog=catalog)
    raw, meta = S.call_model(prompt, model=series.model,
                             max_tokens=S.DOSSIER_MAX_TOKENS, system_prompt=system)
    dossier, claims = extract_claims_block(raw)
    findings = S.blocking_lint_findings(dossier, series)
    if findings:
        logger.warning("[%s] dossier lint: %s — one regeneration", ep.id, findings)
        raw, meta = S.call_model(
            prompt + "\n\nYOUR PREVIOUS DRAFT WAS REJECTED: " + "; ".join(findings)
            + ". Write the whole dossier again without it.",
            model=series.model, max_tokens=S.DOSSIER_MAX_TOKENS, system_prompt=system)
        dossier, claims = extract_claims_block(raw)
        findings = S.blocking_lint_findings(dossier, series)
        if findings:
            raise S.SpecialsError(f"{ep.id}: dossier still fails: {findings}")

    gate = S.check_claims(dossier, claims, articles)
    dossier = gate.pop("text")
    (out_dir / "dossier.md").write_text(dossier.strip() + "\n", encoding="utf-8")
    (out_dir / "claims.json").write_text(
        json.dumps(gate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info("[%s] dossier: %d words, claims %d verified of %d",
                ep.id, S.word_count(dossier), gate["claims_verified"], gate["claims_total"])

    sprompt = S.script_prompt(series, ep, dossier, today=today,
                              host_name=config.publishing.host_name, show_name=config.name,
                              catalog=catalog)
    script, smeta = S.call_model(sprompt, model=series.model,
                                 max_tokens=S.SCRIPT_MAX_TOKENS, system_prompt=system)
    script = S.clean_script(script)
    findings = S.blocking_lint_findings(script, series)
    if findings:
        logger.warning("[%s] script lint: %s — one regeneration", ep.id, findings)
        script, smeta = S.call_model(
            sprompt + "\n\nYOUR PREVIOUS DRAFT WAS REJECTED: " + "; ".join(findings)
            + ". Write the whole script again without it.",
            model=series.model, max_tokens=S.SCRIPT_MAX_TOKENS, system_prompt=system)
        script = S.clean_script(script)
        findings = S.blocking_lint_findings(script, series)
        if findings:
            raise S.SpecialsError(f"{ep.id}: script still fails: {findings}")
    words = S.word_count(script)
    if words < S.MIN_SCRIPT_WORDS:
        # No expansion retry (length levers are dossier-side): a short
        # script means a thin dossier, and the operator decides.
        (out_dir / "script.short.txt").write_text(script, encoding="utf-8")
        raise S.SpecialsError(f"{ep.id}: script {words} words, under {S.MIN_SCRIPT_WORDS}")
    script = script.rstrip() + "\n\n" + S.AI_DISCLOSURE + "\n"
    (out_dir / "script.txt").write_text(script, encoding="utf-8")
    logger.info("[%s] script: %d words", ep.id, words)
    return {
        "part": ep.part, "title": ep.title, "stance": ep.stance,
        "sources": len(articles), "dossier_words": S.word_count(dossier),
        "script_words": words, "claims_total": gate["claims_total"],
        "claims_verified": gate["claims_verified"],
        "claims_flagged": len(gate["flagged_sentences"]),
        "dossier_model": meta.get("served_model"), "script_model": smeta.get("served_model"),
        "text_date": today.isoformat(),
    }


# ---------------------------------------------------------------------------
# Audio stages
# ---------------------------------------------------------------------------

def _tts_text(script: str, slug: str) -> str:
    from assets.pronunciation import prepare_text_for_tts
    return prepare_text_for_tts(script)


def synthesize_checked(script: str, config, out_dir: Path, prefix: str) -> Path:
    """TTS -> transcript -> spoken-text gate (one re-synthesis) -> raw MP3."""
    from engine.spoken_text_gate import check_transcript_files
    from engine.transcripts import generate_transcript
    from engine.tts import synthesize

    tts_text = _tts_text(script, config.slug)
    (out_dir / f"{prefix}_tts.txt").write_text(tts_text, encoding="utf-8")
    api_key = os.environ.get("GROK_API_KEY") or os.environ.get("XAI_API_KEY") or ""
    raw = out_dir / f"{prefix}_raw.mp3"
    t = config.tts
    for attempt in (1, 2):
        synthesize(tts_text, t.voice_id, raw, api_key=api_key, provider=t.provider,
                   max_chars=t.max_chars, model_id=t.model, stability=t.stability,
                   similarity_boost=t.similarity_boost, style=t.style,
                   language_code=t.language_code, speed=t.speed,
                   apply_text_normalization=t.apply_text_normalization,
                   speech_wrap_open=t.speech_wrap_open, speech_wrap_close=t.speech_wrap_close)
        result = generate_transcript(raw, out_dir, prefix, model_size=t.whisper_model,
                                     language="en", vocabulary=[config.name, *config.keywords])
        if result is None:
            raise S.SpecialsError(f"{prefix}: no transcript — the audio cannot be verified")
        report = check_transcript_files(tts_text, result.json_path, result.txt_path)
        logger.info("[%s] spoken-text gate attempt %d: %s opening=%.2f run=%d",
                    prefix, attempt, "PASS" if report.passed else "FAIL",
                    report.opening_match, report.longest_unmatched_run)
        if report.passed:
            return raw
    raise S.SpecialsError(f"{prefix}: spoken-text gate failed twice")


def mix(raw: Path, config, final: Path) -> Path:
    from engine.audio import mix_with_music, normalize_voice

    a = config.audio
    music = ROOT / a.music_file if a.music_file else None
    if music and music.is_file():
        mix_with_music(raw, music, final,
                       intro_duration=int(a.intro_duration), overlap_duration=int(a.overlap_duration),
                       fade_duration=int(a.fade_duration), outro_duration=int(a.outro_duration),
                       intro_volume=a.intro_volume, overlap_volume=a.overlap_volume,
                       fade_volume=a.fade_volume, outro_volume=a.outro_volume,
                       voice_intro_delay=a.voice_intro_delay, outro_crossfade=a.outro_crossfade,
                       denoise=a.voice_denoise)
    else:
        normalize_voice(raw, final, denoise=a.voice_denoise)
    return final


def upload(path: Path, key: str, config, *, private: bool) -> str:
    from engine.access import private_audio_ref, private_bucket
    from engine.storage import upload_to_r2

    env = _r2_env(config)
    if not env:
        raise S.SpecialsError("R2 credentials are not set — the audio reached nobody")
    bucket = private_bucket() if private else config.storage.bucket
    url = upload_to_r2(path, key, bucket=bucket, endpoint_url=env["endpoint"],
                       access_key=env["access"], secret_key=env["secret"],
                       public_base_url="" if private else config.storage.public_base_url,
                       content_type="audio/mpeg")
    return private_audio_ref(bucket, key) if private else url


def produce_audio(series: S.Series, ep: S.Episode, config) -> Dict[str, Any]:
    from engine.audio import get_audio_duration

    out_dir = S.episode_dir(series, ep)
    script = (out_dir / "script.txt").read_text(encoding="utf-8")
    name = S.audio_filename(series, ep)
    prefix = name[:-4]
    raw = synthesize_checked(script, config, out_dir, prefix)
    final = mix(raw, config, out_dir / name)
    ref = upload(final, f"{S.PRIVATE_PREFIX}/{series.id}/{name}", config, private=True)
    info = {"filename": name, "audio_ref": ref, "bytes": final.stat().st_size,
            "duration_seconds": round(float(get_audio_duration(final) or 0), 1)}
    for p in (raw, final):
        p.unlink(missing_ok=True)  # MP3s never enter git (landmine #1)
    return info


def produce_trailer(series: S.Series, config, today: dt.date) -> Dict[str, Any]:
    from engine.audio import get_audio_duration

    out_dir = S.SPECIALS_DIR / series.id
    out_dir.mkdir(parents=True, exist_ok=True)
    text, meta = S.call_model(
        S.trailer_prompt(series, host_name=config.publishing.host_name, show_name=config.name),
        model=series.model, max_tokens=1500, system_prompt=series.rules_text() or None)
    text = S.clean_script(text)
    findings = S.blocking_lint_findings(text, series)
    if findings:
        raise S.SpecialsError(f"trailer fails: {findings}")
    text = text.rstrip() + "\n\n" + S.AI_DISCLOSURE + "\n"
    (out_dir / "trailer.txt").write_text(text, encoding="utf-8")
    name = f"{series.id}-trailer.mp3"
    raw = synthesize_checked(text, config, out_dir, name[:-4])
    final = mix(raw, config, out_dir / name)
    url = upload(final, f"{S.PUBLIC_TRAILER_PREFIX}/{series.id}/{name}", config, private=False)
    info = {"filename": name, "audio_url": url, "bytes": final.stat().st_size,
            "duration_seconds": round(float(get_audio_duration(final) or 0), 1),
            "words": S.word_count(text), "model": meta.get("served_model"),
            "date": today.isoformat()}
    for p in (raw, final):
        p.unlink(missing_ok=True)
    return info


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--series", required=True)
    ap.add_argument("--episode", action="append", default=[],
                    help="episode id (repeatable); default every unproduced episode")
    ap.add_argument("--force", action="store_true", help="re-produce produced episodes")
    ap.add_argument("--text-only", action="store_true", help="research and writing only")
    ap.add_argument("--audio-only", action="store_true",
                    help="synthesize from the committed script.txt")
    ap.add_argument("--no-trailer", action="store_true")
    args = ap.parse_args(argv)

    series = S.find_series(args.series)
    config = _host_config(series)
    catalog = S.load_catalog()
    entry = S.series_entry(catalog, series)
    if entry.get("status") == "released" and not args.force:
        logger.error("%s is released; re-producing it needs --force", series.id)
        return 1
    today = dt.date.today()
    targets = [series.episode(e) for e in args.episode] if args.episode else series.episodes
    failed: List[str] = []
    for ep in targets:
        row = entry["episodes"].setdefault(ep.id, {})
        if row.get("status") == "produced" and not args.force:
            logger.info("[%s] already produced — skipped", ep.id)
            continue
        try:
            if not args.audio_only:
                row.update(write_episode_text(series, ep, config, catalog, today))
                row["status"] = "written"
                S.save_catalog(catalog)
            if not args.text_only:
                row.update(produce_audio(series, ep, config))
                row["status"] = "produced"
                row["produced_date"] = today.isoformat()
        except S.SpecialsError as exc:
            logger.error("::error::%s", exc)
            row["last_error"] = str(exc)
            failed.append(ep.id)
        S.save_catalog(catalog)

    produced = all(entry["episodes"].get(e.id, {}).get("status") == "produced"
                   for e in series.episodes)
    if produced:
        entry["status"] = "produced"
        if not args.no_trailer and not args.text_only and not entry.get("trailer"):
            try:
                entry["trailer"] = produce_trailer(series, config, today)
            except S.SpecialsError as exc:
                logger.error("::error::trailer: %s", exc)
                failed.append("trailer")
    S.save_catalog(catalog)
    logger.info("%s: %d of %d produced%s", series.id,
                sum(1 for e in series.episodes
                    if entry["episodes"].get(e.id, {}).get("status") == "produced"),
                series.total_parts, f"; failed: {failed}" if failed else "")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
