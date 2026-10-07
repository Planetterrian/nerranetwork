"""Oct 7 2026 site review — trust, legal, static and member pages.

What these guard, item by item:

1. Gate 2 as built, on every surface. "Nothing publishes until the guest
   approves" had survived the Sep 22 pass on seven surfaces (the mira.html
   meta description, the claims-ledger rows, the FAQ, the editorial page,
   both apply forms). The sweep below reads every generate_html.py and
   engine/*.py string literal, every page template and both hand-written
   apply pages.
2. The AI disclosure's narration list is read from the YAML ``tts`` blocks
   (Mira reads eight news shows; DP Pod is two voices; Offshore North is
   Dan), and its show count is computed.
3. The FAQ's cadence answer is rendered from the registry ``schedule``
   strings, page and JSON-LD alike.
4. ru/index.html (hand-written): Monday cadence, no stale count, the two
   Russian-dub landers linked, small sized covers.
5. The privacy policy covers the guest-interview data flow and its
   processors, with anchors that resolve.
6-15. Member, listening, contrast, claims, contact and image fixes.

Pages are rendered through the real generators into ``tmp_path``.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

import generate_html as G
from engine import brand

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
APPLY_PAGES = (ROOT / "age-of-ai-apply.html", ROOT / "nerra-voices-apply.html")


def _strip_jinja_comments(text: str) -> str:
    return re.sub(r"\{#.*?#\}", "", text, flags=re.S)


def _flat(text: str) -> str:
    return " ".join(text.lower().split())


def _markup_only(html: str) -> str:
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.S)
    return re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.S)


def _string_literals(path: Path) -> list:
    """Every str constant in a module except docstrings (prose about the
    history of a sentence is allowed to quote it)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(
                    getattr(body[0], "value", None), ast.Constant) and isinstance(
                    body[0].value.value, str):
                docstrings.add(id(body[0].value))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in docstrings:
            out.append(node.value)
        elif isinstance(node, ast.JoinedStr):
            out.append("".join(v.value for v in node.values
                               if isinstance(v, ast.Constant) and isinstance(v.value, str)))
    return out


# ---------------------------------------------------------------------------
# 1. Gate 2 as built
# ---------------------------------------------------------------------------

OVERCLAIMS = (
    "until the guest approves",
    "until the guest has approved",
    "nothing publishes until",
    "every guest approves",
    "guest approves their own transcript",
    "the guest approves their transcript",
    "you approve the episode before it is published",
    "the one mira should call",
    "calls real people",
)

#: Surfaces another part of the Oct 7 pass owns (engine/topic_hubs.py).
#: Listed so the exemption is visible, not silent. The email templates
#: (templates/email/, not globbed below) still carry the overclaim and are
#: an operator item from this pass.
_ELSEWHERE = {"topic_hubs.py"}


def _gate_surfaces() -> dict:
    out = {"generate_html.py": " ".join(_string_literals(ROOT / "generate_html.py"))}
    for path in sorted((ROOT / "engine").glob("*.py")):
        if path.name in _ELSEWHERE:
            continue
        out[f"engine/{path.name}"] = " ".join(_string_literals(path))
    for path in sorted(TEMPLATES.glob("*.j2")):
        out[f"templates/{path.name}"] = _strip_jinja_comments(path.read_text(encoding="utf-8"))
    for path in APPLY_PAGES:
        out[path.name] = path.read_text(encoding="utf-8")
    return out


