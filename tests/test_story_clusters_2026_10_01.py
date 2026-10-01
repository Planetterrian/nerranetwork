"""Oct 1 2026 — same-story clustering (engine/story_clusters.py).

Tesla Ep622 carried one Model 3 refresh as eight items from eight outlets
and the script told it five times; the cross-section dedupe is blind to a
story told once per outlet. Clustering runs on the fetched list and
annotates the later members; nothing is dropped.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import story_clusters as sc  # noqa: E402

CREDIT = [
    {"title": "Tesla Locks in $30 Billion in New Credit as It Scales Up Optimus, Cybercab and Joint Solar Plan",
     "description": "Tesla has secured $30 billion in credit agreements with a bank group."},
    {"title": "Tesla Lines Up $30 Billion Credit Backup Ahead Of Heavy Capex Years",
     "description": "The credit lines back AI, solar and chip spending."},
    {"title": "Tesla Secures $30 Billion in Credit Lines to Fund AI, Solar and Chip Ambitions",
     "description": "Agreements with several banks, the company said in a filing."},
    {"title": "Tesla Patents 'Electric Fan Car' Weeks Before Roadster Reveal",
     "description": "A patent filing shows four ducted fans."},
    {"title": "Kakao blocks Kakao Mobility U.S. listing plan",
     "description": "The parent vetoed a planned IPO."},
    {"title": "Tesla's South Korea sales double but service staff at 17 per center",
     "description": "Repair bottlenecks reported."},
]


class TestClustering:
    def test_three_outlets_on_one_credit_story_are_one_cluster(self):
        groups = sc.cluster_articles(CREDIT)
        assert groups == [[0, 1, 2]]

    def test_the_lead_carries_no_note_and_later_members_do(self):
        notes = sc.annotate_articles(CREDIT)
        assert set(notes) == {1, 2}
        assert "article #1" in notes[1] and "ONE item" in notes[1]
        assert "instruction, not content" in notes[1]

    def test_a_show_vocabulary_token_cannot_join_two_stories(self):
        arts = [
            {"title": "A Survey on Fake Review Detection: From Pre-trained Language Models to Large Language Models"},
            {"title": "Estimating and Orthogonalizing Unknown Pre-training Gradients for Continual Fine-tuning of Large Language Models"},
            {"title": "Nvidia launches Open Agent Safety Platform to secure autonomous AI agents"},
            {"title": "OpenAI shelves new AI model release over safety concerns"},
        ]
        window = ["Large Language Models do X"] * 8 + ["Pre-trained language models and more"] * 8
        assert sc.cluster_articles(arts, window_headlines=window) == []

    def test_fewer_than_four_shared_tokens_is_not_a_story(self):
        arts = [{"title": "Tesla Model Y wins Norway in September"},
                {"title": "Tesla Model Y recall in Norway over seatbelt"}]
        assert sc.cluster_articles(arts) == []


class TestOutcomeMetric:
    def test_a_cluster_told_as_two_items_counts_once(self):
        digest = ("### Top News\n\n1. **Tesla secures $30 billion in credit lines for AI and solar**\n"
                  "body. Source: https://a\n\n2. **Tesla lines up $30 billion credit backup ahead of capex**\n"
                  "body. Source: https://b\n\n3. **Electric fan car patent lands before Roadster reveal**\nbody\n")
        assert sc.cluster_retold_in_digest(digest, CREDIT, [[0, 1, 2]]) == 1

    def test_a_cluster_told_once_counts_zero(self):
        digest = ("### Top News\n\n1. **Tesla secures $30 billion in credit lines for AI, solar and chips**\n"
                  "body. Source: https://a\n\n2. **Electric fan car patent lands before Roadster reveal**\nbody\n")
        assert sc.cluster_retold_in_digest(digest, CREDIT, [[0, 1, 2]]) == 0


class TestWiring:
    def test_config_field_and_opt_ins(self):
        from engine.config import load_config
        for slug in ("tesla", "spacex", "models_agents", "omni_view", "mag7", "omni_view_world"):
            assert load_config(ROOT / "shows" / f"{slug}.yaml").story_clusters is True, slug
        for slug in ("unintended_consequences", "first_principles", "privet_russian", "dp_pod"):
            assert load_config(ROOT / "shows" / f"{slug}.yaml").story_clusters is False, slug

    def test_run_show_annotates_and_measures(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'metrics.record("story_clusters_annotated"' in src
        assert 'metrics.record("story_clusters_retold_in_digest"' in src
        assert "_cluster_notes[i - 1]" in src


class TestSpeakableSourceName:
    def test_non_latin_outlet_becomes_the_domain_stem(self):
        from engine.article_text import speakable_source_name
        assert speakable_source_name("디지털투데이", "https://www.digitaltoday.co.kr/en/view/1") == "Digitaltoday"
        assert speakable_source_name("联合早报", "https://www.zaobao.com.sg/x") == "Zaobao"

    def test_latin_names_are_untouched(self):
        from engine.article_text import speakable_source_name
        assert speakable_source_name("The Guardian", "https://x") == "The Guardian"
        assert speakable_source_name("", "https://www.bbc.co.uk/a") == "Unknown"


class TestTtsKeepsNonLatinNames:
    def test_the_emoji_strip_no_longer_deletes_hangul_or_cjk(self):
        from assets.pronunciation import strip_emojis
        assert strip_emojis("디지털투데이 reported 联合早报 ✅") == "디지털투데이 reported 联合早报 "
        assert strip_emojis("up ▲ down ▼ → ★") == "up  down   "

    def test_a_determiner_before_a_subreddit_gets_no_second_article(self):
        from assets.pronunciation import replace_subreddit_paths
        assert replace_subreddit_paths("Another r/teslamotors thread") == "Another teslamotors subreddit thread"
        assert replace_subreddit_paths("Posted on r/teslamotors") == "Posted on the teslamotors subreddit"
