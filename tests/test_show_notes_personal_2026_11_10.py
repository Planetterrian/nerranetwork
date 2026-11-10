"""Nov 10 2026 growth review: the show notes offer My Nerra and the free
Nerra Daily email, each labelled for what it is.

The old line said "join the newsletter" and linked join.html, which is the
My Nerra page. Listeners in podcast apps (16,607 downloads in the 30 days
to Nov 9) heard about Personal only in the spoken outro rotation.
"""

from engine.funnel import parse_campaign_id
from engine.publisher import build_show_notes_footer, personal_ask_markdown

BASE = "https://nerranetwork.com"


def _campaign(url: str) -> str:
    from urllib.parse import parse_qs, urlparse
    return parse_qs(urlparse(url).query)["utm_campaign"][0]


def _links(md: str):
    import re
    return re.findall(r"\]\((https?://[^)]+)\)", md)


class TestPersonalLine:
    def test_english_show_offers_my_nerra_on_the_join_page(self):
        out = build_show_notes_footer(BASE, "omni_view", 200, has_blog=True,
                                      personal_trial_days=7)
        join = [u for u in _links(out) if "/join.html" in u]
        assert len(join) == 1
        assert "My Nerra" in out and "7 days" in out and "$4.99" in out
        parsed = parse_campaign_id(_campaign(join[0]))
        assert parsed and parsed.show == "omni_view"
        assert parsed.variant == "personal"

    def test_flagships_get_their_own_pitch(self):
        for slug, name in (("spacex", "SpaceX Daily"), ("tesla", "Tesla Shorts Time")):
            out = build_show_notes_footer(BASE, slug, 700, has_blog=True)
            assert f"Your morning in one episode: {name}" in out
            assert "your own stocks" in out

    def test_no_trial_is_promised_without_the_trial_setting(self):
        line = personal_ask_markdown("spacex", "https://x/join.html", trial_days=0)
        assert "free for" not in line and "$4.99" in line

    def test_members_only_show_is_never_offered_my_nerra(self):
        out = build_show_notes_footer(BASE, "omni_view_europe", 30, has_blog=True,
                                      personal_ask=False)
        assert "My Nerra" not in out
        assert "/nerra-daily.html" in out

    def test_free_email_line_goes_to_the_nerra_daily_signup(self):
        out = build_show_notes_footer(BASE, "tesla", 700, has_blog=True)
        email = [u for u in _links(out) if "/nerra-daily.html" in u]
        assert len(email) == 1
        assert email[0].endswith("#show-nerra_daily-hero-newsletter")
        assert "join the newsletter" not in out
        parsed = parse_campaign_id(_campaign(email[0]))
        assert parsed and parsed.variant == "email"

    def test_russian_feed_keeps_its_line(self):
        out = build_show_notes_footer(BASE, "finansy_prosto", 100, has_blog=True,
                                      channel="ru")
        assert "My Nerra" not in out
        assert "join the newsletter" in out and "/join.html" in out

    def test_signup_anchor_exists_on_the_page(self):
        from pathlib import Path
        page = Path(__file__).resolve().parent.parent / "nerra-daily.html"
        assert 'id="show-nerra_daily-hero-newsletter"' in page.read_text(encoding="utf-8")


class TestRunShowWiring:
    def test_run_show_passes_the_members_gate_and_trial(self):
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent / "run_show.py").read_text(encoding="utf-8")
        assert "personal_ask=_personal_ask_ok(config)" in src
        assert 'personal_trial_days=_env_int_or_zero("STRIPE_TRIAL_DAYS")' in src

    def test_members_gate_reads_the_access_setting(self):
        from types import SimpleNamespace
        from pathlib import Path
        import ast
        src = (Path(__file__).resolve().parent.parent / "run_show.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                  and n.name == "_personal_ask_ok")
        ns: dict = {}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "run_show", "exec"), ns)
        ok = ns["_personal_ask_ok"]
        assert ok(SimpleNamespace(access=SimpleNamespace(mode="members_only"))) is False
        assert ok(SimpleNamespace(access=SimpleNamespace(mode="public"))) is True