class TestGateTwoOnEverySurface:
    def test_no_surface_claims_the_guest_holds_a_gate_with_no_timer(self):
        bad = []
        for name, text in _gate_surfaces().items():
            low = _flat(re.sub(r"<[^>]+>", " ", text))
            for phrase in OVERCLAIMS:
                if phrase in low:
                    bad.append(f"{name}: {phrase!r}")
        assert not bad, (
            "gate 2 auto-approves after seven days of silence "
            "(workers/voices/src/index.ts) — " + "; ".join(bad))

    def test_the_sweep_would_catch_the_old_meta_description(self):
        old = ("Mira is the Nerra Network's AI host. She anchors the daily "
               "combined edition and interviews real people live — and nothing "
               "publishes until the guest approves their own transcript.")
        assert any(p in _flat(old) for p in OVERCLAIMS)

    def test_the_mira_meta_description_comes_from_brand(self, tmp_path):
        G.generate_mira_page(output_dir=tmp_path)
        html = (tmp_path / "mira.html").read_text(encoding="utf-8")
        desc = re.search(r'<meta name="description" content="([^"]*)"', html).group(1)
        assert desc.replace("&#39;", "'").replace("&amp;", "&") == brand.MIRA_PAGE_DESCRIPTION
        assert "week" in brand.MIRA_PAGE_DESCRIPTION

    def test_the_interview_ledger_rows_state_the_week_and_the_takedown(self):
        from engine.claims_ledger import NOT_APPLICABLE
        for slug in ("age_of_ai", "nerra_voices"):
            low = _flat(NOT_APPLICABLE[slug])
            assert "week" in low and "takedown" in low, slug

    @pytest.mark.parametrize("path", APPLY_PAGES, ids=lambda p: p.name)
    def test_each_apply_page_states_the_week_and_the_takedown(self, path):
        low = _flat(path.read_text(encoding="utf-8"))
        assert "a week to approve it" in low and "takedown" in low
        assert "seven days without a reply" in low


# ---------------------------------------------------------------------------
# 2. AI disclosure: who voices what, from the YAMLs
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ai_page(tmp_path_factory):
    out = tmp_path_factory.mktemp("ai")
    G.generate_legal_page("ai_disclosure", output_dir=out)
    return _markup_only((out / "ai-disclosure.html").read_text(encoding="utf-8"))


class TestAiDisclosureNarration:
    def _groups(self):
        return {g["key"]: [s["name"] for s in g["shows"]] for g in G._narration_groups()}

    def test_every_mira_news_show_is_listed_as_mira(self):
        groups = self._groups()
        for slug in brand.MIRA_NEWS_SHOW_SLUGS:
            if slug in G._published_show_ids():
                assert G.NETWORK_SHOWS[slug]["name"] in groups["mira"], slug

    def test_dp_pod_is_two_voices_and_offshore_north_is_dan(self):
        groups = self._groups()
        assert G.NETWORK_SHOWS["dp_pod"]["name"] in groups["dialogue"]
        assert G.NETWORK_SHOWS["offshore_north"]["name"] in groups["0vscf8u8yrxc"]
        patrick = groups["kdif6sqjcyiq"]
        for slug in ("dp_pod", "offshore_north", "vancouver", "omni_view_world"):
            assert G.NETWORK_SHOWS[slug]["name"] not in patrick, slug

    def test_every_publishing_show_appears_once(self):
        names = [n for shows in self._groups().values() for n in shows]
        expected = [G.NETWORK_SHOWS[s]["name"] for s in G._published_show_ids()]
        assert sorted(names) == sorted(expected)

    def test_a_show_with_no_feed_is_not_listed(self):
        names = {n for shows in self._groups().values() for n in shows}
        for slug, cfg in G.NETWORK_SHOWS.items():
            if not (ROOT / cfg["rss_file"]).exists():
                assert cfg["name"] not in names, slug

    def test_the_page_renders_the_list_and_a_computed_count(self, ai_page):
        assert 'id="narration"' in ai_page
        assert "eighteen" not in ai_page.lower()
        n = len(G._published_show_ids())
        assert f"{n}\n            shows can publish on their own schedules" in ai_page \
            or f"{n} shows can publish on their own schedules" in _flat(ai_page)
        assert "Two custom voices in conversation" in ai_page
        assert "English shows are voiced by a custom voice" not in ai_page

    def test_the_page_names_one_listener_address(self, ai_page):
        assert "gmail.com" not in ai_page
        assert f"mailto:{brand.CONTACT_EMAIL}" in ai_page


