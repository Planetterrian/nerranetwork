"""Sept 30 2026: recordings that are kept but never published (Meridan
Zerner's and Chad Law's first recordings, both being re-recorded, and the
Sept 9-10 rehearsals) live in a private archive instead of being deleted."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text()


def _body(start, end):
    s = WORKER[WORKER.index(start):]
    return s[:s.index(end)]


def test_archive_is_a_decision_on_the_review_page():
    assert '["approve", "kill", "archive"].includes(body.decision)' in WORKER
    assert "decide('archive')" in WORKER


def test_nothing_downstream_publishes_an_archived_episode():
    # Auto-approval only ever looks at approved_by_patrick.
    assert 'editorial_packages?status=eq.approved_by_patrick&guest_review_deadline=not.is.null' in WORKER
    page = _body("async function handleGuestReviewPage(", "async function handleGuestReviewSubmit(")
    assert 'pkg.status === "archived"' in page
    submit = _body("async function handleGuestReviewSubmit(", "// -- Admin UIs")
    assert 'pkg.status === "archived"' in submit.split("const body")[0]
    publish = (ROOT / "pipelines" / "voices" / "publish_episode.py").read_text()
    assert 'status=eq.approved_by_guest' in publish


def test_the_archive_page_is_private():
    page = _body("async function handleArchivePage(", "async function handleArchiveLink(")
    assert "archiveToken(env)" in page and "Link not found" in page
    assert "status=eq.archived" in page
    link = _body("async function handleArchiveLink(", "async function handleAdminReview(")
    assert "operatorEmail(env)" in link
