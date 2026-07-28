"""Apple's **official** podcast analytics, via the Reporter CLI.

What this replaces
------------------
``scripts/fetch_apple_stats.py`` has authenticated with two browser
cookies (``myacinfo`` / ``itctx``) scraped from a logged-in Podcasts
Connect session. They expire in roughly a day, and this repo's own docs
asserted — in three places — that Apple ships no official creator
analytics API at all. That was wrong.

Apple ships **Reporter**, a command-line tool that returns listening
reports against an access token valid for **180 days**. No browser, no
cookies, no scraping. Verified working against this account on 28 July
2026 after the Apple Podcasters Program agreement went Active; before
that, ``Sales.getVendors`` returned nothing and the reports were
unreachable, which is why the earlier investigation concluded it was a
dead end.

Contrary to Apple's own documentation, the listening reports do **not**
require an active subscription — this account has zero and the reports
return data.

Report shapes
-------------
Two schemas, differing by exactly one leading column:

* ``apShowListening`` — per storefront, first column ``Store Front Name``
* ``apShowListeningWorldwide`` — aggregated, no storefront column

Both are tab-separated, one header row, then one row per show **that had
activity that day**. There is also ``apEpisodeListening`` (adds Episode
Identifier / Name / GUID / Type after the show columns).

Two properties of the data that shape everything here
-----------------------------------------------------
1. **Absence is not zero.** A show with no listening simply has no row.
   On 27 July 2026 the worldwide report carried two rows for a network
   of thirty shows. Reporting the other twenty-eight as ``0`` would be
   the exact silent-zero bug fixed in the cookie path a week earlier —
   a dashboard reading "0 plays" when the truth is "not measured".
2. **Empty cells are suppressed, not zero.** Apple leaves a metric blank
   when the count is too low to disclose. In the same file Tesla Shorts
   Time had 38 plays and a *blank* engaged-listener count, while SpaceX
   Daily had 22 plays and 7 engaged listeners. Parsing blank as 0 would
   invent a precise-looking falsehood.

Both cases map to ``None``, never ``0``, and callers must preserve that
distinction all the way to the dashboard.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import logging
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# The endpoint Reporter.jar itself posts to — the value Apple ships in
# the stock Reporter.properties. Speaking it directly means the nightly
# needs neither Java nor Apple's jar, only the access token.
SALES_URL = "https://reportingitc-reporter.apple.com/reportservice/sales/v1"

# Reporter's own protocol version string. Sent verbatim; Apple rejects
# a request that omits it.
_PROTOCOL_VERSION = "2.2"

# Report types. The spellings are Apple's and are case-sensitive.
SHOW_REPORT = "apShowListening"
SHOW_REPORT_WORLDWIDE = "apShowListeningWorldwide"
EPISODE_REPORT = "apEpisodeListening"

# Column headers, verbatim from a real download. Matched case-insensitively
# on a whitespace-normalised key so a cosmetic change by Apple (spacing,
# capitalisation) does not silently drop a metric.
_METRIC_COLUMNS = {
    "total listening hours": "listening_hours",
    "total listeners": "listeners",
    "total engaged listeners": "engaged_listeners",
    "total plays": "plays",
}
_SHOW_ID_COLUMN = "show identifier"
_SHOW_NAME_COLUMN = "show name"
_STOREFRONT_COLUMN = "store front name"


@dataclass
class ShowListening:
    """One show's listening for one day, per storefront.

    Every metric is ``Optional``. ``None`` means Apple did not report a
    number — either suppressed for being too low, or the column was
    absent. It never means zero.
    """

    show_id: str
    show_name: str = ""
    storefront: str = ""
    listening_hours: Optional[float] = None
    listeners: Optional[int] = None
    engaged_listeners: Optional[int] = None
    plays: Optional[int] = None

    def as_dict(self) -> dict:
        out = {"show_id": self.show_id, "show_name": self.show_name}
        if self.storefront:
            out["storefront"] = self.storefront
        for key in ("listening_hours", "listeners", "engaged_listeners", "plays"):
            value = getattr(self, key)
            if value is not None:
                out[key] = value
        return out


# Apple's phrasings for "there is no report for that date". They are
# indistinguishable from real failures by status code alone, and one of
# them is actively misleading — see ``_is_no_data``.
_NO_DATA_MARKERS = (
    "no reports available",
    "no sales",
    "there were no",
    "not available",
    # Apple returns THIS for a valid vendor on a date it has no report
    # for. Verified 28 July 2026: vendor 93825591 with date 20260727
    # downloads fine, and the identical command with 20260725 answers
    # "Invalid vendor number specified. Try again." The vendor is not
    # invalid; it simply did not exist yet on that date, because Apple
    # provisions the reporting vendor when the Podcasters Program
    # agreement goes Active. Treating this as a hard error would make
    # the nightly look broken every time it reached past that boundary.
    "invalid vendor number",
)


def _is_no_data(text: str) -> bool:
    return any(marker in (text or "").lower() for marker in _NO_DATA_MARKERS)


@dataclass
class ReporterResult:
    """Outcome of one report fetch. Never raises; inspect ``error``.

    ``ok`` with empty ``rows`` means Apple has no report for that date —
    a real answer. ``error`` means the fetch itself failed.
    """

    report_type: str
    date: str
    rows: List[ShowListening] = field(default_factory=list)
    error: str = ""
    no_data: bool = False

    @property
    def ok(self) -> bool:
        return not self.error


def _ssl_context():
    """A verifying SSL context that works on a bare macOS Python.

    Python installed from python.org does not populate a CA bundle, so
    ``urllib`` has nothing to verify against and every HTTPS call dies
    with "self signed certificate in certificate chain" — which reads
    like a proxy problem and is really a missing trust store. Apple's
    endpoint is fine; the client is not.

    ``certifi`` ships the bundle and is already present transitively via
    ``requests``. Using it explicitly is what ``requests`` itself does,
    and it makes this work identically on a developer Mac and a CI
    runner.

    Verification is never disabled. This request carries a 180-day
    credential, so an unverified connection is not an acceptable
    shortcut — if no bundle can be found, the system default is used and
    the caller sees the real error.
    """
    import ssl

    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001 — fall back to the system default
        return ssl.create_default_context()


def _norm(header: str) -> str:
    return " ".join(str(header or "").split()).strip().lower()


def _number(raw: str, *, integer: bool) -> Optional[float]:
    """Parse a cell, mapping blank to None rather than 0.

    See the module docstring: Apple blanks a metric it will not
    disclose, and a blank rendered as 0 is a confident wrong answer.
    """
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        value = float(text.replace(",", ""))
    except ValueError:
        logger.debug("Unparseable Reporter cell %r", raw)
        return None
    return int(round(value)) if integer else value


def parse_show_listening(data: bytes) -> List[ShowListening]:
    """Parse a ShowListening report (gzipped or plain) into rows.

    Handles both the per-storefront and worldwide schemas — they differ
    only by the leading ``Store Front Name`` column, and columns are
    resolved by header name rather than position precisely so that
    difference needs no special case.
    """
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)

    reader = csv.reader(io.StringIO(data.decode("utf-8-sig")), delimiter="\t")
    try:
        header = next(reader)
    except StopIteration:
        return []

    index = {_norm(name): i for i, name in enumerate(header)}
    if _SHOW_ID_COLUMN not in index:
        logger.warning("Reporter output has no %r column — headers: %s",
                       _SHOW_ID_COLUMN, header)
        return []

    def cell(row: List[str], key: str) -> str:
        pos = index.get(key)
        return row[pos] if pos is not None and pos < len(row) else ""

    rows: List[ShowListening] = []
    for raw_row in reader:
        show_id = cell(raw_row, _SHOW_ID_COLUMN).strip()
        if not show_id:
            continue
        entry = ShowListening(
            show_id=show_id,
            show_name=cell(raw_row, _SHOW_NAME_COLUMN).strip(),
            storefront=cell(raw_row, _STOREFRONT_COLUMN).strip(),
        )
        for column, attr in _METRIC_COLUMNS.items():
            setattr(entry, attr,
                    _number(cell(raw_row, column),
                            integer=attr != "listening_hours"))
        rows.append(entry)
    return rows


def aggregate_by_show(rows: List[ShowListening]) -> Dict[str, ShowListening]:
    """Sum per-storefront rows into one row per show.

    Summing has to respect the None/0 distinction: a show with a blank
    metric in every storefront stays ``None``, not ``0``. Only rows that
    actually reported a number contribute.
    """
    merged: Dict[str, ShowListening] = {}
    for row in rows:
        target = merged.get(row.show_id)
        if target is None:
            merged[row.show_id] = ShowListening(
                show_id=row.show_id, show_name=row.show_name,
                listening_hours=row.listening_hours, listeners=row.listeners,
                engaged_listeners=row.engaged_listeners, plays=row.plays)
            continue
        for attr in ("listening_hours", "listeners", "engaged_listeners", "plays"):
            addend = getattr(row, attr)
            if addend is None:
                continue
            current = getattr(target, attr)
            setattr(target, attr, addend if current is None else current + addend)
    return merged


def fetch_report_http(
    *,
    access_token: str,
    account: str,
    vendor: str,
    date: str,
    report_type: str = SHOW_REPORT_WORLDWIDE,
    sales_url: str = SALES_URL,
    timeout: int = 90,
) -> ReporterResult:
    """Fetch a report by speaking Reporter's protocol directly.

    ``Reporter.jar`` is a thin client over an HTTP endpoint, and the jar
    is the problem for automation: macOS ships no JRE, GitHub's runners
    would need a Java toolchain, and Apple's binary cannot be
    redistributed into a public repo. Posting to the same endpoint needs
    nothing but the 180-day access token, which fits in a repo secret.

    The request shape mirrors what the jar sends: a form-encoded
    ``jsonRequest`` whose ``queryInput`` is the same bracketed command
    string the CLI takes. Apple answers with the gzipped TSV directly on
    success, or an XML error document.

    Never raises. ``error`` distinguishes a dead token or a rejected
    request from a day that genuinely had no listening (``ok`` with
    empty ``rows``).
    """
    result = ReporterResult(report_type=report_type, date=date)
    if not access_token:
        result.error = "no access token"
        return result

    query = (f"[p=Reporter.properties, Sales.getReport "
             f"{vendor},{report_type},Summary,Daily,{date}]")
    payload = {
        "accesstoken": access_token,
        "version": _PROTOCOL_VERSION,
        "mode": "Robot.XML",
        "queryInput": query,
    }
    if account:
        payload["account"] = str(account)

    body = urllib.parse.urlencode({"jsonRequest": json.dumps(payload)}).encode()
    request = urllib.request.Request(
        sales_url, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Accept": "*/*"})

    try:
        with urllib.request.urlopen(request, timeout=timeout,
                                    context=_ssl_context()) as response:
            raw = response.read()
            encoding = (response.headers.get("Content-Encoding") or "").lower()
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:400]
        except Exception:  # noqa: BLE001
            pass
        # Apple returns 404 with an "no reports available" body for a
        # date with no data — a real answer, not a failure.
        if _is_no_data(detail):
            logger.info("Apple has no %s report for %s", report_type, date)
            result.no_data = True
            return result
        result.error = f"HTTP {exc.code}: {detail.strip() or exc.reason}"
        return result
    except Exception as exc:  # noqa: BLE001 — analytics never break a run
        detail = f"{type(exc).__name__}: {exc}"
        if "CERTIFICATE_VERIFY_FAILED" in detail:
            detail += ("  [this is a local trust-store problem, not Apple: a "
                       "python.org macOS build ships no CA bundle. pip install "
                       "certifi, or run '/Applications/Python 3.x/Install "
                       "Certificates.command'.]")
        result.error = detail
        return result

    if not raw:
        return result
    if raw[:2] != b"\x1f\x8b" and "gzip" not in encoding:
        # An XML/plain error document rather than a report.
        text = raw.decode("utf-8", "replace").strip()
        if _is_no_data(text):
            logger.info("Apple has no %s report for %s", report_type, date)
            result.no_data = True
            return result
        result.error = text[:400] or "empty response"
        return result

    try:
        result.rows = parse_show_listening(raw)
    except Exception as exc:  # noqa: BLE001
        result.error = f"could not parse response: {exc}"
    return result


def fetch_report(
    *,
    jar_path: Path,
    properties_path: Path,
    vendor: str,
    date: str,
    report_type: str = SHOW_REPORT_WORLDWIDE,
    work_dir: Optional[Path] = None,
    timeout: int = 180,
) -> ReporterResult:
    """Run Reporter for one day and parse the result.

    Reporter writes a ``.txt.gz`` into its working directory rather than
    printing to stdout, so the file is located afterwards by the name
    Reporter reports. Requires a JRE — macOS ships none, and the failure
    mode is a bare "Unable to locate a Java Runtime" on stderr, which is
    surfaced verbatim rather than swallowed.

    Never raises. A missing jar, a dead token, an unavailable date and a
    day with genuinely no listening are four different situations, and
    the caller has to be able to tell them apart: the first three set
    ``error``, the fourth returns ``ok`` with an empty ``rows``.
    """
    result = ReporterResult(report_type=report_type, date=date)
    jar_path = Path(jar_path)
    if not jar_path.exists():
        result.error = f"Reporter.jar not found at {jar_path}"
        return result
    if not Path(properties_path).exists():
        result.error = f"properties file not found at {properties_path}"
        return result

    cwd = Path(work_dir or jar_path.parent)
    # The parameter list is ONE argument with no spaces. Spaces after the
    # commas make the shell (or subprocess) split it and Reporter then
    # reports a misleading "Invalid vendor number specified".
    params = f"{vendor},{report_type},Summary,Daily,{date}"
    cmd = ["java", "-jar", str(jar_path),
           f"p={Path(properties_path).name}", f"Sales.getReport {params}"]

    try:
        proc = subprocess.run(
            ["java", "-jar", str(jar_path), f"p={Path(properties_path).name}",
             "Sales.getReport", params],
            cwd=str(cwd), capture_output=True, text=True, timeout=timeout,
        )
    except FileNotFoundError:
        result.error = "java not on PATH (macOS ships no JRE; install a JDK)"
        return result
    except subprocess.TimeoutExpired:
        result.error = f"Reporter timed out after {timeout}s"
        return result

    output = f"{proc.stdout}\n{proc.stderr}".strip()
    if "Successfully downloaded" not in output:
        if _is_no_data(output):
            logger.info("Apple has no %s report for %s", report_type, date)
            result.no_data = True
            return result
        if proc.returncode != 0:
            result.error = output.splitlines()[0] if output else "Reporter failed"
            return result

    downloaded = None
    for line in output.splitlines():
        if "Successfully downloaded" in line:
            downloaded = cwd / line.split()[-1]
            break
    if downloaded is None or not downloaded.exists():
        if _is_no_data(output):
            logger.info("Apple has no %s report for %s", report_type, date)
            result.no_data = True
            return result
        result.error = output.splitlines()[0] if output else "no file produced"
        return result

    try:
        result.rows = parse_show_listening(downloaded.read_bytes())
    except Exception as exc:  # noqa: BLE001 — analytics never break a run
        result.error = f"could not parse {downloaded.name}: {exc}"
    logger.debug("Reporter command was: %s", " ".join(cmd))
    return result