# ---------------------------------------------------------------------------
# 3. FAQ cadence, from the registry
# ---------------------------------------------------------------------------

def _cron_map() -> dict:
    from tests.test_dp_pod_weekly_2026_09_21 import _cron_map as cm
    return cm()


@pytest.fixture(scope="module")
def faq_page(tmp_path_factory):
    out = tmp_path_factory.mktemp("faq")
    G.generate_faq_page(output_dir=out)
    return (out / "faq.html").read_text(encoding="utf-8")


class TestFaqCadence:
    def _ld_answer(self, html):
        for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
            data = json.loads(m.group(1))
            if data.get("@type") == "FAQPage":
                for q in data["mainEntity"]:
                    if "How often" in q["name"]:
                        return q["acceptedAnswer"]["text"]
        raise AssertionError("no cadence question in the FAQPage JSON-LD")

    def test_page_and_json_ld_carry_the_same_answer(self, faq_page):
        answer = self._ld_answer(faq_page)
        assert answer == G._cadence_answer()
        visible = _flat(re.sub(r"<[^>]+>", " ", _markup_only(faq_page)))
        assert _flat(answer.replace("&", "&amp;")) in visible.replace("&amp;amp;", "&amp;") \
            or _flat(answer) in visible

    def test_no_retired_cadence_survives(self, faq_page):
        low = _flat(faq_page)
        for stale in ("odd weekdays", "even days", "runs weekdays", "через день"):
            assert not re.search(rf"\b{stale}\b", low), stale

    def test_every_monday_only_show_is_named(self, faq_page):
        answer = self._ld_answer(faq_page)
        for slug, (_cron, day_filter) in _cron_map().items():
            if day_filter == "monday" and slug in G._published_show_ids():
                assert G.NETWORK_SHOWS[slug]["name"] in answer, slug

    def test_every_non_daily_publishing_show_is_named(self, faq_page):
        from engine.cadence import cadence_adjective
        answer = self._ld_answer(faq_page)
        for slug in G._published_show_ids():
            sched = G.NETWORK_SHOWS[slug].get("schedule") or ""
            if cadence_adjective(sched) != "daily":
                assert G.NETWORK_SHOWS[slug]["name"] in answer, slug


# ---------------------------------------------------------------------------
# 4. ru/index.html (hand-written)
# ---------------------------------------------------------------------------

class TestRussianIndex:
    @pytest.fixture()
    def page(self):
        return (ROOT / "ru" / "index.html").read_text(encoding="utf-8")

    def test_cadence_is_monday(self, page):
        assert "Через день" not in page
        assert page.count("По понедельникам") >= 2

    def test_no_stale_english_show_count(self, page):
        assert "семь подкастов" not in page

    def test_the_dub_landers_are_linked_and_exist(self, page):
        for name in ("spacex.html", "tesla.html"):
            assert f'href="{name}"' in page
            assert (ROOT / "ru" / name).exists()

    def test_covers_are_the_small_sized_webps(self, page):
        assert not re.search(r'covers/[a-z-]+\.jpg', page)
        for tag in re.findall(r"<img\b[^>]*>", page):
            assert "-400.webp" in tag and "width=" in tag and "height=" in tag, tag
            assert (ROOT / re.search(r'src="\.\./([^"]+)"', tag).group(1)).exists()


# ---------------------------------------------------------------------------
# 5. Privacy policy: guests, processors, anchors
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def privacy_page(tmp_path_factory):
    out = tmp_path_factory.mktemp("privacy")
    G.generate_legal_page("privacy_policy", output_dir=out)
    return _markup_only((out / "privacy-policy.html").read_text(encoding="utf-8"))


class TestPrivacyGuests:
    def test_the_guest_section_exists_and_is_linked(self, privacy_page):
        assert 'id="guests"' in privacy_page
        assert 'href="#guests"' in privacy_page

    @pytest.mark.parametrize("processor", [
        "Supabase", "Voximplant", "Cal.com", "xAI", "Resend", "Whisper", "R2",
    ])
    def test_every_guest_processor_is_named(self, privacy_page, processor):
        assert processor in privacy_page

    def test_what_is_recorded_is_stated(self, privacy_page):
        low = _flat(privacy_page)
        for fact in ("phone number", "recorded", "transcript", "video", "takedown"):
            assert fact in low, fact

    def test_no_retention_period_is_invented_for_interviews(self, privacy_page):
        guest = privacy_page.split('id="guests"')[1].split("Information collected automatically")[0]
        assert not re.search(r"\b\d+\s+(days|months|years)\b", guest)

    def test_every_in_page_anchor_resolves(self, privacy_page):
        ids = set(re.findall(r'id="([^"]+)"', privacy_page))
        for target in re.findall(r'href="#([^"]+)"', privacy_page):
            if target in ("main-content",):
                continue
            assert target in ids, target

    def test_every_section_heading_has_an_id(self, privacy_page):
        body = privacy_page.split('class="legal-body"')[1].split("</nav>", 1)[1]
        for h2 in re.findall(r"<h2[^>]*>", body):
            assert "id=" in h2, h2

    def test_one_listener_address(self, privacy_page):
        assert "gmail.com" not in privacy_page
        assert f"mailto:{brand.CONTACT_EMAIL}" in privacy_page

    def test_apply_pages_link_the_guest_section(self):
        for path in APPLY_PAGES:
            assert 'href="privacy-policy.html#guests"' in path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 6. Join: one roster count everywhere
# ---------------------------------------------------------------------------

class TestJoinCounts:
    def test_hero_stat_and_step_read_the_personal_roster(self, tmp_path):
        G.generate_join_page(output_dir=tmp_path)
        html = _markup_only((tmp_path / "join.html").read_text(encoding="utf-8"))
        n = len(G._personal_shows_list())
        assert f'class="np-hero-sub">{n} shows to pick from' in html
        assert f"<strong>{n}</strong><span>shows to pick from" in html
        assert f"Choose from the {n} English shows" in html
        assert "13 daily English shows" not in html

    def test_the_template_types_no_count(self):
        src = _strip_jinja_comments((TEMPLATES / "join_page.html.j2").read_text(encoding="utf-8"))
        assert "else 13" not in src
        assert "all_shows|length }} shows" not in src


# ---------------------------------------------------------------------------
# 7. How to listen: honest hero, RSS visible on a phone
# ---------------------------------------------------------------------------

class TestHowToListen:
    @pytest.fixture()
    def page(self, tmp_path):
        out = tmp_path
        G.generate_how_to_listen_page(output_dir=out)
        return (out / "how-to-listen.html").read_text(encoding="utf-8")

    def test_the_hero_does_not_claim_every_directory(self, page):
        assert "Every Nerra Network show is available on Apple Podcasts" not in page

    def test_every_row_labels_its_rss_cell(self, page):
        rows = re.findall(r"<tr>\s*<td>.*?</tr>", _markup_only(page), re.S)
        assert rows
        for row in rows:
            assert 'data-label="RSS"' in row

    def test_phones_get_cards_not_a_sideways_table(self, page):
        css = re.search(r"@media \(max-width: 640px\) \{(.*?)\n        \}", page, re.S)
        assert css and "attr(data-label)" in css.group(1)
        assert "overflow-x: auto" not in page.split(".htl-faq {")[0].split(".htl-table td.na")[1]


# ---------------------------------------------------------------------------
# 8. Contrast: no #6B47FF text, accent text mixed toward white
# ---------------------------------------------------------------------------

class TestContrast:
    def test_mira_page_text_never_uses_the_accent(self):
        src = (TEMPLATES / "mira_page.html.j2").read_text(encoding="utf-8")
        assert not re.search(r"(?<!background: )(?<!-)color:\s*var\(--nn-accent\)", src)

    def test_data_hub_accent_text_is_mixed(self):
        src = (TEMPLATES / "data_hub.html.j2").read_text(encoding="utf-8")
        assert not re.search(r"(?<![-\w])color:var\(--accent", src)

    @pytest.mark.parametrize("name", [
        "editorial", "about", "books_page", "join_page", "support_page",
        "how_to_listen", "faq", "contact", "account_page", "ru_landing",
        "login_page", "mira_page",
    ])
    def test_prose_links_are_visible(self, name):
        src = (TEMPLATES / f"{name}.html.j2").read_text(encoding="utf-8")
        assert re.search(r"p a[^{]*\{[^}]*text-decoration:\s*underline", src), name


# ---------------------------------------------------------------------------
# 9. Account and login
# ---------------------------------------------------------------------------

class TestAccountAndLogin:
    def test_account_email_field_is_labelled(self):
        src = (TEMPLATES / "account_page.html.j2").read_text(encoding="utf-8")
        field = re.search(r'<input type="email"[^>]*name="email"[^>]*>', src).group(0)
        assert 'autocomplete="email"' in field
        fid = re.search(r'id="([^"]+)"', field).group(1)
        assert f'<label for="{fid}"' in src

    def test_a_refused_login_request_is_not_a_sent_link(self):
        src = (TEMPLATES / "account_page.html.j2").read_text(encoding="utf-8")
        login = src.split("login: function (form)")[1].split("save: function")[0]
        assert "if (!r.ok)" in login
        assert login.index("if (!r.ok)") < login.index("btn.textContent = 'Check your inbox'")

    def test_login_has_no_button_inside_a_link(self):
        src = (TEMPLATES / "login_page.html.j2").read_text(encoding="utf-8")
        assert not re.search(r"<a\b[^>]*>\s*<button", src)

    def test_login_error_is_announced(self):
        src = (TEMPLATES / "login_page.html.j2").read_text(encoding="utf-8")
        err = re.search(r'<p[^>]*id="nn-login-err"[^>]*>', src).group(0)
        assert 'role="alert"' in err

    @pytest.mark.parametrize("name", ["login_page", "account_page"])
    def test_heading_reads_whole(self, name):
        src = (TEMPLATES / f"{name}.html.j2").read_text(encoding="utf-8")
        assert "Sign in to your Nerra account</h1>" in src
        assert "Sign in to your Nerra</h1>" not in src


# ---------------------------------------------------------------------------
# 10-11. The RU lander clears the nav; the apply forms fit a phone
# ---------------------------------------------------------------------------

class TestLandersAndForms:
    def test_ru_hero_clears_the_fixed_nav(self):
        src = (TEMPLATES / "ru_landing.html.j2").read_text(encoding="utf-8")
        hero = re.search(r"\.ru-hero \{(.*?)\}", src, re.S).group(1)
        assert "var(--nav-height)" in hero
        assert ".ru-hero { padding-top: calc(var(--nav-height)" in src

    @pytest.mark.parametrize("path", APPLY_PAGES, ids=lambda p: p.name)
    def test_apply_select_fits_and_the_page_has_a_background(self, path):
        src = path.read_text(encoding="utf-8")
        rule = re.search(r"input, textarea, select \{(.*?)\}", src, re.S)
        assert rule and "max-width: 100%" in rule.group(1)
        assert re.search(r"html \{[^}]*background", src)
        assert "color-scheme: dark" in src
        assert "patrick@planetterrian.com" not in src


# ---------------------------------------------------------------------------
# 12. Claims: per-status badges, distinct labels, steps as a list
# ---------------------------------------------------------------------------

class TestClaimsPage:
    def test_every_status_has_a_distinct_label(self):
        labels = [pair[0] for pair in brand.CLAIMS_STATUS_LABELS.values()]
        assert len(labels) == len(set(labels))

    def test_episode_summary_badges_each_flag_by_its_own_status(self, tmp_path):
        from tests.test_claims_pages_2026_10_01 import TODAY, _write_flag_era_tree
        root = _write_flag_era_tree(tmp_path)
        out = tmp_path / "site"
        G.generate_claims_pages(output_dir=out, digests_root=root, today=TODAY,
                                slugs=["mag7"])
        html = _markup_only((out / "claims" / "mag7.html").read_text(encoding="utf-8"))
        counts = re.search(r'<span class="nn-claims-episode-counts">(.*?)</summary>',
                           html, re.S).group(1)
        assert "nn-claims-badge--unverified_unreachable" in counts
        assert "nn-claims-badge--unverified_uncovered" in counts
        assert " marked" not in counts

    def test_show_page_steps_are_a_list(self, tmp_path):
        from tests.test_claims_pages_2026_10_01 import TODAY, _write_flag_era_tree
        root = _write_flag_era_tree(tmp_path)
        out = tmp_path / "site"
        G.generate_claims_pages(output_dir=out, digests_root=root, today=TODAY,
                                slugs=["mag7"])
        html = (out / "claims" / "mag7.html").read_text(encoding="utf-8")
        steps = re.search(r'<ol class="nn-claims-steps nn-claims-steps--compact">(.*?)</ol>',
                          html, re.S).group(1)
        assert steps.count("<summary>") == 4


# ---------------------------------------------------------------------------
# 13. One listener-facing address
# ---------------------------------------------------------------------------

class TestOneAddress:
    def test_no_page_template_carries_a_personal_mailbox(self):
        for path in sorted(TEMPLATES.glob("*.j2")):
            if path.name.startswith("show_page_dp_pod"):
                continue  # the Dispatch mailbox; not in this pass's scope
            assert "gmail.com" not in path.read_text(encoding="utf-8"), path.name

    @pytest.mark.parametrize("name", [
        "privacy_policy", "terms_of_service", "ai_disclosure", "support_page",
        "books_page",
    ])
    def test_the_page_uses_the_brand_address(self, name):
        src = (TEMPLATES / f"{name}.html.j2").read_text(encoding="utf-8")
        assert "mailto:{{ contact_email }}" in src


# ---------------------------------------------------------------------------
# 14. Book covers do not collapse the layout
# ---------------------------------------------------------------------------

def test_book_covers_are_sized_and_lazy():
    src = (TEMPLATES / "books_page.html.j2").read_text(encoding="utf-8")
    tag = re.search(r'<img src="\{\{ v\.files\.cover \}\}"[^>]*>', src).group(0)
    for attr in ('width="', 'height="', 'loading="lazy"', 'decoding="async"'):
        assert attr in tag, attr
    assert "aspect-ratio: 5 / 8" in src


# ---------------------------------------------------------------------------
# 15. Language and show counts are computed
# ---------------------------------------------------------------------------

class TestComputedCounts:
    def test_listening_languages_read_the_yamls(self):
        langs = G._listening_languages()
        assert langs[0] == "en" and "ru" in langs
        for slug in G.NETWORK_SHOWS:
            cfg = G._registry_show_config(slug)
            if cfg and cfg.multilingual.enabled:
                assert set(cfg.multilingual.languages) <= set(langs), slug

    def test_support_and_about_render_the_computed_count(self, tmp_path):
        n = len(G._listening_languages())
        G.generate_support_page(output_dir=tmp_path)
        G.generate_about_page(output_dir=tmp_path)
        support = _flat((tmp_path / "support.html").read_text(encoding="utf-8"))
        about = (tmp_path / "about.html").read_text(encoding="utf-8")
        assert f"in {n} listening languages" in support
        assert f'<div class="about-stat-value">{n}</div>' in about

    @pytest.mark.parametrize("name", ["support_page", "about"])
    def test_no_typed_language_count(self, name):
        src = _strip_jinja_comments((TEMPLATES / f"{name}.html.j2").read_text(encoding="utf-8"))
        assert "in four" not in src
        assert '<div class="about-stat-value">4</div>' not in src

    def test_a_show_with_no_feed_is_not_counted(self):
        assert "nerra_voices" not in G._published_show_ids() or \
            (ROOT / G.NETWORK_SHOWS["nerra_voices"]["rss_file"]).exists()

