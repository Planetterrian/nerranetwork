#!/usr/bin/env python3
"""Generate static HTML pages for the Nerra Network podcast shows.

Uses Jinja2 templates to produce show pages, summaries pages, and the
network landing page — all sharing a common base template and CSS.

Usage:
    python generate_html.py --all           # Generate everything (default)
    python generate_html.py --summaries     # Generate summaries pages only
    python generate_html.py --shows         # Generate show pages only
    python generate_html.py --network       # Generate network page only
    python generate_html.py --dry-run       # Preview without writing files
    python generate_html.py --show tesla    # Generate pages for one show
"""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader

# Lone-surrogate scrubber lives in engine.utils so every component that
# writes LLM-touched text to disk (digests, TTS scripts, blog posts,
# RSS feeds, network HTML) scrubs at the same boundary. See utils.py
# for the May 7 2026 operator-caught regression that prompted this.
from engine.utils import strip_lone_surrogates as _strip_lone_surrogates

ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = ROOT / "templates"
SHOWS_DIR = ROOT / "shows"
GITHUB_RAW = "https://nerranetwork.com"

# Newsletter social proof is hidden until the subscriber count clears this
# floor — "Join 23 readers" is anti-proof, "Join 250 readers" converts.
# June 2026 website review: 100 -> 50; fifty real readers is credible
# proof and the badge was invisible through the entire early-growth phase.
MIN_SOCIAL_PROOF_SUBSCRIBERS = 50

# Channel handles for the YouTube CTA on show pages. The handle is
# determined per-show by youtube.channel in the YAML (en → @NerraNetwork,
# ru → @NerraRU).
_YT_CHANNEL_HANDLES = {
    "en": "@NerraNetwork",
    "ru": "@NerraRU",
}


def _read_show_youtube(slug: str) -> dict:
    """Pull the YouTube fields a show page needs from the show YAML.

    Returns a dict with ``youtube_enabled`` (bool),
    ``youtube_playlist_url`` (or empty string), and
    ``youtube_channel_url`` (or empty string). Cheap on disk — one
    YAML read per show per page render.
    """
    import yaml as _yaml

    yaml_path = SHOWS_DIR / f"{slug}.yaml"
    if not yaml_path.exists():
        return {
            "youtube_enabled": False,
            "youtube_playlist_url": "",
            "youtube_channel_url": "",
        }
    try:
        data = _yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    except _yaml.YAMLError:
        return {
            "youtube_enabled": False,
            "youtube_playlist_url": "",
            "youtube_channel_url": "",
        }
    yt = data.get("youtube") or {}
    enabled = bool(yt.get("enabled"))
    playlist_id = (yt.get("podcast_playlist_id") or "").strip()
    channel_key = (yt.get("channel") or "en").strip().lower()
    handle = _YT_CHANNEL_HANDLES.get(channel_key, _YT_CHANNEL_HANDLES["en"])
    return {
        "youtube_enabled": enabled,
        "youtube_playlist_url": (
            f"https://www.youtube.com/playlist?list={playlist_id}"
            if playlist_id else ""
        ),
        "youtube_channel_url": f"https://www.youtube.com/{handle}",
    }


def _read_show_image_provider(slug: str) -> str:
    """Return the show's YouTube ``image_provider`` setting (``pexels``,
    ``grok``, or ``hybrid``). Defaults to ``pexels`` to match
    run_show.py's default — only shows that opt into ``grok`` produce
    gallery images, so this is the signal the show page uses to
    decide whether to embed the gallery section."""
    import yaml as _yaml

    yaml_path = SHOWS_DIR / f"{slug}.yaml"
    if not yaml_path.exists():
        return "pexels"
    try:
        data = _yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    except _yaml.YAMLError:
        return "pexels"
    yt = data.get("youtube") or {}
    return (yt.get("image_provider") or "pexels").strip().lower() or "pexels"


def _collect_language_feeds(rss_file: str, prefix: str) -> list:
    """Return the per-language podcast feeds that exist for a show.

    Scans for ``<rss_stem>.<lang>.rss`` siblings of the English feed (built
    by ``scripts/build_language_feeds.py``) and returns a list of
    ``{"lang", "label", "url"}`` for the show page / how-to-listen table.
    Empty when no translated feed has been built yet, so the template
    renders nothing for English-only shows.
    """
    from engine.language_feeds import LANGUAGE_META, feed_filename

    feeds = []
    for lang, (autonym, _locale) in LANGUAGE_META.items():
        fname = feed_filename(rss_file, lang)
        if (ROOT / fname).exists():
            feeds.append({"lang": lang, "label": autonym, "url": f"{prefix}{fname}"})
    return feeds


# ---------------------------------------------------------------------------
# Marketing / Analytics configuration
# ---------------------------------------------------------------------------
# GA4 Measurement ID is committed to the repo (it's public — visible in
# page source of any GA4-tracked site). Ads ID and conversion labels are
# secrets set via GitHub Actions.
#
# - GA4_MEASUREMENT_ID: Google Analytics 4 (default: Nerra Network property)
# - GOOGLE_ADS_ID: Google Ads conversion ID (e.g. "AW-1234567890")
# - GOOGLE_ADS_SIGNUP_LABEL: Conversion label for newsletter signup
# - PLAUSIBLE_DOMAIN: Plausible analytics domain (privacy-focused alternative)
#
# When any GA4/Ads ID is set, gtag.js loads and Google Consent Mode v2 defaults
# to "denied" until the user accepts the cookie banner.

_GA4_DEFAULT = "G-6PWJCVQQ7B"  # Nerra Network GA4 property (533581233)

MARKETING_CONFIG = {
    # NOTE: `or _GA4_DEFAULT`, not a .get() default — CI passes
    # `GA4_MEASUREMENT_ID: ${{ secrets.GA4_MEASUREMENT_ID }}`, and an UNSET
    # secret arrives as an empty-but-present env var, which defeats a
    # .get() default. That stripped gtag from every CI-regenerated page
    # (homepage/blog indexes had no GA on main while nightly-regenerated
    # tesla.html, built without the env var, kept it) — caught June 2026.
    "ga4_measurement_id": (
        os.environ.get("GA4_MEASUREMENT_ID") or _GA4_DEFAULT
    ).strip(),
    "google_ads_id": os.environ.get("GOOGLE_ADS_ID", "").strip(),
    "google_ads_signup_label": os.environ.get("GOOGLE_ADS_SIGNUP_LABEL", "").strip(),
    "plausible_domain": os.environ.get("PLAUSIBLE_DOMAIN", "").strip(),
    # Google Search Console verification token (set via GSC_VERIFICATION env var).
    # Obtain from Search Console → Settings → Ownership verification → HTML tag.
    "gsc_verification": os.environ.get("GSC_VERIFICATION", "").strip(),
}

# ---------------------------------------------------------------------------
# Per-show configuration
# ---------------------------------------------------------------------------

NETWORK_SHOWS = {
    "tesla": {
        "name": "Tesla Shorts Time",
        "slug": "tesla",
        "display_order": 7,
        "description": "Daily Tesla news digest and podcast.",
        "show_page": "tesla.html",
        "summaries_page": "tesla-summaries.html",
        "json_path": "digests/tesla_shorts_time/summaries_tesla.json",
        "json_format": "wrapped",
        "rss_file": "podcast.rss",
        "podcast_image": "assets/covers/tesla-shorts-time.jpg",
        "x_account": "teslashortstime",
        "brand_color": "#E31937",
        "brand_color_dark": "#C4122E",
        "tagline": "Shorting Tesla? Time's Up.",
        "hero_tagline": "Shorting Tesla? Time's Up.",
        "schedule": "Daily",
        "episode_length": "~15 min",
        "about_text": "Tesla Shorts Time is a daily podcast delivering the most important Tesla news and developments. We focus on how Tesla is advancing its mission to accelerate the world's transition to sustainable energy, saving lives through safer vehicles, and making the world a better place.",
        "about_host": "Hosted by Patrick, each episode covers breaking news, product updates, technology breakthroughs, and the latest developments from Tesla and the broader electric vehicle world.",
        "description_long": "Daily podcast covering how Tesla is advancing its mission to accelerate the transition to sustainable energy. Covers FSD safety milestones, Cybertruck production, energy storage breakthroughs, TSLA stock movements, and why the shorts keep getting it wrong.",
        "related_show": "omni_view",
        "related_reason": "If you enjoy Tesla Shorts Time, you might also like Omni View — balanced daily news from every perspective.",
        "apple_podcasts_url": "https://podcasts.apple.com/us/podcast/tesla-shorts-time/id1855142939",
        "spotify_url": "https://open.spotify.com/show/7I1DIaUaSlVsYliigOe6sS",
        "theme_color": "#E31937",
        "meta_description": "Daily Tesla Shorts Time podcast — Tesla news, TSLA stock, FSD updates, and sustainable energy progress.",
        "meta_keywords": "Tesla podcast, TSLA news, Tesla stock, EV analysis, Tesla Shorts Time, daily digests",
        "audience": "For Tesla owners, TSLA investors, EV enthusiasts, and anyone following the transition to sustainable energy.",
        "source_highlights": ["Teslarati", "CleanTechnica", "InsideEVs", "The Verge"],
        "resource_categories": [
            {
                "title": "Investor Resources",
                "resources": [
                    {"name": "Tesla Investor Relations", "url": "https://ir.tesla.com", "desc": "Official SEC filings, earnings calls, and shareholder letters"},
                    {"name": "TSLA on Yahoo Finance", "url": "https://finance.yahoo.com/quote/TSLA", "desc": "Real-time stock price, charts, and financial data"},
                    {"name": "Tesla Daily (Rob Maurer)", "url": "https://www.youtube.com/@TeslaDaily", "desc": "Daily TSLA analysis from the most-followed Tesla stock commentator"},
                    {"name": "Hypercharts Tesla", "url": "https://hypercharts.co/tsla", "desc": "Tesla financial data visualizations — revenue, margins, deliveries"},
                    {"name": "Macrotrends TSLA", "url": "https://www.macrotrends.net/stocks/charts/TSLA/tesla/revenue", "desc": "Historical Tesla financials, ratios, and growth metrics"},
                ],
            },
            {
                "title": "News Sources",
                "resources": [
                    {"name": "Teslarati", "url": "https://www.teslarati.com", "desc": "Independent Tesla and SpaceX news — the largest dedicated Tesla news outlet"},
                    {"name": "Not A Tesla App", "url": "https://www.notateslaapp.com", "desc": "Tesla software updates, feature tracking, and release notes"},
                    {"name": "CleanTechnica", "url": "https://cleantechnica.com", "desc": "Clean energy and EV industry analysis and commentary"},
                    {"name": "InsideEVs", "url": "https://insideevs.com", "desc": "Electric vehicle news, reviews, and sales data across all brands"},
                    {"name": "Drive Tesla Canada", "url": "https://driveteslacanada.ca", "desc": "Canadian Tesla ownership news, tips, and community coverage"},
                    {"name": "Electrek", "url": "https://electrek.co", "desc": "Electric transport and clean energy news — Tesla, EVs, solar, and storage"},
                ],
            },
            {
                "title": "Community & Forums",
                "resources": [
                    {"name": "Tesla Motors Club", "url": "https://teslamotorsclub.com", "desc": "The largest Tesla owner forum — 500K+ members discussing ownership, mods, and tips"},
                    {"name": "r/TeslaMotors", "url": "https://www.reddit.com/r/TeslaMotors/", "desc": "Reddit's main Tesla community — news, reviews, and owner discussions"},
                    {"name": "r/TSLALounge", "url": "https://www.reddit.com/r/TSLALounge/", "desc": "Tesla investor community focused on TSLA stock and market analysis"},
                    {"name": "Tesla Owners Online", "url": "https://teslaownersonline.com", "desc": "Owner forum with detailed guides for Model 3, Y, S, X, and Cybertruck"},
                ],
            },
            {
                "title": "Tesla Data & Tools",
                "resources": [
                    {"name": "Tesla Blog", "url": "https://www.tesla.com/blog", "desc": "Official Tesla announcements and product updates"},
                    {"name": "PlugShare", "url": "https://www.plugshare.com", "desc": "Find EV charging stations — Supercharger network and third-party chargers"},
                    {"name": "A Better Route Planner", "url": "https://abetterrouteplanner.com", "desc": "EV trip planner with real-time range estimation for Tesla and other EVs"},
                    {"name": "TeslaFi", "url": "https://teslafi.com", "desc": "Tesla data logger — track efficiency, battery health, trips, and charging"},
                ],
            },
            {
                "title": "Learning & Deep Dives",
                "resources": [
                    {"name": "Tesla AI Day Presentations", "url": "https://www.youtube.com/results?search_query=tesla+ai+day", "desc": "Technical presentations on FSD, Optimus robot, and Dojo supercomputer"},
                    {"name": "Sandy Munro", "url": "https://www.youtube.com/@MunroLive", "desc": "Engineering teardowns and manufacturing analysis of Tesla vehicles"},
                    {"name": "Tesla Master Plan", "url": "https://www.tesla.com/blog/master-plan-part-3", "desc": "Tesla's vision for sustainable energy — Master Plan Part 3"},
                    {"name": "Third Row Tesla", "url": "https://www.youtube.com/@thirdrowtesla", "desc": "In-depth Tesla interviews and analysis from the community"},
                ],
            },
        ],
        "tools": [
            {"name": "TradingView", "url": "https://www.tradingview.com/symbols/NASDAQ-TSLA/", "desc": "Advanced TSLA charting, technical analysis, and community ideas", "badge": "Free tier"},
            {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/quote/TSLA", "desc": "Real-time TSLA quotes, financials, analyst ratings, and news", "badge": "Free"},
            {"name": "PlugShare", "url": "https://www.plugshare.com", "desc": "Find Superchargers and charging stations anywhere — essential for road trips", "badge": "Free"},
            {"name": "A Better Route Planner", "url": "https://abetterrouteplanner.com", "desc": "Plan EV road trips with accurate range estimates and charging stops", "badge": "Free"},
            {"name": "TeslaFi", "url": "https://teslafi.com", "desc": "Track your Tesla's efficiency, charging, battery degradation, and trip data", "badge": "Paid"},
            {"name": "Optiwatt", "url": "https://getoptiwatt.com", "desc": "Smart Tesla charging — schedule charging for the cheapest electricity rates", "badge": "Free"},
        ],
        "faq": [
            {"q": "What is FSD (Full Self-Driving)?", "a": "FSD is Tesla's advanced driver-assistance system that aims to enable fully autonomous driving. It uses cameras and neural networks to navigate roads, handle intersections, and park. As of 2026, FSD (Supervised) requires driver attention at all times — it's not yet fully autonomous, but Tesla is working toward unsupervised capability with its robotaxi program."},
            {"q": "What does 'shorts' mean in Tesla Shorts Time?", "a": "In stock market terminology, 'shorting' means betting that a stock's price will go down. Tesla has historically been one of the most-shorted stocks on the market. 'Tesla Shorts Time' plays on this — suggesting that time is running out for those betting against Tesla, as the company continues to grow and prove skeptics wrong."},
            {"q": "What is a Gigafactory?", "a": "A Gigafactory is Tesla's term for its massive manufacturing facilities. The name comes from 'giga' (billion) — these factories produce batteries and vehicles at a scale measured in gigawatt-hours. Tesla operates Gigafactories in Nevada, Shanghai, Berlin, and Texas, each producing hundreds of thousands of vehicles per year."},
            {"q": "What is the Tesla Megapack?", "a": "The Megapack is Tesla's utility-scale battery storage product. Each unit stores up to 4 MWh of energy — enough to power about 3,600 homes for one hour. Utilities and grid operators use Megapacks to store renewable energy from solar and wind farms, stabilize the grid, and replace fossil fuel peaker plants."},
            {"q": "What does TSLA's P/E ratio mean?", "a": "The Price-to-Earnings (P/E) ratio shows how much investors pay per dollar of Tesla's earnings. A high P/E (Tesla's is often 50-100+) means investors expect strong future growth. For comparison, traditional automakers trade at P/E ratios of 5-15. Tesla's premium reflects the market pricing in its AI, energy, and robotaxi potential beyond just car sales."},
        ],
        "referral": {
            "url": "https://ts.la/patrick84289",
            "heading": "Buy a Tesla & Get Free Stuff",
            "cta": "Order a Tesla with Free FSD Trial",
            "intro": "Use our referral link when ordering your new Tesla and you'll receive free benefits at no extra cost. It's Tesla's way of rewarding customers who spread the word.",
            "buyer_benefits": [
                "3 months of Full Self-Driving (Supervised) free — a $297 value",
                "Works on Model 3, Model Y, and Cybertruck orders",
                "No extra cost — the referral discount is applied automatically",
            ],
            "energy_benefits": [
                "$400 rebate on Solar Panels or Solar Roof installations",
                "Rebates available on Powerwall 3 installations",
            ],
            "how_to_steps": [
                "Click our referral link below to visit Tesla.com",
                "Configure your vehicle (Model 3, Model Y, or Cybertruck) or energy product",
                "Place your order — the referral is applied automatically at checkout",
                "Enjoy 3 free months of FSD Supervised when you take delivery",
            ],
            "fine_print": "Referral benefits are subject to Tesla's current program terms and may change. Must be applied at time of order — cannot be added after purchase. Applies to new vehicle and energy product orders only. See Tesla.com for full details.",
        },
    },
    "omni_view": {
        "name": "Omni View",
        "slug": "omni_view",
        "display_order": 3,
        "description": "Daily balanced news summaries from diverse sources.",
        "show_page": "omni-view.html",
        "summaries_page": "omni-view-summaries.html",
        "json_path": "digests/omni_view/summaries_omni.json",
        "json_format": "wrapped",
        "rss_file": "omni_view_podcast.rss",
        "podcast_image": "assets/covers/omni-view.jpg",
        "x_account": "omniviewnews",
        "brand_color": "#0B6FD6",
        "brand_color_dark": "#0B1B3B",
        "tagline": "See every side. Decide for yourself.",
        "hero_tagline": "See every side. Decide for yourself.",
        "schedule": "Daily",
        "episode_length": "~20 min",
        "about_text": "Omni View is a neutral, media-literacy-first daily briefing designed for everyone from children to seniors. Covers top world, business, technology, and media stories with perspectives from across the political spectrum.",
        "about_host": "Hosted by Patrick in Vancouver. Helping you form your own informed opinions through balanced, multi-perspective coverage.",
        "description_long": "A neutral, media-literacy-first daily briefing designed for everyone from children to seniors. Covers top world, business, technology, and media stories with perspectives from across the political spectrum — so you can decide for yourself.",
        "related_show": "tesla",
        "related_reason": "If you enjoy Omni View, you might also like Tesla Shorts Time — daily news focused on Tesla and sustainable energy.",
        "apple_podcasts_url": "https://podcasts.apple.com/us/podcast/omni-view-balanced-news-perspectives/id1885661594",
        "spotify_url": "https://open.spotify.com/show/4KuOgvZMm4Mweorshrm2qR",
        "theme_color": "#0B6FD6",
        "meta_description": "Omni View — Daily balanced news summaries from diverse sources. Multiple perspectives on the stories that matter.",
        "meta_keywords": "balanced news, diverse perspectives, media literacy, news analysis, unbiased reporting",
        "audience": "For thoughtful news consumers who want every side of the story — not just the one their algorithm picks.",
        "source_highlights": ["NPR", "BBC", "Reuters", "WSJ", "Al Jazeera", "The Guardian"],
        "resource_categories": [
            {
                "title": "Media Bias & Literacy Tools",
                "resources": [
                    {"name": "AllSides Media Bias Ratings", "url": "https://www.allsides.com/media-bias/ratings", "desc": "See where 800+ news sources fall on the political spectrum — crowd-sourced and editorial ratings"},
                    {"name": "Ad Fontes Media Bias Chart", "url": "https://adfontesmedia.com", "desc": "Interactive chart rating news sources on reliability and political bias"},
                    {"name": "Media Bias/Fact Check", "url": "https://mediabiasfactcheck.com", "desc": "Independent media bias and factual reporting database — 7,000+ sources rated"},
                    {"name": "The News Literacy Project", "url": "https://newslit.org", "desc": "Free tools and lessons for evaluating news credibility — great for students and adults"},
                    {"name": "First Draft News", "url": "https://firstdraftnews.org", "desc": "Research and training on misinformation, disinformation, and media manipulation"},
                ],
            },
            {
                "title": "Wire Services & Neutral Sources",
                "resources": [
                    {"name": "Reuters", "url": "https://www.reuters.com", "desc": "Global wire service known for factual, neutral reporting across politics and business"},
                    {"name": "AP News", "url": "https://apnews.com", "desc": "Non-profit global news wire — one of the most trusted sources for straight news"},
                    {"name": "BBC News", "url": "https://www.bbc.com/news", "desc": "British public broadcaster — comprehensive international coverage with editorial standards"},
                    {"name": "NPR", "url": "https://www.npr.org", "desc": "US public radio — in-depth reporting on politics, culture, science, and economics"},
                    {"name": "PBS NewsHour", "url": "https://www.pbs.org/newshour/", "desc": "US public television news — long-form reporting without commercial pressure"},
                ],
            },
            {
                "title": "Left-Leaning Sources",
                "resources": [
                    {"name": "The Guardian", "url": "https://www.theguardian.com", "desc": "UK-based global coverage with progressive editorial perspective — free, no paywall"},
                    {"name": "The Intercept", "url": "https://theintercept.com", "desc": "Investigative journalism focused on civil liberties, government accountability, and justice"},
                    {"name": "Mother Jones", "url": "https://www.motherjones.com", "desc": "Investigative reporting on politics, environment, and social justice"},
                    {"name": "Vox", "url": "https://www.vox.com", "desc": "Explanatory journalism — complex stories broken down with context and data"},
                ],
            },
            {
                "title": "Right-Leaning Sources",
                "resources": [
                    {"name": "Wall Street Journal", "url": "https://www.wsj.com", "desc": "Business and financial news with center-right editorial perspective"},
                    {"name": "National Review", "url": "https://www.nationalreview.com", "desc": "Conservative commentary and analysis on politics, culture, and policy"},
                    {"name": "The Dispatch", "url": "https://thedispatch.com", "desc": "Fact-based conservative journalism — emphasis on accuracy over outrage"},
                    {"name": "Reason", "url": "https://reason.com", "desc": "Libertarian perspective on politics, culture, and ideas — free markets and individual liberty"},
                ],
            },
            {
                "title": "International Perspectives",
                "resources": [
                    {"name": "Al Jazeera English", "url": "https://www.aljazeera.com", "desc": "Middle East-based global coverage — perspectives often underrepresented in Western media"},
                    {"name": "Deutsche Welle (DW)", "url": "https://www.dw.com/en/", "desc": "Germany's international broadcaster — European perspective on global events"},
                    {"name": "France 24", "url": "https://www.france24.com/en/", "desc": "French international news — European and African coverage with global lens"},
                    {"name": "South China Morning Post", "url": "https://www.scmp.com", "desc": "Hong Kong-based English coverage of China and Asia-Pacific affairs"},
                ],
            },
            {
                "title": "Fact-Checking",
                "resources": [
                    {"name": "FactCheck.org", "url": "https://www.factcheck.org", "desc": "Non-partisan fact-checking from the Annenberg Public Policy Center at UPenn"},
                    {"name": "PolitiFact", "url": "https://www.politifact.com", "desc": "Pulitzer Prize-winning fact-checking — rates claims on a Truth-O-Meter scale"},
                    {"name": "Snopes", "url": "https://www.snopes.com", "desc": "The internet's oldest fact-checking site — urban legends, viral claims, and political checks"},
                    {"name": "Full Fact", "url": "https://fullfact.org", "desc": "UK's independent fact-checking charity — clear verdicts on public claims"},
                ],
            },
        ],
        "tools": [
            {"name": "Ground News", "url": "https://ground.news", "desc": "See how left, center, and right outlets cover the same story side by side", "badge": "Freemium"},
            {"name": "AllSides", "url": "https://www.allsides.com", "desc": "Balanced news feed showing headlines from left, center, and right perspectives", "badge": "Free"},
            {"name": "Feedly", "url": "https://feedly.com", "desc": "Build your own balanced news feed from multiple sources — organize by topic and bias", "badge": "Free tier"},
            {"name": "Perplexity", "url": "https://www.perplexity.ai", "desc": "AI-powered research tool — ask questions and get sourced answers from across the web", "badge": "Free tier"},
            {"name": "Google News", "url": "https://news.google.com", "desc": "Aggregated headlines from thousands of sources — see full coverage of any story", "badge": "Free"},
        ],
        "faq": [
            {"q": "What is media bias?", "a": "Media bias is the tendency of a news outlet to present information in a way that favors a particular political viewpoint, ideology, or narrative. It can appear in story selection (what gets covered), framing (how it's described), word choice, and source selection. Every outlet has some degree of bias — the key is recognizing it and reading multiple perspectives."},
            {"q": "What's the difference between news and opinion?", "a": "News reporting aims to present facts — who, what, when, where, why — with minimal editorial interpretation. Opinion pieces (editorials, columns, op-eds) express the author's views and arguments about those facts. Many outlets mix both, which is why media literacy matters. Look for labels like 'Opinion,' 'Analysis,' or 'Editorial' to distinguish them."},
            {"q": "What is a wire service?", "a": "A wire service (like AP, Reuters, or AFP) is a news organization that gathers and distributes news to other media outlets. They focus on straight factual reporting without editorial slant, because their stories are used by newspapers, TV stations, and websites across the political spectrum. Wire service reports are generally considered among the most reliable news sources."},
            {"q": "How do I identify misinformation?", "a": "Check multiple sources — if only one outlet reports something, be skeptical. Look at the source's track record on fact-checking databases. Check if the story cites primary sources (documents, studies, official statements). Be wary of emotional headlines, anonymous sources without corroboration, and stories that perfectly confirm your existing beliefs. When in doubt, check FactCheck.org or Snopes."},
            {"q": "Why does Omni View cover sources from 'both sides'?", "a": "Because no single perspective has a monopoly on truth. Stories look different depending on which facts are emphasized, which sources are quoted, and what context is provided. By presenting perspectives from across the political spectrum, Omni View helps you see the full picture and form your own informed opinions — rather than having your views shaped by a single outlet's editorial choices."},
        ],
    },
    "fascinating_frontiers": {
        "name": "Fascinating Frontiers",
        "slug": "fascinating_frontiers",
        "display_order": 5,
        "description": "Daily space and astronomy news digest.",
        "show_page": "fascinating-frontiers.html",
        "summaries_page": "fascinating-frontiers-summaries.html",
        "json_path": "digests/fascinating_frontiers/summaries_space.json",
        "json_format": "wrapped",
        "rss_file": "fascinating_frontiers_podcast.rss",
        "podcast_image": "assets/covers/fascinating-frontiers.jpg",
        "x_account": "planetterrian",
        "brand_color": "#6B47FF",
        "brand_color_dark": "#4f46e5",
        "tagline": "Journey to the stars with today's discoveries.",
        "hero_tagline": "Journey to the stars with today's discoveries.",
        "schedule": "Daily",
        "episode_length": "~15 min",
        "about_text": "Daily space and astronomy news covering mission updates, cosmic discoveries, exoplanet breakthroughs, and rocket launches. From NASA and ESA to SpaceX and beyond.",
        "about_host": "Hosted by Patrick in Vancouver, bringing the cosmos to your ears.",
        "description_long": "Daily space and astronomy news covering mission updates, cosmic discoveries, exoplanet breakthroughs, and rocket launches. From NASA and ESA to SpaceX and beyond — the universe is more exciting than you think.",
        "related_show": "planetterrian",
        "related_reason": "If you enjoy Fascinating Frontiers, you might also like Planetterrian Daily — daily science, longevity, and health discoveries.",
        "apple_podcasts_url": "https://podcasts.apple.com/us/podcast/fascinating-frontiers/id1864803923",
        "spotify_url": "https://open.spotify.com/show/61S2fHlitcYUZZ0PmCkJYE",
        "theme_color": "#6B47FF",
        "meta_description": "Fascinating Frontiers — Daily space and astronomy news podcast. Mission updates, cosmic discoveries, and rocket launches.",
        "meta_keywords": "space podcast, astronomy news, NASA discoveries, space exploration, Fascinating Frontiers",
        "audience": "For space enthusiasts, amateur astronomers, students, and anyone who looks up and wonders what's out there.",
        "source_highlights": ["NASA", "ESA", "Space.com", "SpaceNews"],
        "resource_categories": [
            {
                "title": "Space Agencies",
                "resources": [
                    {"name": "NASA", "url": "https://www.nasa.gov", "desc": "Official NASA mission updates, images, and research — the world's largest space agency"},
                    {"name": "ESA", "url": "https://www.esa.int", "desc": "European Space Agency — Rosalind Franklin rover, Ariane rockets, and Earth observation"},
                    {"name": "JAXA", "url": "https://global.jaxa.jp", "desc": "Japan Aerospace Exploration Agency — Hayabusa asteroid missions and lunar exploration"},
                    {"name": "ISRO", "url": "https://www.isro.gov.in", "desc": "Indian Space Research Organisation — Chandrayaan lunar missions and Mars Orbiter"},
                    {"name": "CSA", "url": "https://www.asc-csa.gc.ca/eng/", "desc": "Canadian Space Agency — Canadarm, Chris Hadfield's agency, and Arctic Earth observation"},
                ],
            },
            {
                "title": "News & Journalism",
                "resources": [
                    {"name": "Space.com", "url": "https://www.space.com", "desc": "Space news, stargazing guides, and astronomy explainers — the go-to popular source"},
                    {"name": "SpaceNews", "url": "https://spacenews.com", "desc": "Industry-focused space journalism — policy, launches, satellites, and business"},
                    {"name": "Spaceflight Now", "url": "https://spaceflightnow.com", "desc": "Launch tracking, mission updates, and real-time coverage of rocket launches"},
                    {"name": "Universe Today", "url": "https://www.universetoday.com", "desc": "Astronomy and space exploration news written for enthusiasts by enthusiasts"},
                    {"name": "The Planetary Society", "url": "https://www.planetary.org", "desc": "Space exploration advocacy, citizen science, and Carl Sagan's legacy organization"},
                ],
            },
            {
                "title": "Citizen Science & Stargazing",
                "resources": [
                    {"name": "NASA APOD", "url": "https://apod.nasa.gov", "desc": "Astronomy Picture of the Day — a stunning new cosmic image with expert explanation every day"},
                    {"name": "Heavens-Above", "url": "https://www.heavens-above.com", "desc": "Track satellites, ISS passes, and planets for your location — essential for observers"},
                    {"name": "Zooniverse", "url": "https://www.zooniverse.org", "desc": "Citizen science projects — help classify galaxies, discover exoplanets, and hunt asteroids"},
                    {"name": "Globe at Night", "url": "https://www.globeatnight.org", "desc": "Citizen science program measuring light pollution — contribute from your backyard"},
                    {"name": "Sky & Telescope", "url": "https://skyandtelescope.org", "desc": "Observing guides, equipment reviews, and astronomical event calendars for amateur astronomers"},
                ],
            },
            {
                "title": "Telescopes & Missions",
                "resources": [
                    {"name": "Webb Telescope", "url": "https://webbtelescope.org", "desc": "James Webb Space Telescope — the most powerful space telescope ever built, images and science"},
                    {"name": "Hubble Site", "url": "https://hubblesite.org", "desc": "Hubble Space Telescope gallery, news, and 35+ years of iconic cosmic images"},
                    {"name": "NASA Mars Exploration", "url": "https://mars.nasa.gov", "desc": "Perseverance rover, Ingenuity helicopter, and the journey to send humans to Mars"},
                    {"name": "NASA Exoplanet Archive", "url": "https://exoplanetarchive.ipac.caltech.edu", "desc": "Database of 5,700+ confirmed exoplanets — search, filter, and explore alien worlds"},
                    {"name": "SpaceX", "url": "https://www.spacex.com", "desc": "Starship development, Falcon 9 launches, and the mission to make humanity multiplanetary"},
                ],
            },
            {
                "title": "Learning & Courses",
                "resources": [
                    {"name": "Crash Course Astronomy", "url": "https://www.youtube.com/playlist?list=PL8dPuuaLjXtPAJr1ysd5yGIyiSFuh0mIL", "desc": "46 free episodes covering the solar system to cosmology — fun, fast, and accurate"},
                    {"name": "Khan Academy Cosmology", "url": "https://www.khanacademy.org/science/cosmology-and-astronomy", "desc": "Free lessons on stars, galaxies, and the Big Bang — great for students"},
                    {"name": "AstroBites", "url": "https://astrobites.org", "desc": "Graduate students summarize the latest astrophysics papers in plain language — daily"},
                    {"name": "ESA Kids", "url": "https://www.esa.int/kids/en/home", "desc": "Space explained for young learners — games, activities, and mission guides from ESA"},
                ],
            },
        ],
        "tools": [
            {"name": "Stellarium", "url": "https://stellarium-web.org", "desc": "Free planetarium in your browser — see tonight's sky from any location on Earth", "badge": "Free"},
            {"name": "NASA Eyes", "url": "https://eyes.nasa.gov", "desc": "3D visualization of the solar system, Earth, and active NASA missions in real time", "badge": "Free"},
            {"name": "Heavens-Above", "url": "https://www.heavens-above.com", "desc": "Track the ISS, Starlink trains, and bright satellites passing over your city", "badge": "Free"},
            {"name": "SkySafari", "url": "https://skysafariastronomy.com", "desc": "Point your phone at the sky to identify stars, planets, and constellations instantly", "badge": "Freemium"},
            {"name": "SpaceX Launch Tracker", "url": "https://www.spacex.com/launches/", "desc": "Upcoming and past SpaceX launches — schedules, webcasts, and mission details", "badge": "Free"},
            {"name": "Spot The Station", "url": "https://spotthestation.nasa.gov", "desc": "NASA's official ISS sighting tool — get alerts when the station flies over your area", "badge": "Free"},
        ],
        "faq": [
            {"q": "What is an exoplanet?", "a": "An exoplanet is a planet that orbits a star outside our solar system. Over 5,700 exoplanets have been confirmed as of 2026, with thousands more candidates awaiting verification. They range from scorching hot Jupiters to potentially habitable rocky worlds. NASA's TESS and the James Webb Space Telescope are the primary tools for finding and studying them."},
            {"q": "How does the James Webb Space Telescope work?", "a": "JWST is an infrared space telescope with a 6.5-meter gold-coated mirror (compared to Hubble's 2.4m). It orbits the Sun at the L2 Lagrange point, 1.5 million km from Earth, where its sunshield keeps instruments at -233C. By observing in infrared, Webb can see through cosmic dust, study the atmospheres of exoplanets, and detect light from the earliest galaxies formed after the Big Bang."},
            {"q": "What is a light-year?", "a": "A light-year is the distance light travels in one year — about 9.46 trillion kilometers (5.88 trillion miles). It's used because space distances are so vast that kilometers become meaningless. For scale: the nearest star (Proxima Centauri) is 4.24 light-years away. The Milky Way galaxy is about 100,000 light-years across. The observable universe extends 46 billion light-years in every direction."},
            {"q": "What's the difference between NASA, ESA, and SpaceX?", "a": "NASA (US) and ESA (Europe) are government space agencies funded by taxpayers — they do science, exploration, and Earth observation. SpaceX is a private company founded by Elon Musk that builds rockets and spacecraft. SpaceX focuses on making space access cheaper (reusable Falcon 9, Starship), while NASA and ESA define scientific missions. They often work together — SpaceX launches NASA astronauts to the ISS."},
            {"q": "How can I see the ISS?", "a": "The International Space Station is the third brightest object in the night sky (after the Sun and Moon). It looks like a fast-moving bright star crossing the sky in 3-5 minutes. Use NASA's Spot The Station website or the Heavens-Above app to get exact times for your location. Best sightings happen just after sunset or before sunrise when the station catches sunlight against a dark sky."},
        ],
    },
    "planetterrian": {
        "name": "Planetterrian Daily",
        "slug": "planetterrian",
        "display_order": 2,
        "description": "Daily science, longevity, and health discoveries.",
        "show_page": "planetterrian.html",
        "summaries_page": "planetterrian-summaries.html",
        "json_path": "digests/planetterrian/summaries_planet.json",
        "json_format": "wrapped",
        "rss_file": "planetterrian_podcast.rss",
        "podcast_image": "assets/covers/planetterrian-daily.jpg",
        "x_account": "planetterrian",
        "brand_color": "#017A99",
        # Hero VML / gradient endpoint — must be DARKER than brand_color
        # so white text on the Outlook fallback (and the gradient's
        # darker stop) clears WCAG AA. The previous #35B5C4 was *lighter*
        # than the brand and white-on-it measured 2.45:1 in May 2026
        # newsletter audits. #005A75 measures 7.72:1.
        "brand_color_dark": "#005A75",
        "tagline": "Science, longevity, and the frontier of human health.",
        "hero_tagline": "Science, longevity, and the frontier of human health.",
        "schedule": "Daily",
        "episode_length": "~15 min",
        "about_text": "Daily discoveries in longevity science, genetics, biotech, CRISPR, neuroscience, and health research. If it could extend your healthspan or change medicine, we cover it.",
        "about_host": "Hosted by Patrick in Vancouver. A tribe of forward-thinking innovators.",
        "description_long": "Daily discoveries in longevity science, genetics, biotech, CRISPR, neuroscience, and health research. If it could extend your healthspan or change medicine, we cover it.",
        "related_show": "fascinating_frontiers",
        "related_reason": "If you enjoy Planetterrian Daily, you might also like Fascinating Frontiers — daily space and astronomy news.",
        "apple_podcasts_url": "https://podcasts.apple.com/us/podcast/planetterrian-daily/id1857782085",
        "spotify_url": "https://open.spotify.com/show/0GgrsEDFLaZfTOQkQm5DI2",
        "theme_color": "#017A99",
        "meta_description": "Planetterrian Daily — Science, longevity, and health discoveries. Genetics, biotech, CRISPR, and more.",
        "meta_keywords": "science podcast, longevity research, health discoveries, Planetterrian Daily, biotech news",
        "audience": "For the health-curious, longevity enthusiasts, biohackers, and anyone who wants tomorrow's medicine explained today.",
        "source_highlights": ["Nature", "Science", "Cell", "New Scientist"],
        "resource_categories": [
            {
                "title": "Journals & Research",
                "resources": [
                    {"name": "Nature", "url": "https://www.nature.com", "desc": "The world's premier multidisciplinary science journal — breakthrough research across all fields"},
                    {"name": "Science (AAAS)", "url": "https://www.science.org", "desc": "Peer-reviewed research and news from the American Association for the Advancement of Science"},
                    {"name": "Cell", "url": "https://www.cell.com", "desc": "Leading journal for molecular biology, genetics, and cell biology research"},
                    {"name": "PubMed", "url": "https://pubmed.ncbi.nlm.nih.gov", "desc": "Free database of 36M+ biomedical research papers — search any health or science topic"},
                    {"name": "Quanta Magazine", "url": "https://www.quantamagazine.org", "desc": "Accessible, beautifully written coverage of math, physics, and biology research"},
                ],
            },
            {
                "title": "Longevity Science",
                "resources": [
                    {"name": "Lifespan.io", "url": "https://www.lifespan.io", "desc": "Longevity research news, rejuvenation science tracker, and clinical trial database"},
                    {"name": "Longevity Technology", "url": "https://longevity.technology", "desc": "Industry news on longevity biotech, startups, and anti-aging interventions"},
                    {"name": "David Sinclair Lab", "url": "https://sinclair.hms.harvard.edu", "desc": "Harvard geneticist's lab — NAD+, sirtuins, and aging reversal research"},
                    {"name": "SENS Research Foundation", "url": "https://www.sens.org", "desc": "Aubrey de Grey's foundation funding damage-repair approaches to aging"},
                    {"name": "ClinicalTrials.gov", "url": "https://clinicaltrials.gov", "desc": "Database of 450,000+ clinical studies — search for longevity, anti-aging, and health trials"},
                ],
            },
            {
                "title": "Health & Nutrition",
                "resources": [
                    {"name": "Examine.com", "url": "https://examine.com", "desc": "Evidence-based supplement and nutrition research — no ads, no hype, just science"},
                    {"name": "Healthline", "url": "https://www.healthline.com", "desc": "Medical information reviewed by doctors — conditions, treatments, and wellness"},
                    {"name": "Nutritionfacts.org", "url": "https://nutritionfacts.org", "desc": "Dr. Michael Greger's free database of nutrition research — video summaries of studies"},
                    {"name": "Harvard Health", "url": "https://www.health.harvard.edu", "desc": "Health information from Harvard Medical School — trusted, peer-reviewed content"},
                    {"name": "Mayo Clinic", "url": "https://www.mayoclinic.org", "desc": "Patient-friendly health information from one of the world's top medical centers"},
                ],
            },
            {
                "title": "Biotech & CRISPR",
                "resources": [
                    {"name": "STAT News", "url": "https://www.statnews.com", "desc": "Health and medicine journalism — biotech, pharma, and life science industry coverage"},
                    {"name": "Genetic Engineering News", "url": "https://www.genengnews.com", "desc": "Biotech industry news — CRISPR, gene therapy, cell therapy, and drug development"},
                    {"name": "The CRISPR Journal", "url": "https://www.liebertpub.com/loi/crispr", "desc": "Peer-reviewed journal dedicated to CRISPR gene editing research and applications"},
                    {"name": "Broad Institute", "url": "https://www.broadinstitute.org", "desc": "MIT-Harvard genomics research institute — home of key CRISPR innovations"},
                ],
            },
            {
                "title": "Mental Health & Neuroscience",
                "resources": [
                    {"name": "Huberman Lab", "url": "https://www.hubermanlab.com", "desc": "Stanford neuroscientist Andrew Huberman's podcast and protocols for brain and body optimization"},
                    {"name": "BrainFacts.org", "url": "https://www.brainfacts.org", "desc": "Neuroscience education from the Society for Neuroscience — brain basics to cutting-edge research"},
                    {"name": "NIMH", "url": "https://www.nimh.nih.gov", "desc": "National Institute of Mental Health — research, statistics, and clinical trial information"},
                    {"name": "Neuroscience News", "url": "https://neurosciencenews.com", "desc": "Daily neuroscience research summaries — psychology, AI, and brain science"},
                ],
            },
        ],
        "tools": [
            {"name": "PubMed", "url": "https://pubmed.ncbi.nlm.nih.gov", "desc": "Search 36M+ biomedical papers — the essential tool for finding health and science research", "badge": "Free"},
            {"name": "Examine.com", "url": "https://examine.com", "desc": "Look up any supplement or nutrient — see what the research actually says, not marketing claims", "badge": "Free tier"},
            {"name": "Cronometer", "url": "https://cronometer.com", "desc": "Track nutrition, micronutrients, and macros with the most detailed food database available", "badge": "Free tier"},
            {"name": "Oura Ring", "url": "https://ouraring.com", "desc": "Sleep, recovery, and readiness tracking — used by longevity researchers for personal data", "badge": "Hardware"},
            {"name": "InsideTracker", "url": "https://www.insidetracker.com", "desc": "Blood biomarker analysis with personalized health recommendations based on your biology", "badge": "Paid"},
        ],
        "faq": [
            {"q": "What is healthspan vs lifespan?", "a": "Lifespan is how long you live. Healthspan is how long you live in good health — free from chronic disease and disability. Longevity researchers increasingly focus on healthspan because living to 100 matters less if the last 20 years are spent in poor health. The goal is to compress morbidity — keeping you healthy and active until very late in life."},
            {"q": "What is CRISPR?", "a": "CRISPR (Clustered Regularly Interspaced Short Palindromic Repeats) is a revolutionary gene-editing tool that allows scientists to precisely cut, delete, or modify DNA sequences. Think of it as molecular scissors with a GPS — you can target a specific gene and change it. It's being used to develop treatments for sickle cell disease, certain cancers, and inherited genetic conditions. The 2020 Nobel Prize in Chemistry was awarded for this technology."},
            {"q": "What are senolytics?", "a": "Senolytics are drugs that selectively destroy senescent cells — 'zombie cells' that have stopped dividing but refuse to die. These cells accumulate with age and secrete inflammatory signals that damage surrounding tissue, contributing to aging and age-related diseases. Senolytic drugs like dasatinib + quercetin and fisetin are being studied in clinical trials. Early results suggest they may improve physical function and reduce inflammation in older adults."},
            {"q": "What is NAD+ and why does it matter?", "a": "NAD+ (Nicotinamide Adenine Dinucleotide) is a coenzyme found in every cell that's essential for energy metabolism, DNA repair, and cellular signaling. NAD+ levels decline with age — by age 50, you may have half the NAD+ you had at 20. Researchers like David Sinclair believe boosting NAD+ (via precursors like NMN or NR) could slow aging. Clinical trials are underway, but results are still preliminary."},
            {"q": "What is a clinical trial?", "a": "A clinical trial is a research study that tests a medical treatment, drug, or intervention in human volunteers. Trials progress through phases: Phase 1 tests safety (small group), Phase 2 tests effectiveness (larger group), Phase 3 compares to existing treatments (thousands of participants), and Phase 4 monitors long-term effects after approval. You can search for trials at ClinicalTrials.gov — some actively recruit participants."},
        ],
    },
    "env_intel": {
        "name": "Environmental Intelligence",
        "slug": "env_intel",
        "display_order": 8,
        "description": "Daily environmental regulatory and compliance briefing.",
        "show_page": "env-intel.html",
        "summaries_page": "env-intel-summaries.html",
        "json_path": "digests/env_intel/summaries_env_intel.json",
        # env_intel's summaries JSON is in the network-standard wrapped
        # form ``{"podcast": ..., "summaries": [...]}``. This entry was
        # previously ``"array"`` — a mis-pin that made the show page's
        # JS path return an empty list and silently fall back to the
        # RSS-from-file path, which doesn't sort items by pubDate, so
        # the page showed ``Ep 2`` (the OLDEST item in the file) as
        # "Latest Episode" instead of the actual latest ``Ep 35``.
        # Operator caught (May 23 2026 screenshot). Every other show
        # in NETWORK_SHOWS already uses ``"wrapped"``.
        "json_format": "wrapped",
        "rss_file": "env_intel_podcast.rss",
        "podcast_image": "assets/covers/environmental-intelligence.jpg",
        "x_account": "teslashortstime",
        "brand_color": "#1B5E20",
        "brand_color_dark": "#0D3B0F",
        "tagline": "Environmental regulatory and compliance briefing.",
        "hero_tagline": "Environmental regulatory and compliance briefing.",
        "schedule": "Odd weekdays",
        "episode_length": "~10 min",
        "about_text": "Environmental regulatory, science, and compliance briefing for BC professionals. Covers contaminated sites, CEPA, emissions, carbon policy, PFAS, and remediation developments.",
        "about_host": "Hosted by Patrick in Vancouver.",
        "description_long": "Environmental regulatory, science, and compliance briefing for BC professionals. Covers contaminated sites, CEPA, emissions, carbon policy, PFAS, and remediation developments across Canada.",
        "related_show": "planetterrian",
        "related_reason": "If you enjoy Environmental Intelligence, you might also like Planetterrian Daily — science, longevity, and health research.",
        "apple_podcasts_url": None,  # Not yet on Apple Podcasts
        "spotify_url": None,  # Not yet on Spotify
        "theme_color": "#1B5E20",
        "meta_description": "Environmental Intelligence — Daily environmental regulatory and compliance briefing for BC professionals.",
        "meta_keywords": "environmental intelligence, regulatory compliance, environmental briefings, Canadian environment",
        "audience": "For Canadian environmental professionals — contaminated sites consultants, regulators, lawyers, and lab scientists.",
        "source_highlights": ["Canada Gazette", "ECCC", "BC Ministry of Environment", "The Narwhal"],
        "resource_categories": [
            {
                "title": "Federal Regulation",
                "resources": [
                    {"name": "Canada Gazette", "url": "https://www.gazette.gc.ca", "desc": "Official source for proposed and enacted federal regulations — Part I (proposals) and Part II (final)"},
                    {"name": "ECCC", "url": "https://www.canada.ca/en/environment-climate-change.html", "desc": "Environment and Climate Change Canada — federal environmental policy, enforcement, and data"},
                    {"name": "CEPA Registry", "url": "https://www.canada.ca/en/environment-climate-change/services/canadian-environmental-protection-act-registry.html", "desc": "Canadian Environmental Protection Act registry — substance assessments and regulations"},
                    {"name": "Impact Assessment Agency", "url": "https://www.canada.ca/en/impact-assessment-agency.html", "desc": "Federal impact assessments for major projects — pipelines, mines, and infrastructure"},
                    {"name": "CCME", "url": "https://ccme.ca", "desc": "Canadian Council of Ministers of the Environment — national guidelines, standards, and water quality objectives"},
                ],
            },
            {
                "title": "BC & Provincial",
                "resources": [
                    {"name": "BC Site Remediation", "url": "https://www2.gov.bc.ca/gov/content/environment/air-land-water/site-remediation", "desc": "BC contaminated sites registry, CSR protocols, technical guidance, and site profiles"},
                    {"name": "BC ENV", "url": "https://www2.gov.bc.ca/gov/content/environment", "desc": "BC Ministry of Environment — permits, compliance, air/water quality, and wildlife"},
                    {"name": "BC Environmental Assessment Office", "url": "https://www.projects.eao.gov.bc.ca", "desc": "Track BC environmental assessments for major projects — mines, LNG, pipelines"},
                    {"name": "Alberta Energy Regulator", "url": "https://www.aer.ca", "desc": "Alberta's energy and environmental regulator — oil sands, pipelines, and reclamation"},
                    {"name": "Ontario MOE", "url": "https://www.ontario.ca/page/ministry-environment-conservation-parks", "desc": "Ontario environmental regulation — brownfields, air quality, and water resources"},
                ],
            },
            {
                "title": "Professional Associations",
                "resources": [
                    {"name": "CSAP (BC)", "url": "https://csapsociety.bc.ca", "desc": "Contaminated Sites Approved Professionals Society — BC's roster of qualified environmental professionals"},
                    {"name": "ECO Canada", "url": "https://eco.ca", "desc": "Environmental careers, training, and professional development across Canada"},
                    {"name": "APEGA", "url": "https://www.apega.ca", "desc": "Association of Professional Engineers and Geoscientists of Alberta — licensing and practice"},
                    {"name": "EGBC", "url": "https://www.egbc.ca", "desc": "Engineers and Geoscientists BC — professional regulation for BC environmental practitioners"},
                ],
            },
            {
                "title": "Contaminated Sites & Remediation",
                "resources": [
                    {"name": "Federal Contaminated Sites Inventory", "url": "https://www.tbs-sct.canada.ca/fcsi-rscf/home-accueil-eng.aspx", "desc": "Database of 24,000+ federal contaminated sites across Canada — searchable by province"},
                    {"name": "ITRC", "url": "https://www.itrcweb.org", "desc": "Interstate Technology and Regulatory Council — technical guidance on PFAS, vapour intrusion, and remediation"},
                    {"name": "CLU-IN", "url": "https://clu-in.org", "desc": "US EPA's contaminated site cleanup information — technologies, training, and case studies"},
                    {"name": "ASTM Environmental Standards", "url": "https://www.astm.org/products-services/standards-and-publications/standards/environmental-standards.html", "desc": "Phase I/II ESA standards (E1527, E1903) and environmental assessment protocols"},
                    {"name": "RemTech Symposium", "url": "https://www.esaa.org/remtech/", "desc": "Canada's premier remediation technology conference — ESAA annual event in Banff"},
                ],
            },
            {
                "title": "Environmental Science & Journalism",
                "resources": [
                    {"name": "The Narwhal", "url": "https://thenarwhal.ca", "desc": "Independent Canadian environmental investigative journalism — in-depth, evidence-based"},
                    {"name": "Ecojustice", "url": "https://ecojustice.ca", "desc": "Canada's leading environmental law charity — legal actions and policy advocacy"},
                    {"name": "Nature Climate Change", "url": "https://www.nature.com/nclimate/", "desc": "Peer-reviewed journal on climate change science, impacts, and policy"},
                    {"name": "Inside Climate News", "url": "https://insideclimatenews.org", "desc": "Pulitzer Prize-winning climate and energy journalism — US and global coverage"},
                ],
            },
        ],
        "tools": [
            {"name": "BC CSR Database", "url": "https://www2.gov.bc.ca/gov/content/environment/air-land-water/site-remediation/contaminated-sites", "desc": "Search BC's contaminated sites registry — site profiles, risk classifications, and remediation status", "badge": "Free"},
            {"name": "CCME Guidelines", "url": "https://ccme.ca/en/current-activities/canadian-environmental-quality-guidelines", "desc": "Canadian soil, water, and sediment quality guidelines — the foundation for site assessments", "badge": "Free"},
            {"name": "ERIS", "url": "https://www.eris.com", "desc": "Environmental risk information services — Phase I ESA database searches for Canadian and US sites", "badge": "Paid"},
            {"name": "Canada Gazette Alerts", "url": "https://www.gazette.gc.ca/cg-gc/subscribe-abonner-eng.html", "desc": "Subscribe to alerts for new federal environmental regulations and amendments", "badge": "Free"},
            {"name": "ArcGIS Environmental", "url": "https://www.esri.com/en-us/industries/environment/overview", "desc": "GIS mapping for environmental data — contaminated sites, watersheds, and monitoring wells", "badge": "Paid"},
        ],
        "faq": [
            {"q": "What is CEPA?", "a": "The Canadian Environmental Protection Act (CEPA 1999) is Canada's primary federal environmental law. It governs the assessment and management of toxic substances, pollution prevention, and environmental emergencies. CEPA gives the federal government authority to regulate chemicals, fuels, and wastes that pose risks to human health or the environment. It was significantly updated in 2023 (Bill S-5) to recognize the right to a healthy environment."},
            {"q": "What is a contaminated site?", "a": "A contaminated site is land or water where hazardous substances exceed regulatory standards and may pose risks to human health or the environment. Common contaminants include petroleum hydrocarbons (from gas stations), heavy metals (from industrial operations), chlorinated solvents (from dry cleaners), and PFAS (from firefighting foam). In BC, the Contaminated Sites Regulation (CSR) defines standards and the process for investigation, risk assessment, and remediation."},
            {"q": "What are PFAS?", "a": "PFAS (Per- and Polyfluoroalkyl Substances) are a group of 12,000+ synthetic chemicals known as 'forever chemicals' because they don't break down in the environment. Used since the 1950s in non-stick coatings, food packaging, firefighting foam, and waterproof clothing, PFAS contaminate groundwater, soil, and drinking water worldwide. Health concerns include cancer, thyroid disease, and immune system effects. Canada is developing federal PFAS regulations, and remediation is extremely challenging and costly."},
            {"q": "What is the CSR (Contaminated Sites Regulation)?", "a": "BC's Contaminated Sites Regulation sets numerical standards for soil, groundwater, vapour, and sediment quality. It defines when a site is 'contaminated' (exceeds standards) and the process for investigation, risk assessment, and remediation. Key concepts include: site profiles (disclosure triggers), preliminary and detailed site investigations, risk-based standards vs. generic standards, and certificates of compliance issued upon successful remediation."},
            {"q": "What does 'remediation' mean?", "a": "Remediation is the process of cleaning up contaminated land or groundwater to make it safe for its intended use. Methods include: excavation and disposal (dig-and-dump), in-situ treatment (treating contamination in place using bioremediation, chemical oxidation, or thermal treatment), pump-and-treat (extracting and treating groundwater), and risk management (containing contamination with barriers or institutional controls). The approach depends on contaminant type, site geology, and intended land use."},
        ],
    },
    "models_agents": {
        "name": "Models & Agents",
        "slug": "models_agents",
        "display_order": 1,
        "description": "Daily AI briefing on models, agent frameworks, and practical AI.",
        "show_page": "models-agents.html",
        "summaries_page": "models-agents-summaries.html",
        "json_path": "digests/models_agents/summaries_models_agents.json",
        "json_format": "wrapped",
        "rss_file": "models_agents_podcast.rss",
        "podcast_image": "assets/covers/models-agents.jpg",
        "x_account": None,
        "brand_color": "#7C3AED",
        "brand_color_dark": "#6D28D9",
        "tagline": "Daily AI models, agents, and practical developments.",
        "hero_tagline": "Daily AI models, agents, and practical developments.",
        "schedule": "Daily",
        "episode_length": "~15 min",
        "about_text": "Daily AI briefing covering new model releases, agent frameworks, and practical developments. From GPT and Claude to OpenClaw and Agent Zero — stay on top of the most exciting developments of our generation.",
        "about_host": "Hosted by Patrick in Vancouver.",
        "description_long": "Daily AI briefing covering new model releases, agent frameworks, and practical developments. From GPT and Claude to open-source projects — stay on top of the most exciting tech developments of our generation.",
        "related_show": "models_agents_beginners",
        "related_reason": "If you enjoy Models & Agents, you might also like Models & Agents for Beginners — the same AI news explained simply for newcomers.",
        "apple_podcasts_url": "https://podcasts.apple.com/us/podcast/models-agents/id1885231539",
        "spotify_url": "https://open.spotify.com/show/28dfMGTVsgQxPuUs7YoJYD",
        "theme_color": "#7C3AED",
        "meta_description": "Models & Agents — Daily AI briefing on models, agent frameworks, and practical AI developments.",
        "meta_keywords": "AI models, agent frameworks, LLM news, AI briefings, Models and Agents",
        "audience": "For developers building with AI, professionals adopting AI tools, and anyone who wants to stay ahead of the most transformative technology of our generation.",
        "source_highlights": ["OpenAI", "Anthropic", "Hugging Face", "arXiv"],
        "resource_categories": [
            {
                "title": "AI Labs & Research",
                "resources": [
                    {"name": "OpenAI", "url": "https://openai.com/research", "desc": "GPT, DALL-E, and Sora — research and blog posts from the makers of ChatGPT"},
                    {"name": "Anthropic", "url": "https://www.anthropic.com/research", "desc": "Claude model family — constitutional AI, safety research, and responsible scaling"},
                    {"name": "Google DeepMind", "url": "https://deepmind.google/research/", "desc": "Gemini, AlphaFold, and fundamental AI research — one of the world's top AI labs"},
                    {"name": "Meta AI (FAIR)", "url": "https://ai.meta.com/research/", "desc": "Llama open-source models, computer vision, and fundamental research"},
                    {"name": "Mistral AI", "url": "https://mistral.ai", "desc": "European AI lab building efficient open-weight models — Mixtral and Mistral Large"},
                    {"name": "arXiv AI", "url": "https://arxiv.org/list/cs.AI/recent", "desc": "Latest AI research preprints — papers drop here before journal publication"},
                ],
            },
            {
                "title": "Developer Tools & Frameworks",
                "resources": [
                    {"name": "Hugging Face", "url": "https://huggingface.co", "desc": "The GitHub of ML — 500K+ models, datasets, and Spaces demos. Essential for any AI developer"},
                    {"name": "LangChain", "url": "https://www.langchain.com", "desc": "Framework for building LLM-powered applications — chains, agents, and retrieval pipelines"},
                    {"name": "LlamaIndex", "url": "https://www.llamaindex.ai", "desc": "Data framework for LLM apps — connect your data to language models with RAG pipelines"},
                    {"name": "Ollama", "url": "https://ollama.com", "desc": "Run open-source LLMs locally — Llama, Mistral, Phi, and more on your own hardware"},
                    {"name": "Vercel AI SDK", "url": "https://sdk.vercel.ai", "desc": "TypeScript toolkit for building AI-powered web applications with streaming UI"},
                    {"name": "Weights & Biases", "url": "https://wandb.ai", "desc": "ML experiment tracking, model versioning, and dataset management for AI teams"},
                ],
            },
            {
                "title": "Benchmarks & Leaderboards",
                "resources": [
                    {"name": "LM Arena (Chatbot Arena)", "url": "https://lmarena.ai", "desc": "Crowdsourced LLM rankings — users vote on which model gives better responses"},
                    {"name": "Open LLM Leaderboard", "url": "https://huggingface.co/spaces/HuggingFaceH4/open_llm_leaderboard", "desc": "Hugging Face's benchmark for open-source models — MMLU, ARC, HellaSwag scores"},
                    {"name": "Papers With Code", "url": "https://paperswithcode.com", "desc": "ML papers with code implementations and state-of-the-art benchmarks across tasks"},
                    {"name": "Artificial Analysis", "url": "https://artificialanalysis.ai", "desc": "Compare LLM providers on speed, cost, and quality — essential for API selection"},
                ],
            },
            {
                "title": "Newsletters & Analysis",
                "resources": [
                    {"name": "Latent Space", "url": "https://www.latent.space", "desc": "AI engineering podcast and newsletter — deep dives with builders and researchers"},
                    {"name": "The Decoder", "url": "https://the-decoder.com", "desc": "Daily AI news focused on practical developments, model releases, and tools"},
                    {"name": "Import AI", "url": "https://importai.substack.com", "desc": "Jack Clark's weekly AI newsletter — policy, research, and industry analysis"},
                    {"name": "The Batch (deeplearning.ai)", "url": "https://www.deeplearning.ai/the-batch/", "desc": "Andrew Ng's weekly AI newsletter — news, insights, and research highlights"},
                    {"name": "Simon Willison's Weblog", "url": "https://simonwillison.net", "desc": "Prolific AI practitioner's blog — LLM tools, prompt engineering, and practical AI"},
                ],
            },
            {
                "title": "Open-Source Ecosystem",
                "resources": [
                    {"name": "Ollama", "url": "https://ollama.com", "desc": "Run Llama 3, Mistral, Phi, and other open models locally with one command"},
                    {"name": "LM Studio", "url": "https://lmstudio.ai", "desc": "Desktop app for running local LLMs — GUI for model discovery, download, and chat"},
                    {"name": "vLLM", "url": "https://github.com/vllm-project/vllm", "desc": "High-throughput LLM serving engine — the standard for production model deployment"},
                    {"name": "llama.cpp", "url": "https://github.com/ggerganov/llama.cpp", "desc": "Run LLMs on CPU/GPU with minimal resources — the engine behind most local AI apps"},
                    {"name": "Open WebUI", "url": "https://github.com/open-webui/open-webui", "desc": "Self-hosted ChatGPT-like interface for local models — works with Ollama out of the box"},
                ],
            },
        ],
        "tools": [
            {"name": "Claude", "url": "https://claude.ai", "desc": "Anthropic's AI assistant — strong at reasoning, coding, and long-context analysis", "badge": "Free tier"},
            {"name": "ChatGPT", "url": "https://chat.openai.com", "desc": "OpenAI's conversational AI — GPT-4o with vision, code, and browsing capabilities", "badge": "Free tier"},
            {"name": "Cursor", "url": "https://cursor.com", "desc": "AI-first code editor — autocomplete, chat, and codebase-aware assistance built on LLMs", "badge": "Free tier"},
            {"name": "Hugging Face", "url": "https://huggingface.co", "desc": "Try 500K+ models in your browser — text, image, audio, and multimodal demos", "badge": "Free"},
            {"name": "Ollama", "url": "https://ollama.com", "desc": "Run open-source LLMs locally — one command to download and chat with Llama, Mistral, Phi", "badge": "Free"},
            {"name": "Perplexity", "url": "https://www.perplexity.ai", "desc": "AI-powered search engine — asks follow-up questions and cites sources for every answer", "badge": "Free tier"},
        ],
        "faq": [
            {"q": "What is an LLM?", "a": "A Large Language Model (LLM) is an AI system trained on vast amounts of text data to understand and generate human language. Models like GPT-4, Claude, Gemini, and Llama are LLMs. They work by predicting the most likely next token (word piece) in a sequence, but this simple mechanism produces remarkably capable systems that can write code, analyze documents, reason through problems, and hold conversations."},
            {"q": "What is an AI agent?", "a": "An AI agent is a system that uses an LLM as its 'brain' to autonomously plan and execute multi-step tasks. Unlike a simple chatbot that responds to one message at a time, an agent can break down complex goals, use tools (web search, code execution, APIs), observe results, and iterate. Examples include coding agents (Cursor, Claude Code), research agents (Perplexity), and browser agents that navigate websites on your behalf."},
            {"q": "What is RAG?", "a": "Retrieval-Augmented Generation (RAG) is a technique that gives LLMs access to external knowledge by retrieving relevant documents before generating a response. Instead of relying solely on training data, a RAG system searches a database (using vector embeddings), finds relevant passages, and includes them in the LLM's context. This reduces hallucinations and lets you build AI that can answer questions about your own documents, codebase, or data."},
            {"q": "What is fine-tuning?", "a": "Fine-tuning is the process of further training a pre-trained LLM on a specific dataset to specialize it for a particular task or domain. For example, you might fine-tune Llama on medical literature to create a healthcare-specific model. It's more expensive than RAG but can teach the model new behaviors, styles, or domain expertise that prompt engineering alone can't achieve. Most developers start with RAG and only fine-tune when necessary."},
            {"q": "What is MCP (Model Context Protocol)?", "a": "MCP is an open protocol (created by Anthropic) that standardizes how AI models connect to external data sources and tools. Think of it as a USB-C port for AI — instead of building custom integrations for every tool, MCP provides a universal interface. An MCP server can expose databases, APIs, file systems, or any tool, and any MCP-compatible AI client can use them. It's rapidly becoming the standard for agent tool connectivity."},
        ],
    },
    "models_agents_beginners": {
        "name": "Models & Agents for Beginners",
        "slug": "models_agents_beginners",
        "display_order": 4,
        "description": "Daily AI podcast for beginners and teens — AI explained simply.",
        "show_page": "models-agents-beginners.html",
        "summaries_page": "models-agents-beginners-summaries.html",
        "json_path": "digests/models_agents_beginners/summaries_models_agents_beginners.json",
        "json_format": "wrapped",
        "rss_file": "models_agents_beginners_podcast.rss",
        "podcast_image": "assets/covers/models-agents-beginners.jpg",
        "x_account": None,
        # MAB brand: orange-700 (#C2410C, 5.18:1 on white). Picked May
        # 2026 to differentiate from Unintended Consequences (which
        # uses the deep amber #B45309) — earlier MAB bump landed on
        # the same #B45309 by coincidence and the two show pills were
        # visually identical across the network grid.
        "brand_color": "#C2410C",
        # Hero VML / gradient endpoint — orange-800 (7.31:1 on white).
        # Must be DARKER than brand_color so white text on the Outlook
        # fallback clears WCAG AA.
        "brand_color_dark": "#9A3412",
        "tagline": "AI explained simply — for beginners and teens.",
        "hero_tagline": "AI explained simply — for beginners and teens.",
        "schedule": "Daily",
        "episode_length": "~10 min",
        "about_text": "A daily AI podcast for beginners and teens. Learn about AI models, agents, and the tools shaping our future — explained simply, with hands-on experiments you can try today. Every expert started as a beginner.",
        "about_host": "Hosted by Patrick in Vancouver.",
        "description_long": "A daily AI podcast for beginners and teens — learn about models, agents, and the AI revolution in plain language. We explain the jargon, encourage experimentation, and help you understand the most exciting technology of our generation.",
        "related_show": "models_agents",
        "related_reason": "If you enjoy Models & Agents for Beginners and want to go deeper, check out Models & Agents — the full daily AI briefing for developers and professionals.",
        "apple_podcasts_url": "https://podcasts.apple.com/us/podcast/models-agents-for-beginners/id1885231582",
        "spotify_url": "https://open.spotify.com/show/7vRUrQAJWzOB729A9aVDd5",
        "theme_color": "#C2410C",
        "meta_description": "Models & Agents for Beginners — Daily AI podcast for beginners and teens. AI models, agents, and tools explained simply.",
        "meta_keywords": "AI for beginners, AI podcast teens, learn AI, beginner AI, Models and Agents for Beginners",
        "audience": "For students, teens, curious parents, career changers, and anyone new to AI who wants to understand what's happening without the jargon.",
        "source_highlights": ["OpenAI", "Google AI", "Hugging Face", "TechCrunch AI"],
        "resource_categories": [
            {
                "title": "Start Here — Free Courses",
                "resources": [
                    {"name": "Google AI Essentials", "url": "https://grow.google/ai-essentials/", "desc": "Free introductory AI course from Google — no experience needed, earn a certificate"},
                    {"name": "Elements of AI", "url": "https://www.elementsofai.com", "desc": "Free online course from University of Helsinki — understand AI concepts without coding"},
                    {"name": "Khan Academy AI", "url": "https://www.khanacademy.org/computing/ai-for-everyone", "desc": "AI for Everyone — free, self-paced lessons from Khan Academy"},
                    {"name": "Crash Course AI", "url": "https://www.youtube.com/playlist?list=PL8dPuuaLjXtO65LeD2p4_Sb5XQ51par_b", "desc": "20 fun video episodes explaining AI concepts — great for visual learners"},
                    {"name": "AI for Everyone (Coursera)", "url": "https://www.coursera.org/learn/ai-for-everyone", "desc": "Andrew Ng's non-technical AI course — understand what AI can and can't do"},
                ],
            },
            {
                "title": "Try AI Right Now",
                "resources": [
                    {"name": "ChatGPT", "url": "https://chat.openai.com", "desc": "The most popular AI chatbot — ask questions, write stories, get homework help, or learn to code"},
                    {"name": "Claude", "url": "https://claude.ai", "desc": "Anthropic's AI assistant — excellent at explaining concepts, writing, and careful reasoning"},
                    {"name": "Google Gemini", "url": "https://gemini.google.com", "desc": "Google's AI — integrated with Search, can analyze images, and create content"},
                    {"name": "Microsoft Copilot", "url": "https://copilot.microsoft.com", "desc": "Free AI assistant from Microsoft — chat, create images, and get help with tasks"},
                    {"name": "Hugging Face Spaces", "url": "https://huggingface.co/spaces", "desc": "Try thousands of AI demos in your browser — image generation, translation, and more"},
                ],
            },
            {
                "title": "Hands-On Projects",
                "resources": [
                    {"name": "Machine Learning for Kids", "url": "https://machinelearningforkids.co.uk", "desc": "Build AI projects with Scratch — teach a computer to recognize images, text, and sounds"},
                    {"name": "Teachable Machine", "url": "https://teachablemachine.withgoogle.com", "desc": "Google's tool to train your own AI model in the browser — no code needed, instant results"},
                    {"name": "AI Experiments with Google", "url": "https://experiments.withgoogle.com/collection/ai", "desc": "Interactive AI demos — draw with AI, make music, play games, and explore neural networks"},
                    {"name": "Runway ML", "url": "https://runwayml.com", "desc": "Create AI-generated videos, images, and effects — the creative playground for AI art"},
                ],
            },
            {
                "title": "YouTube Channels & Creators",
                "resources": [
                    {"name": "3Blue1Brown", "url": "https://www.youtube.com/@3blue1brown", "desc": "Beautiful math visualizations that explain neural networks and machine learning intuitively"},
                    {"name": "Two Minute Papers", "url": "https://www.youtube.com/@TwoMinutePapers", "desc": "Quick, exciting summaries of the latest AI research — 'What a time to be alive!'"},
                    {"name": "Fireship", "url": "https://www.youtube.com/@Fireship", "desc": "Fast-paced tech explainers — AI news in 100 seconds, coding tutorials, and developer culture"},
                    {"name": "Matt Wolfe", "url": "https://www.youtube.com/@maboroshi", "desc": "Weekly AI tool roundups, tutorials, and news — perfect for staying current as a beginner"},
                ],
            },
            {
                "title": "Books & Reading",
                "resources": [
                    {"name": "Life 3.0 (Max Tegmark)", "url": "https://www.goodreads.com/book/show/34272565-life-3-0", "desc": "Accessible exploration of how AI will transform society — great for teens and adults"},
                    {"name": "Hello World (Hannah Fry)", "url": "https://www.goodreads.com/book/show/38212157-hello-world", "desc": "How algorithms are changing our lives — fun, readable, and thought-provoking"},
                    {"name": "AI 2041 (Kai-Fu Lee)", "url": "https://www.goodreads.com/book/show/56377201-ai-2041", "desc": "Ten short stories imagining AI's impact 15 years from now — science fiction meets real science"},
                    {"name": "You Look Like a Thing and I Love You", "url": "https://www.goodreads.com/book/show/44286534", "desc": "Hilarious, illustrated guide to how AI works (and fails) — by AI researcher Janelle Shane"},
                ],
            },
        ],
        "tools": [
            {"name": "ChatGPT", "url": "https://chat.openai.com", "desc": "Start here — ask anything, get homework help, write stories, or learn to code with AI", "badge": "Free"},
            {"name": "Claude", "url": "https://claude.ai", "desc": "Great for learning — ask it to explain any topic like you're a beginner. Patient and thorough", "badge": "Free"},
            {"name": "Google Gemini", "url": "https://gemini.google.com", "desc": "Google's AI — analyze images, get study help, and explore topics with web search built in", "badge": "Free"},
            {"name": "Teachable Machine", "url": "https://teachablemachine.withgoogle.com", "desc": "Train your own AI in minutes — teach it to recognize your face, gestures, or sounds. No code!", "badge": "Free"},
            {"name": "Canva Magic Studio", "url": "https://www.canva.com/ai-image-generator/", "desc": "Generate images, presentations, and designs with AI — great for school projects", "badge": "Free tier"},
        ],
        "faq": [
            {"q": "What is AI?", "a": "Artificial Intelligence (AI) is technology that enables computers to perform tasks that normally require human intelligence — like understanding language, recognizing images, making decisions, and learning from experience. Modern AI systems learn from huge amounts of data rather than following explicit rules. When you use ChatGPT, Google Translate, or Instagram filters, you're using AI."},
            {"q": "What is a 'model'?", "a": "An AI model is the trained 'brain' of an AI system. It's created by feeding a computer program enormous amounts of data and letting it find patterns. For example, a language model like GPT or Claude was trained on billions of pages of text, so it learned how language works. The word 'model' just means 'a simplified representation of something' — an AI model is a simplified representation of human knowledge and reasoning."},
            {"q": "Is AI dangerous?", "a": "Like any powerful technology, AI has risks and benefits. Current AI can spread misinformation, create deepfakes, and be biased against certain groups. Long-term, researchers debate whether very advanced AI could be hard to control. But AI also helps doctors diagnose diseases, scientists discover new medicines, and students learn faster. The key is developing AI responsibly — with safety research, regulation, and public awareness. Understanding AI helps you use it wisely."},
            {"q": "Can AI replace my job?", "a": "AI is more likely to change jobs than eliminate them entirely. It's very good at repetitive, pattern-based tasks (data entry, basic writing, image sorting) but struggles with creativity, empathy, physical dexterity, and complex judgment. Most experts predict AI will become a powerful tool that makes workers more productive — like how calculators didn't replace mathematicians but changed what they focus on. The best strategy is learning to work WITH AI, not compete against it."},
            {"q": "What's the difference between ChatGPT and Google Gemini?", "a": "Both are AI chatbots powered by large language models, but they're made by different companies with different strengths. ChatGPT (by OpenAI) was the first widely popular AI chatbot and is known for creative writing and coding. Gemini (by Google) is integrated with Google Search and services, so it's good at finding current information. Claude (by Anthropic) is known for careful reasoning and safety. Try all three — they're all free to use — and see which you prefer!"},
        ],
    },
    "finansy_prosto": {
        "name": "Финансы Просто",
        "slug": "finansy_prosto",
        # Buttondown rejects non-ASCII tags; keep the display name in
        # Cyrillic but tag in ASCII to match shows/finansy_prosto.yaml.
        "newsletter_tag": "Finansy Prosto",
        "display_order": 9,
        "description": "Ежедневный подкаст о финансах на русском языке для женщин в Канаде.",
        "show_page": "ru/finansy-prosto.html",
        "summaries_page": "ru/finansy-prosto-summaries.html",
        "json_path": "digests/finansy_prosto/summaries_finansy_prosto.json",
        "json_format": "wrapped",
        "rss_file": "finansy_prosto_podcast.rss",
        "podcast_image": "assets/covers/finansy-prosto.jpg",
        "x_account": None,
        "brand_color": "#BE185D",
        "brand_color_dark": "#DB2777",
        "tagline": "Finances Made Simple.",
        "hero_tagline": "Финансы — просто и понятно.",
        "schedule": "Even days",
        "episode_length": "~12 min",
        "about_text": "Ежедневный подкаст о финансах на русском языке для женщин в Канаде. Ведущая Оля объясняет инвестиции, сбережения, бюджет и финансовую грамотность — просто и понятно.",
        "about_host": "Ведущая — Оля из Ванкувера. Каждый выпуск — практические советы, новости и ресурсы для финансовой независимости.",
        "description_long": "Ежедневный подкаст о финансах на русском языке для женщин в Канаде — инвестиции, сбережения, бюджет и финансовая грамотность просто и понятно.",
        "related_show": "privet_russian",
        "related_reason": "If you enjoy Финансы Просто, you might also like Привет, Русский! — learn Russian through fun, themed episodes.",
        "apple_podcasts_url": "https://podcasts.apple.com/us/podcast/%D1%84%D0%B8%D0%BD%D0%B0%D0%BD%D1%81%D1%8B-%D0%BF%D1%80%D0%BE%D1%81%D1%82%D0%BE/id1885235226",
        "spotify_url": "https://open.spotify.com/show/35jCJTVe3ITGah3ryeKzzM",
        "theme_color": "#BE185D",
        "meta_description": "Финансы Просто — ежедневный подкаст о финансах на русском языке для женщин в Канаде. Инвестиции, сбережения, бюджет.",
        "meta_keywords": "финансы, подкаст, русский, Канада, инвестиции, сбережения, бюджет, финансовая грамотность",
        "audience": "Для русскоговорящих женщин в Канаде, которые хотят разобраться в финансах — от TFSA до ипотеки.",
        "source_highlights": ["MoneySense", "Financial Post", "FinTolk", "Tinkoff Journal"],
        "resource_categories": [
            {
                "title": "Канадские финансы",
                "resources": [
                    {"name": "MoneySense", "url": "https://www.moneysense.ca", "desc": "Канадский портал о финансах — инвестиции, пенсия, ипотека и налоги"},
                    {"name": "Financial Post", "url": "https://financialpost.com", "desc": "Финансовые новости Канады — рынки, экономика и личные финансы"},
                    {"name": "Globe and Mail Investing", "url": "https://www.theglobeandmail.com/investing/", "desc": "Инвестиционные новости и аналитика от ведущей канадской газеты"},
                    {"name": "Canadian Couch Potato", "url": "https://canadiancouchpotato.com", "desc": "Пассивное инвестирование для канадцев — модельные портфели из ETF"},
                    {"name": "Young and Thrifty", "url": "https://youngandthrifty.ca", "desc": "Финансовые советы для молодых канадцев — бюджет, сбережения, инвестиции"},
                ],
            },
            {
                "title": "Инвестиционные платформы",
                "resources": [
                    {"name": "Wealthsimple", "url": "https://www.wealthsimple.com", "desc": "Инвестиционная платформа для канадцев — TFSA, RRSP, торговля без комиссии"},
                    {"name": "Questrade", "url": "https://www.questrade.com", "desc": "Канадский онлайн-брокер — ETF без комиссии, TFSA, RRSP, RESP"},
                    {"name": "Interactive Brokers", "url": "https://www.interactivebrokers.ca", "desc": "Профессиональная торговая платформа — низкие комиссии, доступ к мировым рынкам"},
                    {"name": "EQ Bank", "url": "https://www.eqbank.ca", "desc": "Высокие ставки по сберегательным счетам и GIC — без ежемесячных комиссий"},
                ],
            },
            {
                "title": "Калькуляторы и инструменты",
                "resources": [
                    {"name": "RateHub", "url": "https://www.ratehub.ca", "desc": "Сравнение ипотечных ставок, кредитных карт и сберегательных счетов в Канаде"},
                    {"name": "Borrowell", "url": "https://www.borrowell.com", "desc": "Бесплатная проверка кредитного рейтинга и персональные финансовые рекомендации"},
                    {"name": "Wealthsimple Tax", "url": "https://www.wealthsimple.com/en-ca/tax", "desc": "Бесплатная подача налоговой декларации онлайн — простой и понятный интерфейс"},
                    {"name": "CRA My Account", "url": "https://www.canada.ca/en/revenue-agency/services/e-services/digital-services-individuals/account-individuals.html", "desc": "Личный кабинет в налоговой — проверка возвратов, лимитов TFSA/RRSP"},
                ],
            },
            {
                "title": "Государственные ресурсы",
                "resources": [
                    {"name": "Canada.ca Benefits", "url": "https://www.canada.ca/en/services/benefits.html", "desc": "Государственные пособия — CCB, EI, CPP, OAS, кредиты на детей и налоговые льготы"},
                    {"name": "Financial Consumer Agency", "url": "https://www.canada.ca/en/financial-consumer-agency.html", "desc": "Защита прав потребителей финансовых услуг — жалобы, права и образование"},
                    {"name": "BC Housing", "url": "https://www.bchousing.org", "desc": "Программы доступного жилья в BC — субсидии, аренда, первый дом"},
                    {"name": "Settlement.org", "url": "https://settlement.org/ontario/employment/financial-information/", "desc": "Финансовая информация для иммигрантов — банки, налоги и кредит в Канаде"},
                ],
            },
            {
                "title": "Финансовое образование",
                "resources": [
                    {"name": "Tinkoff Journal", "url": "https://journal.tinkoff.ru", "desc": "Российский портал о финансовой грамотности — инвестиции, налоги, экономика (на русском)"},
                    {"name": "FinTolk", "url": "https://fintolk.pro", "desc": "Финансы простым языком на русском — статьи, калькуляторы и советы"},
                    {"name": "Investopedia", "url": "https://www.investopedia.com", "desc": "Энциклопедия инвестиций и финансов — термины, стратегии и обучение (на английском)"},
                    {"name": "Khan Academy Finance", "url": "https://www.khanacademy.org/economics-finance-domain", "desc": "Бесплатные уроки по экономике и финансам — от базовых до продвинутых тем"},
                ],
            },
        ],
        "tools": [
            {"name": "Wealthsimple", "url": "https://www.wealthsimple.com", "desc": "Инвестируйте без комиссии — TFSA, RRSP, торговля акциями и ETF для начинающих", "badge": "Бесплатно"},
            {"name": "Questrade", "url": "https://www.questrade.com", "desc": "Канадский брокер — покупайте ETF без комиссии, управляйте RRSP и RESP", "badge": "Бесплатно"},
            {"name": "YNAB", "url": "https://www.ynab.com", "desc": "You Need A Budget — лучшее приложение для бюджетирования, помогает контролировать расходы", "badge": "Пробный период"},
            {"name": "Borrowell", "url": "https://www.borrowell.com", "desc": "Бесплатная проверка кредитного рейтинга — следите за вашим Equifax score", "badge": "Бесплатно"},
            {"name": "Wealthsimple Tax", "url": "https://www.wealthsimple.com/en-ca/tax", "desc": "Подайте налоговую декларацию бесплатно — простой интерфейс на английском", "badge": "Бесплатно"},
        ],
        "faq": [
            {"q": "Что такое TFSA?", "a": "Tax-Free Savings Account (TFSA) — это канадский сберегательный счёт, на котором вся прибыль от инвестиций не облагается налогом. Каждый год правительство увеличивает лимит взносов (в 2026 году — $7,000). Вы можете инвестировать в акции, ETF, облигации и GIC внутри TFSA, и все доходы — дивиденды, проценты, прирост капитала — остаются полностью вашими. Это один из лучших инструментов для долгосрочных сбережений в Канаде."},
            {"q": "Что такое RRSP?", "a": "Registered Retirement Savings Plan (RRSP) — это пенсионный сберегательный план. Главное отличие от TFSA: взносы в RRSP уменьшают ваш налогооблагаемый доход в текущем году (вы получаете налоговый возврат), но при снятии денег на пенсии вы платите налог. RRSP выгоден, если сейчас ваш доход (и налоговая ставка) выше, чем будет на пенсии. Лимит взносов — 18% от заработка прошлого года."},
            {"q": "Как начать инвестировать в Канаде?", "a": "Шаг 1: Откройте TFSA (максимально используйте налоговые льготы). Шаг 2: Выберите платформу — Wealthsimple (самая простая для начинающих) или Questrade (больше опций). Шаг 3: Начните с ETF широкого рынка, например XEQT или VGRO — они автоматически диверсифицированы по всему миру. Шаг 4: Инвестируйте регулярно (даже $50-100 в месяц), не пытайтесь угадать рынок. Время на рынке важнее, чем тайминг рынка."},
            {"q": "Что такое GIC?", "a": "Guaranteed Investment Certificate (GIC) — это гарантированный инвестиционный сертификат. Вы вкладываете деньги в банк на фиксированный срок (от 30 дней до 5 лет), и банк гарантирует возврат + проценты. GIC застрахованы CDIC до $100,000. Ставки зависят от срока и банка — сравнивайте на RateHub.ca. GIC подходят для краткосрочных сбережений (на первый взнос, фонд безопасности), но для долгосрочных целей ETF обычно приносят больше."},
            {"q": "Что такое кредитный рейтинг?", "a": "Кредитный рейтинг (credit score) — это число от 300 до 900, показывающее вашу кредитоспособность. В Канаде два бюро — Equifax и TransUnion. Рейтинг выше 700 считается хорошим, выше 750 — отличным. Он влияет на одобрение ипотеки, кредитных карт и процентные ставки. Чтобы улучшить рейтинг: платите вовремя, используйте менее 30% кредитного лимита, не закрывайте старые карты. Проверяйте бесплатно через Borrowell."},
        ],
    },
    "privet_russian": {
        "name": "Привет, Русский!",
        "slug": "privet_russian",
        # Buttondown rejects non-ASCII tags; keep the display name in
        # Cyrillic but tag in ASCII to match shows/privet_russian.yaml.
        "newsletter_tag": "Privet Russian",
        "display_order": 10,
        "description": "Bilingual Russian language learning podcast for English speakers.",
        "show_page": "ru/privet-russian.html",
        "summaries_page": "ru/privet-russian-summaries.html",
        "json_path": "digests/privet_russian/summaries_privet_russian.json",
        "json_format": "wrapped",
        "rss_file": "privet_russian_podcast.rss",
        "podcast_image": "assets/covers/privet-russian.jpg",
        "x_account": None,
        "brand_color": "#4F46E5",
        "brand_color_dark": "#4F46E5",
        "tagline": "Learn Russian — Привет means hello!",
        "hero_tagline": "Learn Russian — Привет means hello!",
        "schedule": "Even days",
        "episode_length": "~10 min",
        "about_text": "A bilingual Russian language learning podcast for English speakers — kids and adult beginners. Host Olya teaches vocabulary, phrases, grammar, and culture through fun, themed episodes.",
        "about_host": "Hosted by Olya from Vancouver. Each episode is a mini lesson you can practice anywhere.",
        "description_long": "A bilingual Russian language learning podcast for English speakers — kids and adult beginners. Vocabulary, phrases, grammar, and culture in fun themed episodes.",
        "related_show": "finansy_prosto",
        "related_reason": "If you enjoy Привет, Русский!, you might also like Финансы Просто — a Russian-language finance podcast for women in Canada.",
        "apple_podcasts_url": "https://podcasts.apple.com/us/podcast/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D1%80%D1%83%D1%81%D1%81%D0%BA%D0%B8%D0%B9/id1885236720",
        "spotify_url": "https://open.spotify.com/show/7rB9mPNBp5S6RCpHPKIZbL",
        "theme_color": "#4F46E5",
        "meta_description": "Привет, Русский! — Learn Russian with fun bilingual podcast episodes. Vocabulary, phrases, grammar, and culture for beginners.",
        "meta_keywords": "learn Russian, Russian podcast, Russian for beginners, Russian language, bilingual podcast",
        "audience": "For students, teens, curious parents, career changers, and anyone who wants to learn Russian — no experience needed.",
        "source_highlights": ["BBC News", "NPR", "National Geographic", "Moscow Times"],
        "resource_categories": [
            {
                "title": "Language Learning Apps",
                "resources": [
                    {"name": "Duolingo Russian", "url": "https://www.duolingo.com/course/ru/en/Learn-Russian", "desc": "Free gamified Russian course — 5 minutes a day builds vocabulary and grammar habits"},
                    {"name": "Babbel Russian", "url": "https://www.babbel.com/learn-russian", "desc": "Structured Russian lessons with speech recognition — more grammar-focused than Duolingo"},
                    {"name": "Busuu Russian", "url": "https://www.busuu.com/en/course/learn-russian-online", "desc": "Russian course with native speaker feedback on your writing and speaking exercises"},
                    {"name": "Pimsleur Russian", "url": "https://www.pimsleur.com/learn-russian", "desc": "Audio-first method — learn Russian through listening and speaking, great for car commutes"},
                ],
            },
            {
                "title": "Dictionaries & Grammar",
                "resources": [
                    {"name": "OpenRussian", "url": "https://en.openrussian.org", "desc": "Free Russian dictionary with declensions, conjugations, stress marks, and usage examples"},
                    {"name": "Wiktionary Russian", "url": "https://en.wiktionary.org/wiki/Category:Russian_language", "desc": "Community dictionary with etymologies, pronunciations, and detailed grammar tables"},
                    {"name": "Russian Grammar Tables", "url": "https://www.russianlessons.net/grammar/", "desc": "Clear grammar reference — cases, verb conjugations, and adjective agreements"},
                    {"name": "Reverso Context", "url": "https://context.reverso.net/translation/russian-english/", "desc": "See Russian words used in real sentences — context-based translation with examples"},
                ],
            },
            {
                "title": "Russian Media",
                "resources": [
                    {"name": "Russian With Max", "url": "https://russianwithmax.com", "desc": "Comprehensible input podcast — slow, clear Russian with transcripts for A2-B2 learners"},
                    {"name": "Meduza (English)", "url": "https://meduza.io/en", "desc": "Independent Russian news in English — understand current events and cultural context"},
                    {"name": "Arzamas Academy", "url": "https://arzamas.academy", "desc": "Russian culture and history courses — literature, art, and philosophy (in Russian with subtitles)"},
                    {"name": "Kinopoisk", "url": "https://www.kinopoisk.ru", "desc": "Russia's IMDB — find Russian films and TV shows to practice listening comprehension"},
                ],
            },
            {
                "title": "Practice & Immersion",
                "resources": [
                    {"name": "Forvo Russian", "url": "https://forvo.com/languages/ru/", "desc": "Hear native speakers pronounce any Russian word — essential for mastering pronunciation"},
                    {"name": "Tandem", "url": "https://www.tandem.net", "desc": "Find Russian-speaking language partners for text and voice chat — free language exchange"},
                    {"name": "italki", "url": "https://www.italki.com/en/teachers/russian", "desc": "Book affordable 1-on-1 lessons with native Russian tutors — from $5/hour"},
                    {"name": "Clozemaster", "url": "https://www.clozemaster.com/languages/eng-rus", "desc": "Learn Russian through mass sentence exposure — fill in the blanks in context"},
                ],
            },
            {
                "title": "Culture & History",
                "resources": [
                    {"name": "Russia Beyond", "url": "https://www.rbth.com", "desc": "Russian culture, history, food, and travel — English-language articles about Russia"},
                    {"name": "Moscow Times", "url": "https://www.themoscowtimes.com", "desc": "Independent English-language news about Russia — politics, culture, and society"},
                    {"name": "Russian Life Magazine", "url": "https://russianlife.com", "desc": "Russian culture, travel, and history — beautifully written long-form articles"},
                    {"name": "RussianPod101", "url": "https://www.russianpod101.com", "desc": "Comprehensive Russian learning platform — lessons, vocabulary lists, and cultural notes"},
                ],
            },
        ],
        "tools": [
            {"name": "Duolingo", "url": "https://www.duolingo.com/course/ru/en/Learn-Russian", "desc": "Start learning Russian with 5-minute daily lessons — gamified, fun, and builds habits", "badge": "Free"},
            {"name": "Anki", "url": "https://apps.ankiweb.net", "desc": "Spaced repetition flashcards — the most effective way to memorize Russian vocabulary", "badge": "Free"},
            {"name": "Forvo", "url": "https://forvo.com/languages/ru/", "desc": "Hear any Russian word pronounced by native speakers — type it in, hear it spoken", "badge": "Free"},
            {"name": "Tandem", "url": "https://www.tandem.net", "desc": "Free language exchange app — find native Russian speakers who want to learn English", "badge": "Free"},
            {"name": "Google Translate", "url": "https://translate.google.com/?sl=en&tl=ru", "desc": "Instant English-to-Russian translation — use camera mode to translate signs and menus", "badge": "Free"},
        ],
        "faq": [
            {"q": "How hard is Russian to learn?", "a": "The US Foreign Service Institute rates Russian as a Category III language — harder than Spanish or French, but easier than Chinese, Japanese, or Arabic. For English speakers, the main challenges are the Cyrillic alphabet (learnable in a week), six grammatical cases (takes months to internalize), and verb aspect (perfective vs imperfective). The good news: Russian pronunciation is very regular — if you can read a word, you can pronounce it. With daily practice, expect basic conversational ability in 6-12 months."},
            {"q": "What is the Cyrillic alphabet?", "a": "Cyrillic is the alphabet used to write Russian (and Ukrainian, Bulgarian, Serbian, and others). It has 33 letters — some look and sound like English letters (A, K, M, O, T), some look familiar but sound different (B sounds like V, H sounds like N, P sounds like R, C sounds like S), and some are unique (Ж, Щ, Ы, Э). You can learn all 33 letters in about a week of focused practice. Once you know Cyrillic, you can sound out any Russian word."},
            {"q": "How many cases does Russian have?", "a": "Russian has six grammatical cases: Nominative (subject), Genitive (possession/of), Dative (to/for), Accusative (direct object), Instrumental (by/with), and Prepositional (about/in). Cases change the endings of nouns, adjectives, and pronouns depending on their role in the sentence. English handles this with word order and prepositions; Russian uses endings. It sounds intimidating, but you learn them gradually — start with Nominative and Accusative, then add others as you progress."},
            {"q": "What's the difference between ты and вы?", "a": "Both mean 'you,' but ты (tee) is informal/singular and вы (vee) is formal/plural. Use ты with friends, family, children, and pets. Use вы with strangers, older people, professionals, and in formal situations. Вы (capitalized Вы) is also used as a polite singular 'you' — like saying 'sir' or 'ma'am' in English. Using the wrong form isn't a disaster, but switching from вы to ты with someone signals that you've become friends — it's a meaningful social moment in Russian culture."},
            {"q": "How long does it take to learn Russian?", "a": "It depends on your goals and daily practice. With 30 minutes/day: basic greetings and survival phrases in 1-2 months, simple conversations in 4-6 months, comfortable intermediate level in 12-18 months. The FSI estimates 1,100 classroom hours for professional proficiency. Key accelerators: daily consistency (even 15 minutes beats occasional long sessions), native speaker practice (italki or Tandem), and immersion through media (Russian music, YouTube, Netflix shows with subtitles). This podcast is designed to be one of those daily touchpoints!"},
        ],
    },
    "modern_investing": {
        "name": "Modern Investing Techniques",
        "slug": "modern_investing",
        "display_order": 6,
        "description": "AI-driven analysis of investing strategies, market trends, and financial techniques for the modern investor.",
        "show_page": "modern-investing.html",
        "summaries_page": "modern-investing-summaries.html",
        "performance_page": "modern-investing-performance.html",  # Dedicated recursive learning + transparency hub
        "json_path": "digests/modern_investing/summaries_modern_investing.json",
        "json_format": "wrapped",
        "rss_file": "modern_investing_podcast.rss",
        "podcast_image": "assets/covers/modern-investing.jpg",
        "x_account": None,
        "brand_color": "#047857",
        "brand_color_dark": "#047857",
        "tagline": "AI-Powered Market Intelligence",
        # Special: Strong recursive learning + public transparency vs NASDAQ
        "has_performance_loop": True,
        "hero_tagline": "AI-Powered Market Intelligence",
        "schedule": "Daily",
        "episode_length": "~12 min",
        "about_text": "Modern Investing Techniques is a daily investing podcast using AI analysis and modern tools to identify opportunities, track simulated trades, and teach strategies that aim to outperform index fund returns. Focused on Canadian and US markets.",
        "about_host": "Hosted by Patrick in Vancouver. Each episode covers market analysis, a strategy spotlight, AI-selected practice trades with real performance tracking, and tools to sharpen your investing edge.",
        "description_long": "Daily investing podcast using AI-driven analysis and modern tools to identify market opportunities, track simulated trades, and teach strategies that aim to outperform index funds. Covering Canadian and US markets with actionable picks, performance tracking, and lessons learned.",
        "related_show": "tesla",
        "related_reason": "If you're interested in TSLA as an investment, check out Tesla Shorts Time — our daily Tesla and EV analysis show.",
        "apple_podcasts_url": "https://podcasts.apple.com/us/podcast/modern-investing-techniques/id1886870483",
        "spotify_url": "https://open.spotify.com/show/2Txa9atsocnmm91r65Ahy9",
        "theme_color": "#047857",
        "meta_description": "Modern Investing Techniques — AI-powered daily market intelligence with simulated trades, strategy breakdowns, and tools for Canadian and US investors.",
        "meta_keywords": "investing podcast, stock market, ETF, TFSA, RRSP, AI investing, market analysis, modern investing, Canadian investing",
        "audience": "For active investors who want to go beyond buy-and-hold — using AI, modern platforms, and data-driven strategies.",
        "source_highlights": ["Financial Post", "BNN Bloomberg", "Globe and Mail", "Seeking Alpha"],
        "resource_categories": [
            {
                "title": "Canadian Investing Platforms",
                "resources": [
                    {"name": "Wealthsimple Trade", "url": "https://www.wealthsimple.com/en-ca/product/trade/", "desc": "Commission-free trading for Canadian stocks, ETFs, and crypto — TFSA/RRSP/FHSA supported"},
                    {"name": "Questrade", "url": "https://www.questrade.com", "desc": "Canada's largest independent online brokerage — free ETF purchases, low stock commissions"},
                    {"name": "Interactive Brokers", "url": "https://www.interactivebrokers.ca", "desc": "Professional-grade platform with the lowest margin rates — access to global markets"},
                    {"name": "National Bank Direct Brokerage", "url": "https://nbdb.ca", "desc": "Commission-free stock and ETF trading from a Big 5 bank — TFSA/RRSP accounts"},
                ],
            },
            {
                "title": "Market Research & Analysis",
                "resources": [
                    {"name": "TradingView", "url": "https://www.tradingview.com", "desc": "Advanced charting, technical analysis, screeners, and a massive community of traders sharing ideas"},
                    {"name": "Seeking Alpha", "url": "https://seekingalpha.com", "desc": "In-depth stock analysis, earnings call transcripts, and quantitative ratings"},
                    {"name": "Finviz", "url": "https://finviz.com", "desc": "Free stock screener, heatmaps, and market overview — essential for finding trade setups"},
                    {"name": "Yahoo Finance", "url": "https://finance.yahoo.com", "desc": "Free real-time quotes, financials, analyst ratings, and portfolio tracking"},
                ],
            },
            {
                "title": "Learning & Strategy",
                "resources": [
                    {"name": "Investopedia", "url": "https://www.investopedia.com", "desc": "The most comprehensive investing education resource — from basics to advanced strategies"},
                    {"name": "Canadian Couch Potato", "url": "https://canadiancouchpotato.com", "desc": "Index investing strategies for Canadians — the benchmark to beat with active strategies"},
                    {"name": "Rational Reminder", "url": "https://rationalreminder.ca", "desc": "Evidence-based investing from PWL Capital — academic research meets practical Canadian advice"},
                    {"name": "Ben Felix (YouTube)", "url": "https://www.youtube.com/@BenFelixCSI", "desc": "Factor investing, portfolio theory, and Canadian tax optimization explained brilliantly"},
                ],
            },
            {
                "title": "Canadian Tax-Advantaged Accounts",
                "resources": [
                    {"name": "TFSA Guide (CRA)", "url": "https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/tax-free-savings-account.html", "desc": "Official CRA guide to Tax-Free Savings Account — contribution limits, rules, and eligibility"},
                    {"name": "RRSP Guide (CRA)", "url": "https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/rrsps-related-plans.html", "desc": "Official guide to Registered Retirement Savings Plans — contribution room, deductions, withdrawals"},
                    {"name": "FHSA Guide (CRA)", "url": "https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/first-home-savings-account.html", "desc": "First Home Savings Account — the newest tax-advantaged account for first-time homebuyers"},
                    {"name": "Wealthsimple Tax", "url": "https://www.wealthsimple.com/en-ca/product/tax/", "desc": "Free Canadian tax filing — auto-imports slips, tracks TFSA/RRSP contributions"},
                ],
            },
        ],
        "tools": [
            {"name": "TradingView", "url": "https://www.tradingview.com", "desc": "Advanced charting, screeners, alerts, and technical analysis — the gold standard for active traders", "badge": "Free tier"},
            {"name": "Wealthsimple Trade", "url": "https://www.wealthsimple.com/en-ca/product/trade/", "desc": "Commission-free Canadian trading — stocks, ETFs, crypto in TFSA/RRSP/FHSA accounts", "badge": "Free"},
            {"name": "Finviz", "url": "https://finviz.com", "desc": "Stock screener, heatmaps, and market overview — find setups based on technicals or fundamentals", "badge": "Free"},
            {"name": "Yahoo Finance", "url": "https://finance.yahoo.com", "desc": "Real-time quotes, portfolio tracking, earnings calendars, and analyst estimates", "badge": "Free"},
            {"name": "Seeking Alpha", "url": "https://seekingalpha.com", "desc": "Deep stock analysis, quant ratings, earnings transcripts, and dividend data", "badge": "Free tier"},
            {"name": "Portfolio Visualizer", "url": "https://www.portfoliovisualizer.com", "desc": "Backtest portfolios, optimize asset allocation, and analyze historical factor returns", "badge": "Free tier"},
        ],
        "referral": {
            "url": "https://wealthsimple.com/invite/U5JROW",
            "heading": "Start Investing with Wealthsimple",
            "cta": "Get Started with Wealthsimple",
            "intro": "New to investing? Wealthsimple is Canada's most popular investing platform with commission-free trading, automatic contributions, and tax-advantaged accounts. Sign up with our referral link and start building your portfolio today.",
            "buyer_benefits": [
                "Commission-free trading on stocks, ETFs, and crypto",
                "Tax-advantaged accounts — TFSA, RRSP, and FHSA supported",
                "Fractional shares — start investing with as little as $1",
                "Automatic contributions and smart savings features",
            ],
            "how_to_steps": [
                "Click our referral link below to visit Wealthsimple",
                "Create your free account in minutes",
                "Open a TFSA, RRSP, or personal investing account",
                "Fund your account and start investing commission-free",
            ],
            "fine_print": "Wealthsimple referral benefits are subject to Wealthsimple's current terms and may change. This podcast is not financial advice — always do your own research before investing.",
        },
        "faq": [
            {"q": "Are the trades real?", "a": "No — all Practice Investment picks are simulated. We track them as if we invested $1,000 per trade using real market open/close prices, but no actual money is involved. This is purely educational. The podcast is not financial advice. Always do your own research before investing real money."},
            {"q": "What is a TFSA?", "a": "A Tax-Free Savings Account is a Canadian registered account where all investment gains — dividends, interest, and capital gains — are completely tax-free. In 2026, the annual contribution limit is $7,000, with cumulative room of $102,000 if you've been eligible since 2009. It's the most powerful wealth-building tool for most Canadians because you never pay tax on withdrawals."},
            {"q": "What is an ETF?", "a": "An Exchange-Traded Fund is a basket of investments (stocks, bonds, etc.) that trades on a stock exchange like a single stock. ETFs like VFV (S&P 500), XEQT (global equities), or VGRO (balanced growth) let you diversify across hundreds of companies with a single purchase. They typically have much lower fees than mutual funds — often 0.05-0.25% per year vs 2%+ for mutual funds."},
            {"q": "What does 'outperform index funds' mean?", "a": "Index funds like the S&P 500 (which returned ~10% annually over the last century) are the benchmark. 'Outperforming' means earning higher returns through active strategies — momentum trading, sector rotation, value picks, or options. Most active managers fail to beat the index over 10+ years, which is why we track our simulated trades honestly. The goal is education: understanding WHY strategies work or fail."},
            {"q": "Is this show financial advice?", "a": "No. Modern Investing Techniques is for educational and entertainment purposes only. We discuss strategies, analyze markets, and track simulated trades to help you learn — but we are not licensed financial advisors. Your financial situation is unique. Before making investment decisions, consider consulting a fee-only financial planner, especially for tax-advantaged account strategies (TFSA/RRSP/FHSA)."},
        ],
    },
    "unintended_consequences": {
        "name": "Unintended Consequences",
        "slug": "unintended_consequences",
        "display_order": 11,
        "description": "Inventions, policies, and systems designed with good intentions — and the surprising results they triggered.",
        "show_page": "unintended-consequences.html",
        "summaries_page": "unintended-consequences-summaries.html",
        "json_path": "digests/unintended_consequences/summaries_unintended_consequences.json",
        "json_format": "wrapped",
        "rss_file": "unintended_consequences_podcast.rss",
        "podcast_image": "assets/covers/unintended-consequences.jpg",
        "x_account": None,
        "brand_color": "#B45309",          # Deep amber — wisdom, caution, gravitas
        "brand_color_dark": "#92400E",
        "tagline": "Good intentions. Surprising results. Real lessons.",
        "hero_tagline": "Good intentions. Surprising results. Real lessons.",
        "schedule": "Weekdays",
        "episode_length": "~15-18 min",
        "about_text": "A daily narrative podcast profiling case studies of well-intentioned actions that triggered surprising consequences. From the Cobra Effect to social media algorithms, every episode follows a single story through good intentions, implementation, unexpected fallout, and the lessons we can learn.",
        "about_host": "Hosted by Patrick in Vancouver.",
        "description_long": "A daily narrative podcast profiling inventions, policies, and systems that were meant to help — but triggered surprising, unintended consequences. From the Cobra Effect to social media algorithms, every episode follows a single case study through good intentions, implementation, unexpected fallout, and the lessons we can learn.",
        "related_show": "env_intel",
        "related_reason": "If you enjoy Unintended Consequences, you might also like Environmental Intelligence — the regulatory side of how policy actually plays out.",
        # TODO(uc-launch): paste Apple Podcasts / Spotify URLs once
        # both directories ingest the feed (typically 3-7 days after
        # the first episode ships).
        "apple_podcasts_url": None,
        "spotify_url": None,
        "theme_color": "#B45309",
        "meta_description": "Unintended Consequences — Daily narrative podcast on inventions, policies, and systems that were designed to help but triggered surprising results.",
        "meta_keywords": "unintended consequences, history, policy, technology, narrative podcast, case studies",
        "audience": "For curious listeners who want stories with depth — historians, policy wonks, designers, engineers, and anyone who's ever wondered why a well-meaning fix made things worse.",
        "source_highlights": ["Academic journals", "Government archives", "Investigative journalism", "Retrospective analyses"],
        "resource_categories": [
            {
                "title": "Recommended Reading",
                "resources": [
                    {"name": "Antifragile (Nassim Taleb)", "url": "https://www.penguinrandomhouse.com/books/176227/antifragile-by-nassim-nicholas-taleb/", "desc": "Classic on systems that gain from disorder — and the ones that don't"},
                    {"name": "Seeing Like a State (James C. Scott)", "url": "https://yalebooks.yale.edu/book/9780300078152/seeing-like-a-state/", "desc": "Why centralized planning so often fails the people it tries to help"},
                    {"name": "The Alchemy of Air (Thomas Hager)", "url": "https://www.harmonybooks.com/", "desc": "The Haber-Bosch process — feeding the world, fueling two world wars"},
                    {"name": "Drawdown (Paul Hawken)", "url": "https://drawdown.org", "desc": "Climate solutions evaluated honestly — including ones that backfired"},
                ],
            },
            {
                "title": "Source Archives",
                "resources": [
                    {"name": "Wikipedia (case studies)", "url": "https://en.wikipedia.org", "desc": "Excellent for episode bibliographies and primary-source links"},
                    {"name": "JSTOR", "url": "https://www.jstor.org", "desc": "Peer-reviewed academic papers — many available with free registration"},
                    {"name": "Internet Archive", "url": "https://archive.org", "desc": "Newspapers, government reports, and historical documents"},
                    {"name": "Google Scholar", "url": "https://scholar.google.com", "desc": "Search engine for academic literature across all disciplines"},
                ],
            },
        ],
        "tools": [
            {"name": "Topic Submission", "url": "https://nerranetwork.com/unintended-consequences.html", "desc": "Have a case study you want to hear? Reach out — the topic queue is operator-curated and we welcome suggestions.", "badge": "Free"},
        ],
        "faq": [
            {"q": "Why this show?", "a": "The world is full of cautionary tales about complex systems, well-meaning interventions, and policies that backfired. Most get told as cheap 'look how dumb they were' stories. This show treats the original decision-makers with empathy and extracts general principles you can apply to your own decisions — at work, in policy, in product design."},
            {"q": "How do you choose topics?", "a": "From a curated queue of around 50 case studies organized into themes: classic studies (Cobra Effect, DDT, Prohibition), technology and the internet, policy and law, science and medicine, urban planning, and economics. New topics are added weekly. Listener suggestions are welcome."},
            {"q": "Is this depressing?", "a": "Not the goal. Each episode ends with one to three actionable lessons. Many topics also have happy endings — the ozone layer is healing, leaded gasoline is gone, thalidomide led to modern drug-safety regulation. The point is to learn, not to wallow."},
            {"q": "How long are episodes?", "a": "Each episode is 15-18 minutes — long enough for genuine depth on a single case, short enough for a daily commute. Episodes follow the same six-segment arc: Hook, Good Intention, Implementation, Unintended Consequences, Aftermath, Lesson."},
            {"q": "Do you fact-check?", "a": "Yes. Episodes draw on academic papers, government archives, investigative journalism, and retrospective analyses. When the historical record is uncertain, we hedge rather than fabricate ('estimates suggest…', 'by most accounts…'). Errors are corrected in the show notes when caught."},
        ],
    },
    "first_principles": {
        "name": "First Principles Daily",
        "slug": "first_principles",
        "display_order": 12,
        "description": "Reasoning about the world from first principles — the 'magic wand number' and the 'Idiot Index' — applied to the great cost breakthroughs of history and today, and the industries still ripe for one.",
        "show_page": "first-principles.html",
        "summaries_page": "first-principles-summaries.html",
        "json_path": "digests/first_principles/summaries_first_principles.json",
        "json_format": "wrapped",
        "rss_file": "first_principles_podcast.rss",
        "podcast_image": "assets/covers/first-principles-daily.jpg",
        "x_account": None,
        "brand_color": "#0F766E",          # Deep teal — engineering, clarity, depth
        "brand_color_dark": "#115E59",
        "tagline": "Reason from raw materials, not analogy.",
        "hero_tagline": "Reason from raw materials, not analogy.",
        "schedule": "Daily",
        "episode_length": "~10-12 min",
        "about_text": "A daily narrative podcast that reasons from first principles. Each episode alternates between a concrete example of first-principles thinking in action — drawn from across history and modern industry, from Henry Ford and Bessemer steel to solar, batteries, and yes sometimes SpaceX — and a deep exposé on an industry ripe for the same treatment. The recurring tools are the 'magic wand number' (what a thing would cost if you only paid for its raw materials) and the 'Idiot Index' (how many times more the finished thing costs than the materials inside it). Elon Musk popularized that language; the method is much older and much bigger than any one person.",
        "about_host": "Hosted by Patrick in Vancouver.",
        "description_long": "A daily narrative podcast that takes one idea seriously: most of the world runs on reasoning by analogy, and reasoning from first principles — building up from raw materials and physics — is how the biggest leaps actually happen. Episodes alternate between a concrete example of this thinking in action — historical breakthroughs like the moving assembly line, Bessemer steel, and the shipping container, modern cost curves like solar and batteries, and occasionally one of Musk's teams — and a deep look at an industry whose Idiot Index is begging to be attacked.",
        "related_show": "tesla",
        "related_reason": "If you enjoy First Principles Daily, you might also like Tesla Shorts Time — the daily rundown on the company where a lot of this thinking shows up first.",
        "apple_podcasts_url": None,
        "spotify_url": None,
        "theme_color": "#0F766E",
        "meta_description": "First Principles Daily — a daily podcast that reasons from raw materials, not analogy, using Elon Musk's magic-wand number and Idiot Index on real engineering and the industries ripe for it.",
        "meta_keywords": "first principles, Elon Musk, SpaceX, Tesla, engineering, idiot index, cost, manufacturing, innovation",
        "audience": "For engineers, builders, founders, and the endlessly curious — anyone who wants to understand WHY something costs what it costs and where the next 10x is hiding.",
        "source_highlights": ["Primary engineering accounts", "Company technical disclosures", "Reputable trade and science press", "First-principles cost reasoning"],
        "resource_categories": [
            {
                "title": "Foundations",
                "resources": [
                    {"name": "Elon Musk (Walter Isaacson)", "url": "https://www.simonandschuster.com/books/Elon-Musk/Walter-Isaacson/9781982181284", "desc": "Where the 'magic wand number' and 'Idiot Index' are laid out in the subject's own words"},
                    {"name": "The Case for Space (Robert Zubrin)", "url": "https://www.penguinrandomhouse.com/", "desc": "First-principles economics of getting to orbit and beyond"},
                    {"name": "How Big Things Get Done (Bent Flyvbjerg)", "url": "https://www.penguinrandomhouse.com/", "desc": "Why megaprojects blow their budgets — and the few that don't"},
                ],
            },
            {
                "title": "Going Deeper",
                "resources": [
                    {"name": "The Box (Marc Levinson)", "url": "https://press.princeton.edu/books/paperback/9780691170817/the-box", "desc": "How the shipping container — not any one genius — remade the cost of global trade"},
                    {"name": "Construction Physics", "url": "https://www.construction-physics.com/", "desc": "First-principles writing on why building things costs what it does"},
                    {"name": "Works in Progress", "url": "https://worksinprogress.co/", "desc": "Essays on progress, cost disease, and what's actually possible"},
                ],
            },
        ],
        "tools": [
            {"name": "Topic Submission", "url": "https://nerranetwork.com/first-principles.html", "desc": "Know an industry with an outrageous Idiot Index, or a great example of first-principles engineering? The topic queue is operator-curated and suggestions are welcome.", "badge": "Free"},
        ],
        "faq": [
            {"q": "What is this show?", "a": "A daily podcast that reasons about the world from first principles. Each episode either dissects a concrete example of first-principles thinking inside one of Elon Musk's companies, or makes the case for an industry that's ripe for the same treatment. The tools are the 'magic wand number' (the raw-material cost floor) and the 'Idiot Index' (finished cost divided by material cost)."},
            {"q": "What's the cadence?", "a": "Every day, alternating: one day a concrete example, the next an opportunity area. Episode 1 is a longer premiere that introduces the framework with two worked examples — the SpaceX Raptor engine, and an industry ripe for first-principles thinking."},
            {"q": "Where do the numbers come from?", "a": "Well-established public figures wherever possible. Cost estimates and Idiot-Index figures are reasoned out loud and clearly flagged as approximate ('roughly', 'on the order of') — the show makes the reasoning visible so you can judge it, and never presents a back-of-the-envelope number as a measured fact."},
            {"q": "How long are episodes?", "a": "About 10 to 12 minutes — long enough to genuinely walk through the reasoning, short enough for a daily commute."},
            {"q": "Is this just Elon Musk fan content?", "a": "No. Musk popularized the 'magic wand number' and 'Idiot Index' language and his teams are vivid modern examples, but first-principles thinking is old and widespread — the show draws on Henry Ford and the moving assembly line, Bessemer steel, the shipping container, the Haber-Bosch process, and modern cost curves like solar, batteries, and mRNA, as well as the industries (housing, desalination, nuclear, the power grid, and more) where no one has applied it yet. Musk's teams appear as some examples among many, never as the whole show."},
        ],
    },
}


# Complete English nav/footer translation map for standalone pages that
# extend base.html.j2 (dashboard, etc.). Mirrors the inline dicts the
# narrative pages use, with the mobile-nav keys filled in so no label
# renders empty.
_NAV_T = {
    "nav_shows": "Shows", "nav_blog": "Blog", "all_blog_posts": "All Blog Posts",
    "show_blog_suffix": "Blog", "nav_start_here": "Start Here",
    "nav_listen": "How to Listen", "nav_how_to_listen": "How to Listen",
    "nav_about": "About", "nav_player": "Player", "nav_home": "Home",
    "toggle_menu": "Toggle menu", "mobile_all_shows": "All Shows",
    "mobile_blogs": "Blogs", "footer_network_status": "Network Status",
}


# Shows that render a live stock-price pill in the hero. Each show's
# pipeline hook writes the same-origin JSON; the page JS reads it first
# and falls back to Yahoo Finance via CORS proxies. yahoo_symbol is the
# fallback ticker queried at query{1,2}.finance.yahoo.com.
_STOCK_WIDGETS: dict = {
    "tesla": {"ticker": "TSLA", "json_path": "/api/tsla.json", "yahoo_symbol": "TSLA"},
    "spacex": {"ticker": "SPCX", "json_path": "/api/spcx.json", "yahoo_symbol": "SPCX"},
}


# Curated "best source of <topic> information" resource blocks for
# scaffolded shows (the hardcoded NETWORK_SHOWS entries carry their own;
# this layers rich resources onto shows defined in network_meta.yaml
# without bloating that auto-generated file). Merged in below.
_SCAFFOLD_SHOW_RESOURCES: dict = {
    "spacex": {
        "resource_categories": [
            {
                "title": "SpaceX — Official",
                "resources": [
                    {"name": "SpaceX.com", "url": "https://www.spacex.com", "desc": "The company's official site — vehicles, missions, and capabilities"},
                    {"name": "SpaceX Launches", "url": "https://www.spacex.com/launches/", "desc": "Upcoming and past launches with mission details and webcasts"},
                    {"name": "Starship", "url": "https://www.spacex.com/vehicles/starship/", "desc": "The fully reusable launch system built for the Moon and Mars"},
                    {"name": "Starlink", "url": "https://www.starlink.com", "desc": "SpaceX's satellite-internet constellation — the company's cash engine"},
                    {"name": "SpaceX on X", "url": "https://x.com/SpaceX", "desc": "Official launch announcements, webcasts, and mission updates"},
                    {"name": "SpaceX on YouTube", "url": "https://www.youtube.com/@SpaceX", "desc": "Live launch webcasts and mission replays in full"},
                ],
            },
            {
                "title": "SPCX — Stock, Filings & the IPO",
                "resources": [
                    {"name": "SpaceX S-1 / Prospectus (SEC EDGAR)", "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=space+exploration+technologies&type=S-1&dateb=&owner=include&count=40", "desc": "The registration statement behind the June 2026 IPO — the numbers, straight from the source"},
                    {"name": "SEC EDGAR — all SpaceX filings", "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=space+exploration+technologies&type=&dateb=&owner=include&count=40", "desc": "Every public filing as it lands — 10-Ks, 10-Qs, 8-Ks, insider forms"},
                    {"name": "SPCX on Yahoo Finance", "url": "https://finance.yahoo.com/quote/SPCX", "desc": "Real-time quote, charts, financials, and analyst coverage"},
                    {"name": "SPCX on TradingView", "url": "https://www.tradingview.com/symbols/NASDAQ-SPCX/", "desc": "Advanced charting, technicals, and community trade ideas"},
                    {"name": "SPCX on Nasdaq", "url": "https://www.nasdaq.com/market-activity/stocks/spcx", "desc": "Exchange-of-record quote page, volume, and corporate data"},
                ],
            },
            {
                "title": "Spaceflight News & Analysis",
                "resources": [
                    {"name": "NASASpaceflight", "url": "https://www.nasaspaceflight.com", "desc": "The deepest independent launch reporting and Starbase coverage"},
                    {"name": "SpaceNews", "url": "https://spacenews.com", "desc": "Industry, policy, and business of the space sector"},
                    {"name": "Ars Technica — Space", "url": "https://arstechnica.com/space/", "desc": "Eric Berger's authoritative, skeptical spaceflight analysis"},
                    {"name": "Spaceflight Now", "url": "https://spaceflightnow.com", "desc": "Launch schedules and live mission coverage"},
                    {"name": "Eric Berger on X", "url": "https://x.com/SciGuySpace", "desc": "Breaking SpaceX news and reporting from Ars Technica's senior space editor"},
                    {"name": "Michael Sheetz on X", "url": "https://x.com/thesheetztweetz", "desc": "CNBC's space-business reporter — the SPCX investor angle"},
                ],
            },
            {
                "title": "Launch Tracking & Data",
                "resources": [
                    {"name": "Next Spaceflight", "url": "https://nextspaceflight.com", "desc": "Every upcoming launch with countdowns, rockets, and pads"},
                    {"name": "Flight Club", "url": "https://flightclub.io", "desc": "Live trajectory simulations and telemetry for orbital launches"},
                    {"name": "Jonathan's Space Report", "url": "https://planet4589.org/space/jsr/jsr.html", "desc": "Jonathan McDowell's authoritative catalogue of launches and satellites"},
                    {"name": "r/SpaceX", "url": "https://www.reddit.com/r/spacex/", "desc": "The largest SpaceX community — launch threads and technical discussion"},
                    {"name": "r/SpaceXLounge", "url": "https://www.reddit.com/r/SpaceXLounge/", "desc": "Looser SpaceX discussion, speculation, and community analysis"},
                ],
            },
            {
                "title": "AI & Compute — xAI, Grok & the Musk Stack",
                "resources": [
                    {"name": "xAI", "url": "https://x.ai", "desc": "Musk's AI company — the compute/AI-satellite thread that runs through the SpaceX story"},
                    {"name": "xAI News", "url": "https://x.ai/news", "desc": "Official xAI announcements — new Grok models, Colossus compute, and partnerships"},
                    {"name": "xAI API & Docs", "url": "https://docs.x.ai", "desc": "The Grok API — models, pricing, and capabilities (also powers this show)"},
                    {"name": "Grok", "url": "https://grok.com", "desc": "xAI's assistant — the AI that researches and voices this show"},
                    {"name": "Grok on X", "url": "https://x.com/grok", "desc": "Grok updates and the X-platform integration"},
                    {"name": "Cursor", "url": "https://cursor.com", "desc": "The AI code editor (Anysphere) — Grok is selectable in it; a window into how xAI models reach developers"},
                    {"name": "Cursor Changelog", "url": "https://cursor.com/changelog", "desc": "Cursor's latest releases and model integrations, including Grok"},
                    {"name": "Elon Musk on X", "url": "https://x.com/elonmusk", "desc": "First-hand program updates across SpaceX, xAI, and X"},
                ],
            },
            {
                "title": "Partnerships & Customers",
                "resources": [
                    {"name": "NASA Commercial Crew", "url": "https://www.nasa.gov/humans-in-space/commercial-space/commercial-crew-program/", "desc": "Dragon flies NASA astronauts to the ISS — SpaceX's anchor government partner"},
                    {"name": "NASA Artemis", "url": "https://www.nasa.gov/humans-in-space/artemis/", "desc": "Starship is the human landing system for NASA's return to the Moon"},
                    {"name": "T-Mobile Starlink", "url": "https://www.t-mobile.com/coverage/satellite-phone-service", "desc": "Starlink direct-to-cell — SpaceX's flagship carrier partnership"},
                    {"name": "Space Force / SSC", "url": "https://www.ssc.spaceforce.mil/", "desc": "National-security launch and Starshield contracts"},
                ],
            },
        ],
        "tools": [
            {"name": "SpaceX Launch Dashboard", "url": "https://nerranetwork.com/spacex-dashboard.html", "desc": "Live next-launch countdown, cadence, fleet & payload stats, and SPCX", "badge": "Free"},
            {"name": "SPCX on TradingView", "url": "https://www.tradingview.com/symbols/NASDAQ-SPCX/", "desc": "Chart SPCX with technicals and alerts", "badge": "Free tier"},
            {"name": "SEC EDGAR Full-Text Search", "url": "https://efts.sec.gov/LATEST/search-index?q=%22space+exploration+technologies%22", "desc": "Search every word of every SpaceX filing", "badge": "Free"},
            {"name": "Next Spaceflight", "url": "https://nextspaceflight.com", "desc": "Never miss a launch — schedules and countdowns", "badge": "Free"},
        ],
        "faq": [
            {"q": "What is SpaceX Daily?", "a": "A daily podcast and blog that tracks SpaceX now that it's a public company (Nasdaq: SPCX). Every weekday: the day's developments with sources, what the spaceflight community is talking about, one honest counterpoint, a first-principles engineering deep dive, a dedicated AI & Compute segment (the SpaceX↔xAI/Grok thread), and the SPCX market picture. Hosted by Patrick in Vancouver."},
            {"q": "Why does a SpaceX show cover xAI and Grok?", "a": "Because the businesses are increasingly one stack. SpaceX earmarked IPO proceeds for AI compute infrastructure, is developing orbital data centers and 'AI satellites', and Starlink is the backhaul for a planet-wide compute-and-connectivity play. xAI (Grok, the Colossus datacenters) and X sit on the other side of that same Musk compute ecosystem — so the show carries a dedicated AI & Compute segment for Grok, xAI, X, and the partnerships (like Grok in Cursor) that show where the models are going."},
            {"q": "What is SPCX?", "a": "SPCX is SpaceX's stock ticker on the Nasdaq. SpaceX held the largest IPO in history in June 2026, pricing at $135 per share and raising about $75 billion at a valuation near $1.8 trillion. A dual-class share structure leaves Elon Musk with a controlling majority of the voting power. Nothing on this show is financial advice."},
            {"q": "Where do the numbers come from?", "a": "Official sources wherever possible — SpaceX announcements, the SEC S-1/prospectus and later filings, and credible reporting from NASASpaceflight, SpaceNews, Ars Technica, and CNBC. Community and social posts are clearly flagged as unverified. The live SPCX price on this page is refreshed every run from market data."},
            {"q": "How long are episodes?", "a": "About 11 to 14 minutes — enough to walk through the day's launches, programs, the engineering, the AI thread, and the market picture, short enough for a commute."},
            {"q": "Is this just Elon Musk fan content?", "a": "No. The show is genuinely balanced: every episode carries an honest counterpoint, and the premiere named the real risks — stretched valuation, Musk's concentrated voting control, and a launch business that still loses money while Starlink carries the profit. Enthusiasm grounded in numbers is the brand."},
        ],
    },
}


def _merge_scaffolded_network_registry() -> None:
    """Overlay shows/network_meta.yaml (from scaffold_show.py) onto registries."""
    meta_path = SHOWS_DIR / "network_meta.yaml"
    if not meta_path.exists():
        return
    try:
        import yaml as _yaml
        extra = _yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return
    if not isinstance(extra, dict):
        return
    for slug, meta in extra.items():
        if not isinstance(meta, dict):
            continue
        meta = dict(meta)
        picker = meta.pop("picker_tags", None)
        # Layer curated resource blocks (resource_categories/tools/faq)
        # onto the scaffolded base metadata — keeps the rich, hand-written
        # link sets in Python instead of the auto-generated YAML.
        if slug in _SCAFFOLD_SHOW_RESOURCES:
            for key, value in _SCAFFOLD_SHOW_RESOURCES[slug].items():
                if not meta.get(key):
                    meta[key] = value
        if slug not in NETWORK_SHOWS:
            NETWORK_SHOWS[slug] = meta
        if picker and slug not in _SHOW_PICKER_TAGS:
            _SHOW_PICKER_TAGS[slug] = picker


# Per-show interest tags used by the "Find Your Show" picker on the
# network landing page. Intentionally small and curated — every tag is a
# button on the picker UI, and every show must claim at least one tag
# from each category the picker groups by.
#
# Format: {slug: {topics: [...], audience: [...], language: [...]}}
_SHOW_PICKER_TAGS = {
    "tesla": {
        "topics": ["tesla", "ev", "tech", "stocks", "energy"],
        "audience": ["investors", "enthusiasts"],
        "language": ["english"],
    },
    "omni_view": {
        "topics": ["world-news", "politics", "balanced"],
        "audience": ["professionals", "citizens"],
        "language": ["english"],
    },
    "fascinating_frontiers": {
        "topics": ["space", "astronomy", "science"],
        "audience": ["enthusiasts", "students"],
        "language": ["english"],
    },
    "planetterrian": {
        "topics": ["longevity", "biotech", "health", "science"],
        "audience": ["professionals", "enthusiasts"],
        "language": ["english"],
    },
    "env_intel": {
        "topics": ["environment", "climate", "regulatory"],
        "audience": ["professionals"],
        "language": ["english"],
    },
    "models_agents": {
        "topics": ["ai", "tech", "research"],
        "audience": ["builders", "professionals"],
        "language": ["english"],
    },
    "models_agents_beginners": {
        "topics": ["ai", "tech"],
        "audience": ["students", "beginners"],
        "language": ["english"],
    },
    "modern_investing": {
        "topics": ["investing", "stocks", "personal-finance"],
        "audience": ["investors", "professionals"],
        "language": ["english"],
    },
    "finansy_prosto": {
        "topics": ["personal-finance", "investing"],
        "audience": ["newcomers", "families"],
        "language": ["russian"],
    },
    "privet_russian": {
        "topics": ["language-learning"],
        "audience": ["students", "heritage-learners"],
        "language": ["bilingual"],
    },
    "unintended_consequences": {
        "topics": ["history", "policy", "technology", "narrative"],
        "audience": ["enthusiasts", "professionals", "students"],
        "language": ["english"],
    },
    "first_principles": {
        "topics": ["engineering", "tech", "innovation", "narrative"],
        "audience": ["builders", "professionals", "enthusiasts"],
        "language": ["english"],
    },
}


# Must run AFTER _SHOW_PICKER_TAGS is defined — the merge writes scaffolded
# shows' picker tags into it (NameError at import time otherwise, which only
# fires once network_meta.yaml has its first entry).
_merge_scaffolded_network_registry()


def _newsletter_tag_for_slug(slug: str, fallback_name: str) -> str:
    """Return the Buttondown tag for a show.

    Reads ``newsletter.tag`` from the show's YAML when available so
    the network signup form posts the same tag string the per-show
    forms use. Falls back to the show's display name. Buttondown
    requires tags to contain at least one ASCII letter or digit, so
    Russian shows now ship ASCII tags ("Privet Russian", "Finansy
    Prosto") rather than their Cyrillic display names.
    """
    import yaml as _yaml

    yaml_path = SHOWS_DIR / f"{slug}.yaml"
    if yaml_path.exists():
        try:
            data = _yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            tag = ((data.get("newsletter") or {}).get("tag") or "").strip()
            if tag:
                return tag
        except _yaml.YAMLError:
            pass
    return fallback_name


def _build_all_shows_list():
    """Build a list of all shows with metadata needed by templates."""
    shows = [
        {
            "name": cfg["name"],
            "slug": cfg["slug"],
            "show_page": cfg["show_page"],
            "summaries_page": cfg["summaries_page"],
            "podcast_image": cfg["podcast_image"],
            "rss_file": cfg["rss_file"],
            "language_feeds": _collect_language_feeds(cfg["rss_file"], ""),
            "brand_color": cfg["brand_color"],
            "tagline": cfg["tagline"],
            "schedule": cfg.get("schedule", "Daily"),
            "episode_length": cfg.get("episode_length", ""),
            "description_long": cfg.get("description_long", cfg["description"]),
            "source_highlights": cfg.get("source_highlights", []),
            "audience": cfg.get("audience", ""),
            "apple_podcasts_url": cfg.get("apple_podcasts_url"),
            "spotify_url": cfg.get("spotify_url"),
            "picker_tags": _SHOW_PICKER_TAGS.get(cfg["slug"], {}),
            "blog_page": f"blog/{cfg['slug']}/index.html",
            "newsletter_tag": _newsletter_tag_for_slug(cfg["slug"], cfg["name"]),
            "_order": cfg.get("display_order", 99),
        }
        for cfg in NETWORK_SHOWS.values()
    ]
    shows.sort(key=lambda s: s["_order"])
    return shows


def _url_encode_image(image_path):
    """URL-encode an image filename for use in OG/meta tags."""
    return quote(image_path, safe="/")


def _path_prefix(html_path):
    """Return a relative prefix to reach the repo root from *html_path*.

    For root-level files (e.g. ``tesla.html``) this returns ``""``.
    For files in subdirectories (e.g. ``ru/finansy-prosto.html``) this
    returns ``"../"``, so that ``{{ path_prefix }}styles/main.css`` resolves
    correctly regardless of page depth.
    """
    depth = html_path.count("/")
    return "../" * depth


def _load_mit_performance_data():
    """Return the Modern Investing performance block for template rendering.

    Tries ``api/dashboard.json`` first (regenerated by ``generate_dashboard.py``
    in CI before this script runs). Falls back to calling the aggregator
    directly so local dev / dry-run also works. Returns ``None`` if neither
    path yields usable data — the template gates on
    ``performance_data and performance_data.available``.
    """
    import json
    dashboard_path = ROOT / "api" / "dashboard.json"
    if dashboard_path.exists():
        try:
            data = json.loads(dashboard_path.read_text(encoding="utf-8"))
            perf = data.get("mit_performance")
            if isinstance(perf, dict) and perf.get("available"):
                return perf
        except (json.JSONDecodeError, OSError):
            pass
    # Fallback to the aggregator so `generate_html.py` works standalone.
    try:
        import sys as _sys
        _sys.path.insert(0, str(ROOT / "scripts"))
        from generate_dashboard import aggregate_mit_performance  # type: ignore
        return aggregate_mit_performance(ROOT)
    except Exception:
        return None


def _mit_chart_data(tracker):
    """Build chart-ready series from the investment tracker for the MIT
    performance page: an equity curve (cumulative % over closed trades by
    date), the win/loss split, and per-sector P&L. Returns {} when the
    tracker is missing so the template's charts simply don't render."""
    import math

    def _fin(v):
        """Finite float or None (guards the yfinance-NaN class so the
        baked JSON never contains NaN/Infinity, which break JSON.parse)."""
        try:
            f = float(v)
            return f if math.isfinite(f) else None
        except (TypeError, ValueError):
            return None

    if not isinstance(tracker, dict):
        return {}
    trades = [t for t in tracker.get("trades", [])
              if isinstance(t, dict) and _fin(t.get("pnl_pct")) is not None and t.get("date")]
    trades.sort(key=lambda t: t.get("date", ""))
    equity, cum = [], 0.0
    for t in trades:
        cum += _fin(t["pnl_pct"])
        equity.append({"date": t["date"], "cum": round(cum, 2),
                       "symbol": t.get("symbol", "")})
    s = tracker.get("summary", {}) or {}
    sectors = tracker.get("sectors", {}) or {}
    sector_pnl = sorted(
        ({"sector": k.replace("_", " "), "pnl": round(_fin(v.get("cumulative_pnl")) or 0.0, 2),
          "trades": v.get("trade_count", 0)}
         for k, v in sectors.items() if (v or {}).get("trade_count", 0) > 0),
        key=lambda x: x["pnl"], reverse=True,
    )
    recent = [{"date": t.get("date", ""), "symbol": t.get("symbol", ""),
               "strategy": t.get("strategy", ""), "pnl": _fin(t.get("pnl_pct"))}
              for t in reversed(trades[-8:])]
    # Monthly P&L (sum of closed-trade % points per calendar month) — same
    # basis as the equity curve, just bucketed; powers a green/red bar chart.
    from collections import OrderedDict
    by_month = OrderedDict()
    for t in trades:
        ym = (t.get("date") or "")[:7]  # YYYY-MM
        if len(ym) == 7:
            by_month[ym] = by_month.get(ym, 0.0) + _fin(t["pnl_pct"])
    monthly_pnl = [{"month": k, "pnl": round(v, 2)} for k, v in by_month.items()]
    return {
        "equity_curve": equity,
        "monthly_pnl": monthly_pnl,
        "winloss": {"wins": s.get("wins", 0), "losses": s.get("losses", 0),
                    "breakeven": s.get("breakeven", 0)},
        "sector_pnl": sector_pnl,
        "recent_trades": recent,
        "headline": {
            "cumulative_pnl": _fin(s.get("cumulative_pnl")),
            "cumulative_alpha": _fin(s.get("cumulative_alpha_vs_nasdaq")),
            "win_rate": _fin(s.get("win_rate_pct")),
            "best": _fin(s.get("best_trade_pct")), "worst": _fin(s.get("worst_trade_pct")),
            "longest_win_streak": s.get("longest_win_streak"),
        },
    }


def _load_tesla_narrative_data():
    """Load the Tesla narrative tracker for the public page."""
    import json
    tracker_path = ROOT / "digests" / "tesla_shorts_time" / "tesla_narrative_tracker.json"
    if not tracker_path.exists():
        return None
    try:
        data = json.loads(tracker_path.read_text(encoding="utf-8"))
        return {
            "available": True,
            "programs": data.get("programs", {}),
            "last_updated": data.get("last_updated", ""),
        }
    except Exception:
        return None


def _with_utm(url, source="nerranetwork", medium="web", campaign=""):
    """Jinja filter: append UTM tracking parameters to an outbound URL.

    Skips empty URLs. Preserves existing query parameters. Used for
    Apple Podcasts / Spotify links so we can attribute subscriber
    acquisition by source.
    """
    if not url:
        return url
    # Don't double-tag URLs that already have utm parameters
    if "utm_source=" in url:
        return url
    sep = "&" if "?" in url else "?"
    parts = ["utm_source=" + quote(source), "utm_medium=" + quote(medium)]
    if campaign:
        parts.append("utm_campaign=" + quote(campaign))
    return url + sep + "&".join(parts)


def _get_jinja_env():
    """Create a shared Jinja2 environment with marketing globals + filters."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False,
        keep_trailing_newline=True,
    )
    # Make marketing config available in every template without
    # threading it through every render() call.
    env.globals["marketing"] = MARKETING_CONFIG
    env.filters["with_utm"] = _with_utm
    # Jinja's default ``tojson`` filter inherits Python's
    # ``ensure_ascii=True``, which escapes Cyrillic to ``Ф...``
    # in rendered HTML. That's bad for SEO (Google parsers prefer
    # readable Unicode) and bad for shareable copy-paste. Override the
    # policy so ``{{ show_name | tojson }}`` for "Финансы Просто"
    # renders as ``"Финансы Просто"`` instead of ``"Фи..."``.
    env.policies["json.dumps_kwargs"] = {
        "sort_keys": True,
        "ensure_ascii": False,
    }
    return env


# ---------------------------------------------------------------------------
# Summaries pages
# ---------------------------------------------------------------------------

def generate_summaries_page(slug, *, dry_run=False):
    """Render and write a summaries page for a single show."""
    cfg = NETWORK_SHOWS[slug]
    env = _get_jinja_env()
    template = env.get_template("summaries_page.html.j2")

    podcast_logo_url = None
    og_image_url = None
    if cfg.get("podcast_image"):
        podcast_logo_url = f"{GITHUB_RAW}/{_url_encode_image(cfg['podcast_image'])}"
        og_image_url = podcast_logo_url

    prefix = _path_prefix(cfg["summaries_page"])

    context = {
        **cfg,
        "path_prefix": prefix,
        "show_name": cfg["name"],
        "show_slug": cfg["slug"],
        "page_title": f"{cfg['name']} | Summaries",
        "podcast_logo_url": podcast_logo_url,
        "og_image": og_image_url,
        "show_color": cfg["brand_color"],
        "show_color_dark": cfg.get("brand_color_dark", cfg["brand_color"]),
        "canonical_url": f"{GITHUB_RAW}/{cfg['summaries_page']}",
        "rss_url": f"{prefix}{cfg['rss_file']}",
        "hero_title": cfg["name"],
        "hero_subtitle": f"Complete archive of {cfg['name']} episode summaries.",
        "blog_page": f"blog/{cfg['slug']}/index.html",
        "all_shows": _build_all_shows_list(),
        "page_lang": "ru" if slug in ("finansy_prosto", "privet_russian") else "en",
        **_read_show_youtube(slug),
    }

    html = template.render(**context)

    out_path = ROOT / cfg["summaries_page"]
    if dry_run:
        print(f"[dry-run] Would write {out_path} ({len(html):,} bytes)")
        return None

    out_path.write_text(_strip_lone_surrogates(html), encoding="utf-8")
    print(f"Wrote {out_path} ({len(html):,} bytes)")
    return out_path


def generate_all_summaries(*, dry_run=False):
    """Generate summaries pages for every show."""
    paths = []
    for slug in NETWORK_SHOWS:
        result = generate_summaries_page(slug, dry_run=dry_run)
        if result:
            paths.append(result)
    return paths


# ---------------------------------------------------------------------------
# Show pages
# ---------------------------------------------------------------------------

def generate_mit_performance_page(*, dry_run=False):
    """Generate the dedicated Modern Investing Techniques Performance & Lessons page."""
    cfg = NETWORK_SHOWS["modern_investing"]
    env = _get_jinja_env()
    template = env.get_template("mit_performance_page.html.j2")

    performance_data = _load_mit_performance_data()

    # Load richer data directly from tracker for the dedicated page
    tracker_data = None
    try:
        tracker_path = ROOT / "digests" / "modern_investing" / "investment_tracker.json"
        if tracker_path.exists():
            tracker_data = json.loads(tracker_path.read_text(encoding="utf-8"))
    except Exception:
        pass

    context = {
        "show": cfg,
        "performance_data": performance_data,
        "tracker": tracker_data,
        "mit_charts": _mit_chart_data(tracker_data),
        "path_prefix": "",
        "is_russian": False,
        "t": {
            "nav_shows": "Shows", "nav_blog": "Blog", "all_blog_posts": "All Blog Posts",
            "show_blog_suffix": "Blog", "nav_start_here": "Start Here", "nav_listen": "How to Listen",
            "nav_about": "About", "nav_player": "Player", "nav_home": "Home",
            "footer_network_status": "Network Status"
        },
        "all_shows": _build_all_shows_list(),
        "youtube": _read_show_youtube("modern_investing"),
        "image_provider": _read_show_image_provider("modern_investing"),
    }

    html = template.render(**context)
    out_path = ROOT / cfg["performance_page"]

    if dry_run:
        print(f"[dry-run] Would write {out_path} ({len(html):,} bytes)")
        return None

    out_path.write_text(_strip_lone_surrogates(html), encoding="utf-8")
    print(f"Wrote dedicated MIT Performance page: {out_path}")
    return out_path


def generate_tesla_narrative_page(*, dry_run=False):
    """Generate the public Tesla Narrative Tracker / Storylines page."""
    env = _get_jinja_env()
    template = env.get_template("tesla_narrative_page.html.j2")

    narrative_data = _load_tesla_narrative_data()

    context = {
        "narrative": narrative_data,
        "path_prefix": "",
        "is_russian": False,
        "t": {
            "nav_shows": "Shows", "nav_blog": "Blog", "all_blog_posts": "All Blog Posts",
            "show_blog_suffix": "Blog", "nav_start_here": "Start Here", "nav_listen": "How to Listen",
            "nav_about": "About", "nav_player": "Player", "nav_home": "Home",
            "footer_network_status": "Network Status"
        },
        "all_shows": _build_all_shows_list(),
    }

    html = template.render(**context)
    out_path = ROOT / "tesla-narrative.html"

    if dry_run:
        print(f"[dry-run] Would write {out_path}")
        return out_path

    out_path.write_text(_strip_lone_surrogates(html), encoding="utf-8")
    print(f"Wrote dedicated Tesla Narrative page: {out_path}")
    return out_path


def _load_narrative_data(slug):
    """Load a memory-enabled show's narrative tracker for its public page."""
    import json
    from engine import show_memory
    mcfg = show_memory.get_config(slug)
    if mcfg is None:
        return None
    tracker_path = ROOT / "digests" / slug / mcfg.narrative_filename
    if not tracker_path.exists():
        return None
    try:
        data = json.loads(tracker_path.read_text(encoding="utf-8"))
        return {
            "available": True,
            "programs": data.get("programs", {}),
            "last_updated": data.get("last_updated", ""),
        }
    except Exception:
        return None


def generate_narrative_page(slug, *, dry_run=False):
    """Generate the public Narrative Tracker page for a memory-enabled show.

    Generic counterpart to generate_tesla_narrative_page (Tesla keeps its own,
    richer page). No-ops cleanly when the show has no memory config or no
    committed tracker yet.
    """
    from engine import show_memory
    cfg = NETWORK_SHOWS.get(slug)
    mcfg = show_memory.get_config(slug)
    if cfg is None or mcfg is None:
        return None
    narrative_data = _load_narrative_data(slug)
    if not narrative_data:
        return None

    env = _get_jinja_env()
    template = env.get_template("narrative_page.html.j2")
    context = {
        "narrative": narrative_data,
        "show_name": cfg["name"],
        "show_slug": slug,
        "x_account": cfg.get("x_account") or "",
        "brand_color": cfg.get("brand_color", ""),
        "source_path": f"digests/{slug}/{mcfg.narrative_filename}",
        "page_title": f"{cfg['name']} — Narrative Tracker | Nerra Network",
        "meta_description": (
            f"The ongoing storylines {cfg['name']} tracks over time — current status, "
            "key open questions, and real progress across episodes."
        ),
        "og_image": cfg.get("podcast_image", ""),
        "path_prefix": "",
        "is_russian": False,
        "t": {
            "nav_shows": "Shows", "nav_blog": "Blog", "all_blog_posts": "All Blog Posts",
            "show_blog_suffix": "Blog", "nav_start_here": "Start Here", "nav_listen": "How to Listen",
            "nav_about": "About", "nav_player": "Player", "nav_home": "Home",
            "footer_network_status": "Network Status",
        },
        "all_shows": _build_all_shows_list(),
    }
    html = template.render(**context)
    out_path = ROOT / cfg["show_page"].replace(".html", "-narrative.html")
    if dry_run:
        print(f"[dry-run] Would write {out_path}")
        return out_path
    out_path.write_text(_strip_lone_surrogates(html), encoding="utf-8")
    print(f"Wrote narrative page: {out_path}")
    return out_path


def generate_spacex_dashboard(*, dry_run=False):
    """Render the SpaceX Launch Dashboard (spacex-dashboard.html).

    A standalone themed page with a live next-launch countdown, time
    since last launch, launch-cadence chart, SPCX price, and the upcoming
    manifest. All data is read client-side from same-origin caches
    (``api/spacex_launches.json`` + ``api/spcx.json``) with a live
    Launch Library 2 fallback, so the page itself carries no data and
    regenerates cheaply on every site build.
    """
    cfg = NETWORK_SHOWS.get("spacex")
    if cfg is None:
        return None
    env = _get_jinja_env()
    template = env.get_template("spacex_dashboard.html.j2")
    context = {
        "path_prefix": "",
        "page_lang": "en",
        "show_name": "SpaceX Daily",
        "page_title": "SpaceX Launch Dashboard | Nerra Network",
        "meta_description": (
            "Live SpaceX launch dashboard — countdown to the next launch, time "
            "since the last one, launch cadence, the upcoming manifest, and the "
            "SPCX market picture. The companion to the SpaceX Daily podcast."
        ),
        "theme_color": cfg.get("brand_color", "#1A5CFF"),
        "brand_color": cfg.get("brand_color", "#1A5CFF"),
        "canonical_url": f"{GITHUB_RAW}/spacex-dashboard.html",
        "og_image": f"{GITHUB_RAW}/{_url_encode_image(cfg['podcast_image'])}",
        "rss_url": f"{cfg['rss_file']}",
        "t": _NAV_T,
        "all_shows": _build_all_shows_list(),
    }
    html = template.render(**context)
    out_path = ROOT / "spacex-dashboard.html"
    if dry_run:
        print(f"[dry-run] Would write {out_path} ({len(html):,} bytes)")
        return out_path
    out_path.write_text(_strip_lone_surrogates(html), encoding="utf-8")
    print(f"Wrote {out_path} ({len(html):,} bytes)")
    return out_path


def generate_tesla_dashboard(*, dry_run=False):
    """Render the Tesla data dashboard (tesla-dashboard.html).

    Live TSLA market data + a 1-year price chart are read client-side from
    ``api/tesla_dashboard.json``; the curated operating metrics
    (deliveries, energy storage, milestones) are baked in from
    ``site/data/tesla_metrics.json`` at generation time, so the page is
    cheap to regenerate and grows as the operator appends new years.
    """
    cfg = NETWORK_SHOWS.get("tesla")
    if cfg is None:
        return None
    metrics = {}
    try:
        import json as _json
        mp = ROOT / "site" / "data" / "tesla_metrics.json"
        if mp.exists():
            metrics = _json.loads(mp.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Warning: could not load tesla_metrics.json: {exc}")
    env = _get_jinja_env()
    template = env.get_template("tesla_dashboard.html.j2")
    context = {
        "path_prefix": "",
        "page_lang": "en",
        "show_name": "Tesla Shorts Time",
        "page_title": "Tesla Dashboard — TSLA, Deliveries & Energy | Nerra Network",
        "meta_description": (
            "Live Tesla dashboard — TSLA price and 1-year chart, market cap and "
            "52-week range, plus annual vehicle deliveries and energy-storage "
            "deployments. The data companion to the Tesla Shorts Time podcast."
        ),
        "theme_color": cfg.get("brand_color", "#E31937"),
        "brand_color": cfg.get("brand_color", "#E31937"),
        "canonical_url": f"{GITHUB_RAW}/tesla-dashboard.html",
        "og_image": f"{GITHUB_RAW}/{_url_encode_image(cfg['podcast_image'])}",
        "rss_url": f"{cfg['rss_file']}",
        "deliveries_annual": metrics.get("deliveries_annual", []),
        "deliveries_quarterly": metrics.get("deliveries_quarterly", []),
        "energy_storage_annual_gwh": metrics.get("energy_storage_annual_gwh", []),
        "supercharger_connectors_annual": metrics.get("supercharger_connectors_annual", []),
        "highlights": metrics.get("highlights", []),
        "t": _NAV_T,
        "all_shows": _build_all_shows_list(),
    }
    html = template.render(**context)
    out_path = ROOT / "tesla-dashboard.html"
    if dry_run:
        print(f"[dry-run] Would write {out_path} ({len(html):,} bytes)")
        return out_path
    out_path.write_text(_strip_lone_surrogates(html), encoding="utf-8")
    print(f"Wrote {out_path} ({len(html):,} bytes)")
    return out_path


def generate_all_narrative_pages(*, dry_run=False):
    """Generate narrative pages for every memory-configured show (except Tesla,
    which has its own dedicated generator)."""
    from engine import show_memory
    for slug in show_memory.SHOW_MEMORY_CONFIGS:
        generate_narrative_page(slug, dry_run=dry_run)


def generate_show_page(slug, *, dry_run=False):
    """Render and write a show page for a single show."""
    cfg = NETWORK_SHOWS[slug]
    env = _get_jinja_env()
    template = env.get_template("show_page.html.j2")

    podcast_image_url = cfg["podcast_image"]

    # Build related show info for cross-promotion
    related_show_data = None
    related_slug = cfg.get("related_show")
    if related_slug and related_slug in NETWORK_SHOWS:
        rel = NETWORK_SHOWS[related_slug]
        related_show_data = {
            "name": rel["name"],
            "slug": rel["slug"],
            "show_page": rel["show_page"],
            "podcast_image": rel["podcast_image"],
            "tagline": rel["tagline"],
            "reason": cfg.get("related_reason", ""),
        }

    prefix = _path_prefix(cfg["show_page"])

    # Special MIT performance & learning transparency (strong recursive loop)
    mit_performance = None
    if slug == "modern_investing":
        try:
            import json as _json
            tracker_path = ROOT / "digests" / "modern_investing" / "investment_tracker.json"
            if tracker_path.exists():
                tracker = _json.loads(tracker_path.read_text(encoding="utf-8"))
                summary = tracker.get("summary", {})
                mit_performance = {
                    "cumulative_alpha_vs_nasdaq": summary.get("cumulative_alpha_vs_nasdaq", 0.0),
                    "total_trades": summary.get("total_trades", 0),
                    "win_rate": summary.get("win_rate", 0.0),
                    "last_updated": tracker.get("last_updated", ""),
                    "derived_principles": tracker.get("derived_principles", []),
                    "confidence_stats": tracker.get("confidence_calibration", {}),
                }
        except Exception as e:
            print(f"Warning: could not load MIT performance tracker: {e}")

    # Collect latest blog post metadata for the show page
    latest_blog_posts = []
    try:
        from engine.blog import extract_blog_metadata
        digest_dir = ROOT / "digests" / _SHOW_DIRS.get(slug, slug)
        if digest_dir.exists():
            seen_eps: dict[int, dict] = {}
            for md_file in sorted(digest_dir.glob("*.md")):
                md_text = md_file.read_text(encoding="utf-8")
                meta = extract_blog_metadata(md_text, slug, md_file.name, file_path=md_file)
                ep = meta["episode_num"]
                if ep in seen_eps:
                    if md_file.name > seen_eps[ep]["filename"]:
                        seen_eps[ep] = meta
                else:
                    seen_eps[ep] = meta
            all_posts = sorted(seen_eps.values(),
                               key=lambda m: m.get("episode_num", 0),
                               reverse=True)
            latest_blog_posts = all_posts[:3]
    except Exception as e:
        print(f"Warning: could not collect blog posts for show page: {e}")

    # Collect latest episodes from RSS for static rendering
    static_episodes = []
    try:
        import xml.etree.ElementTree as ET
        from email.utils import parsedate_to_datetime
        rss_path = ROOT / cfg["rss_file"]
        if rss_path.exists():
            tree = ET.parse(rss_path)
            root_el = tree.getroot()
            items = root_el.findall(".//item")
            for it in items:
                title = it.findtext("title", "Episode")
                pub_date_str = it.findtext("pubDate", "")
                enclosure = it.find("enclosure")
                audio_url = enclosure.get("url", "") if enclosure is not None else ""
                pub_date = None
                if pub_date_str:
                    try:
                        pub_date = parsedate_to_datetime(pub_date_str)
                    except Exception:
                        pass
                static_episodes.append({
                    "title": title,
                    "pub_date": pub_date,
                    "pub_date_str": pub_date_str,
                    "date_display": pub_date.strftime("%a, %b %d, %Y") if pub_date else "",
                    "audio_url": audio_url,
                })
            # Sort newest first
            static_episodes.sort(
                key=lambda e: e["pub_date"] or __import__("datetime").datetime.min.replace(
                    tzinfo=__import__("datetime").timezone.utc),
                reverse=True,
            )
            static_episodes = static_episodes[:12]
    except Exception as e:
        print(f"Warning: could not collect episodes from RSS for {slug}: {e}")

    # Quick-win dynamic metadata (May 2026 review): inject freshest episode title/hook
    # into page_title and meta description so social cards + search snippets reflect
    # the current episode instead of static NETWORK_SHOWS text. RSS parse already
    # happens above for the episodes rail; we just reuse the first item.
    latest_episode_title = None
    dynamic_meta_description = cfg.get("meta_description", "")
    if static_episodes:
        latest_episode_title = static_episodes[0].get("title")
        if latest_episode_title:
            # Keep original meta but lead with the fresh episode for better CTR/SEO
            dynamic_meta_description = f"Latest: {latest_episode_title}. {cfg.get('meta_description', '')}".strip()
            # Page title becomes "Show — Latest Hook Snippet | Nerra Network" (safe length)
            hook_snippet = latest_episode_title.split(":", 1)[-1].strip() if ":" in latest_episode_title else latest_episode_title
            if len(hook_snippet) > 70:
                hook_snippet = hook_snippet[:67] + "…"
            page_title = f"{cfg['name']} — {hook_snippet} | Nerra Network"

    # Modern Investing: pull the mock-trade performance block from
    # api/dashboard.json if it's already been generated this run (normal
    # CI flow), or compute it on the fly as a fallback (dev / dry-run).
    performance_data = None
    if slug == "modern_investing":
        performance_data = _load_mit_performance_data()

    is_russian = slug in ("finansy_prosto", "privet_russian")

    yt_meta = _read_show_youtube(slug)
    # Phase 2 gallery: enable the embedded per-show gallery section
    # only on shows that *also* use Grok Imagine for their YouTube
    # slideshow. The Phase 1 gallery uploader is wired exclusively
    # into the Grok Imagine code path in run_show.py; Pexels-sourced
    # slideshows are stock photography and don't land in the gallery
    # bucket — embedding the section on those pages would render an
    # empty state forever. Switching a show from `image_provider:
    # pexels` to `grok` (or `hybrid`) in its YAML opts it in.
    image_provider = _read_show_image_provider(slug)
    gallery_enabled = (
        bool(yt_meta.get("youtube_enabled"))
        and image_provider in ("grok", "hybrid")
    )

    # Quick-win (May 2026 review): dynamic metadata from the RSS we already
    # parsed for the episodes rail. Makes <title>, meta description, and OG
    # cards reflect the current episode hook instead of static NETWORK_SHOWS text.
    page_title = f"{cfg['name']} | Nerra Network"
    meta_description = cfg.get("meta_description", "")
    latest_episode_title = static_episodes[0]["title"] if static_episodes else None
    if latest_episode_title:
        hook_snippet = latest_episode_title.split(":", 1)[-1].strip() if ":" in latest_episode_title else latest_episode_title
        if len(hook_snippet) > 68:
            hook_snippet = hook_snippet[:65] + "…"
        page_title = f"{cfg['name']} — {hook_snippet} | Nerra Network"
        meta_description = f"Latest: {latest_episode_title}. {cfg.get('meta_description', '')}".strip()

    # Phase 3: link to the show's public narrative tracker page when it has one
    # (Tesla has a dedicated page; other shows use the generic generator).
    from engine import show_memory as _sm
    if slug == "tesla":
        narrative_page_url = "tesla-narrative.html"
    elif _sm.get_config(slug) is not None:
        narrative_page_url = cfg["show_page"].replace(".html", "-narrative.html")
    else:
        narrative_page_url = ""

    # Live stock-price pill (Tesla + SpaceX). Each show's pipeline hook
    # writes a same-origin api/<ticker>.json the page JS reads first, with
    # a Yahoo-Finance CORS-proxy fallback. SPCX joined when SpaceX IPO'd
    # June 2026.
    stock_widget = _STOCK_WIDGETS.get(slug)

    context = {
        **cfg,
        "narrative_page_url": narrative_page_url,
        "path_prefix": prefix,
        "show_name": cfg["name"],
        "show_slug": cfg["slug"],
        "stock_widget": stock_widget,
        "show_description": cfg.get("about_text", cfg["description"]),
        "page_title": page_title,
        "meta_description": meta_description,  # override the static one from **cfg
        "latest_episode_title": latest_episode_title,
        "podcast_image_url": podcast_image_url,
        "og_image": f"{GITHUB_RAW}/{_url_encode_image(cfg['podcast_image'])}",
        "show_color": cfg["brand_color"],
        "show_color_dark": cfg.get("brand_color_dark", cfg["brand_color"]),
        "canonical_url": f"{GITHUB_RAW}/{cfg['show_page']}",
        "schema_web_feed": f"{GITHUB_RAW}/{cfg['rss_file']}",
        "schema_image_url": f"{GITHUB_RAW}/{cfg['podcast_image'].lstrip('/')}",
        "rss_url": f"{prefix}{cfg['rss_file']}",
        "language_feeds": _collect_language_feeds(cfg["rss_file"], prefix),
        "related_show": related_show_data,
        "blog_page": f"blog/{cfg['slug']}/index.html",
        "latest_blog_posts": latest_blog_posts,
        "static_episodes": static_episodes,
        "newsletter_tag": _newsletter_tag_for_slug(cfg["slug"], cfg["name"]),
        "all_shows": _build_all_shows_list(),
        "performance_data": performance_data,
        "page_lang": "ru" if is_russian else "en",
        "hreflang_self": f"ru-{cfg['slug']}" if is_russian else "en",
        # Per-show embedded gallery (Phase 2).
        "gallery_enabled": gallery_enabled,
        "section_id": "gallery",
        "section_title": "Episode gallery",
        "section_intro": (
            f"AI-generated visuals from recent {cfg['name']} episodes. "
            "Click any image for a larger view; “Show prompt” "
            "reveals the text the image was generated from."
        ),
        "page_size": 24,
        "hide_controls": True,
        **yt_meta,
    }

    html = template.render(**context)

    out_path = ROOT / cfg["show_page"]
    if dry_run:
        print(f"[dry-run] Would write {out_path} ({len(html):,} bytes)")
        return None

    out_path.write_text(_strip_lone_surrogates(html), encoding="utf-8")
    print(f"Wrote {out_path} ({len(html):,} bytes)")
    return out_path


def generate_all_show_pages(*, dry_run=False):
    """Generate show pages for every show."""
    paths = []
    for slug in NETWORK_SHOWS:
        result = generate_show_page(slug, dry_run=dry_run)
        if result:
            paths.append(result)

    # Dedicated MIT Performance & Lessons page (best-in-class transparency)
    mit_result = generate_mit_performance_page(dry_run=dry_run)
    if mit_result:
        paths.append(mit_result)

    # Tesla Narrative Tracker page (recursive memory + transparency)
    if "tesla" in NETWORK_SHOWS:
        tesla_narrative = generate_tesla_narrative_page(dry_run=dry_run)
        if tesla_narrative:
            paths.append(tesla_narrative)

    # Phase 3: narrative pages for the other memory-enabled shows.
    from engine import show_memory
    for slug in show_memory.SHOW_MEMORY_CONFIGS:
        result = generate_narrative_page(slug, dry_run=dry_run)
        if result:
            paths.append(result)

    return paths


# ---------------------------------------------------------------------------
# Network landing page
# ---------------------------------------------------------------------------

def generate_network_page(*, dry_run=False):
    """Render and write the network landing page."""
    env = _get_jinja_env()
    template = env.get_template("network_page.html.j2")

    # Collect 6 most recent blog posts across all shows for the landing page
    latest_blog_posts = []
    try:
        from engine.blog import extract_blog_metadata
        from datetime import date as _date, datetime as _datetime

        all_posts = []
        for slug in NETWORK_SHOWS:
            digest_dir = ROOT / "digests" / _SHOW_DIRS.get(slug, slug)
            if not digest_dir.exists():
                continue
            seen_eps: dict[int, dict] = {}
            for md_file in sorted(digest_dir.glob("*.md")):
                md_text = md_file.read_text(encoding="utf-8")
                meta = extract_blog_metadata(md_text, slug, md_file.name, file_path=md_file)
                ep = meta["episode_num"]
                if ep in seen_eps:
                    if md_file.name > seen_eps[ep]["filename"]:
                        seen_eps[ep] = meta
                else:
                    seen_eps[ep] = meta
            for meta in seen_eps.values():
                cfg_show = NETWORK_SHOWS.get(slug, {})
                meta["show_name"] = cfg_show.get("name", slug)
                meta["show_color"] = cfg_show.get("brand_color", "#6B47FF")
            all_posts.extend(seen_eps.values())

        def _sort_key(p):
            d = p.get("date_obj")
            if isinstance(d, _datetime):
                return d.date()
            if isinstance(d, _date):
                return d
            return _date.min

        all_posts.sort(key=_sort_key, reverse=True)
        latest_blog_posts = all_posts[:6]
    except Exception as e:
        print(f"Warning: could not collect blog posts for network page: {e}")

    # Collect latest episodes from RSS feeds (static rendering)
    latest_episodes = []
    try:
        import xml.etree.ElementTree as ET
        from email.utils import parsedate_to_datetime

        for slug, cfg in NETWORK_SHOWS.items():
            rss_path = ROOT / cfg["rss_file"]
            if not rss_path.exists():
                continue
            try:
                tree = ET.parse(rss_path)
                root_el = tree.getroot()
                items = root_el.findall(".//item")
                if not items:
                    continue
                # Find newest item by pubDate
                best_item = None
                best_date = None
                for it in items:
                    pds = it.findtext("pubDate", "")
                    pd = None
                    if pds:
                        try:
                            pd = parsedate_to_datetime(pds)
                        except Exception:
                            pass
                    if best_item is None or (pd and (best_date is None or pd > best_date)):
                        best_item = it
                        best_date = pd
                if best_item is None:
                    continue
                title = best_item.findtext("title", "Episode")
                pub_date_str = best_item.findtext("pubDate", "")
                enclosure = best_item.find("enclosure")
                audio_url = enclosure.get("url", "") if enclosure is not None else ""
                latest_episodes.append({
                    "show_name": cfg["name"],
                    "show_page": cfg["show_page"],
                    "brand_color": cfg["brand_color"],
                    "title": title,
                    "pub_date_str": pub_date_str,
                    "pub_date": best_date,
                    "audio_url": audio_url,
                })
            except Exception:
                continue

        from datetime import datetime as _dt, timezone as _tz
        _epoch = _dt(1970, 1, 1, tzinfo=_tz.utc)
        def _ep_sort(e):
            d = e.get("pub_date")
            if d is None:
                return _epoch
            if d.tzinfo is None:
                return d.replace(tzinfo=_tz.utc)
            return d
        latest_episodes.sort(key=_ep_sort, reverse=True)
        latest_episodes = latest_episodes[:10]
        # Format dates for display
        for ep in latest_episodes:
            d = ep.get("pub_date")
            if d:
                ep["date_display"] = d.strftime("%a, %b %d, %Y")
            else:
                ep["date_display"] = ""
    except Exception as e:
        print(f"Warning: could not collect latest episodes from RSS: {e}")

    # "Most played this week" rail — fed by the nightly OP3 stats fetch
    # (scripts/fetch_op3_stats.py). Renders nothing when the file is
    # missing/empty (OP3_API_TOKEN not configured yet).
    popular_episodes = []
    try:
        _popular_path = ROOT / "site" / "data" / "popular_episodes.json"
        if _popular_path.exists():
            popular_episodes = json.loads(
                _popular_path.read_text(encoding="utf-8")) or []
            popular_episodes = [
                ep for ep in popular_episodes if ep.get("audio_url")
            ][:6]
    except Exception as e:
        print(f"Warning: could not load popular episodes: {e}")

    # Newsletter social proof — fed by the nightly Buttondown stats fetch
    # (scripts/fetch_buttondown_stats.py). Hidden below the threshold so a
    # small number never reads as anti-proof; rounded down to the nearest
    # 10 so it doesn't read as fake-precise.
    newsletter_subscriber_count = None
    try:
        _bd_path = ROOT / "api" / "buttondown_stats.json"
        if _bd_path.exists():
            _count = (json.loads(_bd_path.read_text(encoding="utf-8"))
                      or {}).get("subscriber_count")
            if isinstance(_count, int) and _count >= MIN_SOCIAL_PROOF_SUBSCRIBERS:
                newsletter_subscriber_count = (_count // 10) * 10
    except Exception as e:
        print(f"Warning: could not load newsletter stats: {e}")

    context = {
        "path_prefix": "",
        "page_title": f"Nerra Network | {len(NETWORK_SHOWS)} Daily Shows",
        "meta_description": f"Nerra Network — {len(NETWORK_SHOWS)} daily podcasts keeping you informed. Tesla, world news, space, science, environment, AI, modern investing, first-principles thinking, narrative case studies, Russian finance, and language learning. Independent, daily, free.",
        "meta_keywords": "podcast network, daily podcasts, Nerra Network, Tesla, space, science, AI, environment, history, unintended consequences",
        "theme_color": "#6B47FF",
        "og_image": f"{GITHUB_RAW}/assets/og-preview.png",
        "canonical_url": f"{GITHUB_RAW}/index.html",
        "rss_url": "network.rss",
        "all_shows": _build_all_shows_list(),
        "latest_blog_posts": latest_blog_posts,
        "latest_episodes": latest_episodes,
        "popular_episodes": popular_episodes,
        "newsletter_subscriber_count": newsletter_subscriber_count,
        "emit_bilingual_hreflang": True,
        "total_episodes": _count_total_episodes(),
    }

    html = template.render(**context)

    out_path = ROOT / "index.html"
    if dry_run:
        print(f"[dry-run] Would write {out_path} ({len(html):,} bytes)")
        return None

    out_path.write_text(_strip_lone_surrogates(html), encoding="utf-8")
    print(f"Wrote {out_path} ({len(html):,} bytes)")
    return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
# Blog pages
# ---------------------------------------------------------------------------

# Mapping from show slug to digest directory name.  Only "tesla" differs
# (slug "tesla" → directory "tesla_shorts_time").  Used by all blog and
# sitemap functions.  Single source of truth — do NOT duplicate elsewhere.
_SHOW_DIRS = {
    "tesla": "tesla_shorts_time",
    "omni_view": "omni_view",
    "fascinating_frontiers": "fascinating_frontiers",
    "planetterrian": "planetterrian",
    "env_intel": "env_intel",
    "models_agents": "models_agents",
    "models_agents_beginners": "models_agents_beginners",
    "finansy_prosto": "finansy_prosto",
    "modern_investing": "modern_investing",
    "privet_russian": "privet_russian",
    "unintended_consequences": "unintended_consequences",
}


def _pick_cross_show_related(slug, cross_show_posts, *, want=3):
    """Pick up to *want* cross-show posts for a blog post's rec section.

    The show's curated sibling (``NETWORK_SHOWS[slug]["related_show"]``)
    always takes the first slot when it has a recent post, so the
    on-brand recommendation is deterministic; remaining slots are
    sampled from the latest cross-show pool.
    """
    if not cross_show_posts:
        return []
    import random
    related = []
    candidates = [p for p in cross_show_posts if p.get("show_slug") != slug]
    curated_slug = (NETWORK_SHOWS.get(slug) or {}).get("related_show")
    curated = next(
        (p for p in candidates if p.get("show_slug") == curated_slug),
        None,
    )
    if curated is not None:
        related.append(curated)
        candidates = [p for p in candidates if p is not curated]
    remaining = want - len(related)
    if len(candidates) <= remaining:
        related.extend(candidates[:remaining])
    else:
        related.extend(random.sample(candidates[:12], remaining))
    return related


def _attach_translations(slug, cfg, metas):
    """Merge each episode's summaries record (audio URL + per-language
    translation tracks, June 2026 multilingual) into its blog metadata.

    The episode ``.md`` carries neither the audio URL nor the translations;
    they live in the show's ``summaries_<show>.json``. English stays canonical
    — episodes with no ``translations`` key render exactly as before. Used by
    both the blog-post and blog-index generators so language badges + the
    inline switcher appear consistently.
    """
    records_by_ep: dict[int, dict] = {}
    json_path = cfg.get("json_path")
    if json_path:
        try:
            from engine.summaries_io import load_summaries
            _, recs = load_summaries(ROOT / json_path)
            for r in recs:
                ep = r.get("episode_num")
                if isinstance(ep, int):
                    records_by_ep[ep] = r
        except FileNotFoundError:
            return
        except Exception as exc:  # noqa: BLE001 — never block HTML gen
            print(f"  Warning: could not load summaries for {slug}: {exc}")
            return
    for meta in metas:
        rec = records_by_ep.get(meta.get("episode_num"))
        if not rec:
            continue
        if not meta.get("audio_url"):
            meta["audio_url"] = rec.get("audio_url", "")
        tr = rec.get("translations")
        if isinstance(tr, dict) and tr:
            meta["translations"] = tr


def generate_blog_posts(slug, *, dry_run=False, cross_show_posts=None):
    """Generate blog post HTML pages for all episodes of a show.

    *cross_show_posts*: optional list of dicts from other shows for
    "You might also like" recommendations on each post.

    Returns list of (metadata_dict, output_path) tuples.
    """
    from engine.blog import (
        extract_blog_metadata,
        generate_blog_post_html,
    )

    cfg = NETWORK_SHOWS[slug]
    env = _get_jinja_env()

    digest_dir = ROOT / "digests" / _SHOW_DIRS.get(slug, slug)
    if not digest_dir.exists():
        print(f"Warning: digest dir {digest_dir} not found for {slug}")
        return []

    md_files = sorted(digest_dir.glob("*.md"))
    if not md_files:
        print(f"No markdown files found in {digest_dir}")
        return []

    # Extract metadata from all files first
    all_meta = []
    for md_file in md_files:
        md_text = md_file.read_text(encoding="utf-8")
        meta = extract_blog_metadata(md_text, slug, md_file.name, file_path=md_file)
        meta["_md_path"] = md_file
        all_meta.append(meta)

    # Deduplicate by episode number — keep the file with the latest filename
    # (newer date in filename wins, e.g. Ep413_20260322 over Ep413_20260320)
    seen_eps: dict[int, dict] = {}
    for meta in all_meta:
        ep = meta["episode_num"]
        if ep in seen_eps:
            existing = seen_eps[ep]
            if meta["_md_path"].name > existing["_md_path"].name:
                print(f"  Warning: duplicate ep{ep} — keeping {meta['_md_path'].name} over {existing['_md_path'].name}")
                seen_eps[ep] = meta
            else:
                print(f"  Warning: duplicate ep{ep} — keeping {existing['_md_path'].name} over {meta['_md_path'].name}")
        else:
            seen_eps[ep] = meta
    all_meta = list(seen_eps.values())

    # Sort by episode number
    all_meta.sort(key=lambda m: m["episode_num"])

    _attach_translations(slug, cfg, all_meta)

    blog_dir = ROOT / "blog" / slug
    results = []

    for i, meta in enumerate(all_meta):
        prev_post = all_meta[i - 1] if i > 0 else None
        next_post = all_meta[i + 1] if i < len(all_meta) - 1 else None

        md_text = meta["_md_path"].read_text(encoding="utf-8")

        # Pick up to 3 recent posts from other shows for cross-show recs
        _related = _pick_cross_show_related(slug, cross_show_posts)

        html = generate_blog_post_html(
            md_text, meta, cfg, env,
            prev_post=prev_post,
            next_post=next_post,
            related_posts=_related,
        )

        ep_num = meta["episode_num"]
        out_path = blog_dir / f"ep{ep_num:03d}.html"

        if dry_run:
            print(f"[dry-run] Would write {out_path} ({len(html):,} bytes)")
        else:
            blog_dir.mkdir(parents=True, exist_ok=True)
            out_path.write_text(_strip_lone_surrogates(html), encoding="utf-8")
            print(f"Wrote {out_path}")

        results.append((meta, out_path))

    return results


def generate_blog_index(slug, *, dry_run=False, posts=None):
    """Generate a blog index page for a show.

    If *posts* is None, scans the digest directory for metadata.
    """
    from engine.blog import (
        extract_blog_metadata,
        generate_blog_index_html,
    )

    cfg = NETWORK_SHOWS[slug]
    env = _get_jinja_env()

    if posts is None:
        digest_dir = ROOT / "digests" / _SHOW_DIRS.get(slug, slug)
        posts = []
        if digest_dir.exists():
            seen_eps: dict[int, dict] = {}
            for md_file in sorted(digest_dir.glob("*.md")):
                md_text = md_file.read_text(encoding="utf-8")
                meta = extract_blog_metadata(md_text, slug, md_file.name, file_path=md_file)
                ep = meta["episode_num"]
                if ep in seen_eps:
                    if md_file.name > seen_eps[ep]["filename"]:
                        seen_eps[ep] = meta
                else:
                    seen_eps[ep] = meta
            posts = list(seen_eps.values())
            _attach_translations(slug, cfg, posts)

    # Sort newest first for index display
    posts_sorted = sorted(posts, key=lambda m: m.get("episode_num", 0), reverse=True)

    html = generate_blog_index_html(posts_sorted, cfg, env)

    blog_dir = ROOT / "blog" / slug
    out_path = blog_dir / "index.html"

    if dry_run:
        print(f"[dry-run] Would write {out_path} ({len(html):,} bytes)")
        return None

    blog_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_strip_lone_surrogates(html), encoding="utf-8")
    print(f"Wrote {out_path}")
    return out_path


def generate_network_blog_index(*, dry_run=False, all_posts=None):
    """Generate the network-wide blog index page at blog/index.html.

    If *all_posts* is None, collects posts from all shows by scanning
    their digest directories.
    """
    from engine.blog import (
        extract_blog_metadata,
        generate_network_blog_index_html,
    )

    env = _get_jinja_env()

    if all_posts is None:
        all_posts = []
        for slug in NETWORK_SHOWS:
            digest_dir = ROOT / "digests" / _SHOW_DIRS.get(slug, slug)
            if not digest_dir.exists():
                continue
            cfg = NETWORK_SHOWS[slug]
            seen_eps: dict[int, dict] = {}
            for md_file in sorted(digest_dir.glob("*.md")):
                md_text = md_file.read_text(encoding="utf-8")
                meta = extract_blog_metadata(md_text, slug, md_file.name, file_path=md_file)
                # Fallback: use show name when digest has no title heading
                if not meta.get("title"):
                    meta["title"] = cfg["name"]
                ep = meta["episode_num"]
                if ep in seen_eps:
                    if md_file.name > seen_eps[ep]["filename"]:
                        seen_eps[ep] = meta
                else:
                    seen_eps[ep] = meta
            all_posts.extend(seen_eps.values())

    html = generate_network_blog_index_html(all_posts, NETWORK_SHOWS, env)

    out_path = ROOT / "blog" / "index.html"

    if dry_run:
        print(f"[dry-run] Would write {out_path} ({len(html):,} bytes)")
        return None

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_strip_lone_surrogates(html), encoding="utf-8")
    print(f"Wrote {out_path}")
    return out_path


def generate_all_blogs(*, dry_run=False):
    """Generate blog posts and index pages for every show, plus network index."""
    from engine.blog import extract_blog_metadata

    # First pass: collect recent posts from all shows for cross-show recs
    _cross_show_posts: list[dict] = []
    for slug, cfg in NETWORK_SHOWS.items():
        digest_dir = ROOT / "digests" / _SHOW_DIRS.get(slug, slug)
        if not digest_dir.exists():
            continue
        md_files = sorted(digest_dir.glob("*.md"))[-6:]  # Last 6 episodes per show
        for md_file in md_files:
            try:
                md_text = md_file.read_text(encoding="utf-8")
                meta = extract_blog_metadata(md_text, slug, md_file.name, file_path=md_file)
                _cross_show_posts.append({
                    "show_slug": slug,
                    "show_name": cfg["name"],
                    "show_color": cfg["brand_color"],
                    "title": meta.get("title", cfg["name"]),
                    "hook": meta.get("hook", ""),
                    "episode_num": meta.get("episode_num", 0),
                    "url": f"../../blog/{slug}/ep{meta.get('episode_num', 0):03d}.html",
                    "date": meta.get("date", ""),
                })
            except Exception:
                pass
    # Sort by date descending so most recent posts get picked
    _cross_show_posts.sort(key=lambda p: p.get("date", ""), reverse=True)

    all_posts = []

    for slug in NETWORK_SHOWS:
        print(f"\n--- Blog: {NETWORK_SHOWS[slug]['name']} ---")
        results = generate_blog_posts(slug, dry_run=dry_run, cross_show_posts=_cross_show_posts)
        posts = [meta for meta, _ in results]
        generate_blog_index(slug, dry_run=dry_run, posts=posts)
        all_posts.extend(posts)

    # Generate network-wide blog index
    print("\n--- Network Blog Index ---")
    generate_network_blog_index(dry_run=dry_run, all_posts=all_posts)

    if not dry_run:
        from engine.blog import regenerate_network_blog_rss, regenerate_show_blog_rss
        for slug, cfg in NETWORK_SHOWS.items():
            regenerate_show_blog_rss(
                slug, cfg["name"], ROOT, channel_image=cfg.get("podcast_image", ""),
            )
        regenerate_network_blog_rss(ROOT, NETWORK_SHOWS)
        print("Blog RSS feeds regenerated for all shows")


# ---------------------------------------------------------------------------
# Sitemap generation
# ---------------------------------------------------------------------------


def generate_sitemap(*, dry_run=False):
    """Generate sitemap.xml with all pages on the site."""
    from xml.sax.saxutils import escape as _esc
    import os
    from datetime import datetime, timezone
    from engine.show_memory import get_config as _sm_get_config

    base = "https://nerranetwork.com"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls: list[tuple[str, str, str]] = []  # (loc, priority, lastmod)

    def _file_lastmod(path):
        """Get file modification date as YYYY-MM-DD."""
        try:
            mtime = os.path.getmtime(path)
            return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            return today

    # ``lastmod`` is per-file modification time wherever possible —
    # Google uses it as a freshness signal. The previous sitemap
    # used ``today`` for everything (build date), defeating the
    # signal because every URL claimed to have changed every day
    # whether it had or not (May 2026 audit Phase 5).
    def _lm_or_today(rel: str) -> str:
        path = ROOT / rel
        return _file_lastmod(path) if path.exists() else today

    # Landing page
    urls.append((f"{base}/", "1.0", _lm_or_today("index.html")))

    # Show pages, summaries pages, blog indices — file mtime reflects
    # when each was last regenerated (typically when a new episode
    # publishes for that show).
    for slug, cfg in NETWORK_SHOWS.items():
        urls.append((f"{base}/{cfg['show_page']}", "0.8",
                     _lm_or_today(cfg["show_page"])))
        urls.append((f"{base}/{cfg['summaries_page']}", "0.7",
                     _lm_or_today(cfg["summaries_page"])))
        urls.append((f"{base}/blog/{slug}/index.html", "0.7",
                     _lm_or_today(f"blog/{slug}/index.html")))
        # Public narrative tracker page (Tesla + Phase 3 memory shows), when present.
        _narr = "tesla-narrative.html" if slug == "tesla" else (
            cfg["show_page"].replace(".html", "-narrative.html")
            if _sm_get_config(slug) else None
        )
        if _narr and (ROOT / _narr).exists():
            urls.append((f"{base}/{_narr}", "0.6", _lm_or_today(_narr)))

    # Network blog hub
    urls.append((f"{base}/blog/index.html", "0.7",
                 _lm_or_today("blog/index.html")))

    # Russian hub
    urls.append((f"{base}/ru/index.html", "0.7",
                 _lm_or_today("ru/index.html")))

    # Legal pages
    for legal in ["privacy-policy.html", "terms-of-service.html", "ai-disclosure.html"]:
        if (ROOT / legal).exists():
            urls.append((f"{base}/{legal}", "0.4", _file_lastmod(ROOT / legal)))

    # Special pages. 404.html is deliberately NOT listed — error pages
    # don't belong in sitemaps (Search Console flags them).
    for extra in ["modern-investing-resources.html", "start-here.html",
                  "about.html", "how-to-listen.html", "faq.html",
                  "press.html", "contact.html", "editorial.html",
                  "gallery.html", "player.html", "data.html",
                  "modern-investing-performance.html",
                  "spacex-dashboard.html", "tesla-dashboard.html"]:
        if (ROOT / extra).exists():
            urls.append((f"{base}/{extra}", "0.5", _file_lastmod(ROOT / extra)))

    # Individual blog posts
    blog_dir = ROOT / "blog"
    if blog_dir.exists():
        for show_dir in sorted(blog_dir.iterdir()):
            if show_dir.is_dir():
                for ep_file in sorted(show_dir.glob("ep*.html")):
                    rel = f"blog/{show_dir.name}/{ep_file.name}"
                    urls.append((f"{base}/{rel}", "0.6", _file_lastmod(ep_file)))

    # Build XML
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, priority, lastmod in urls:
        lines.append(f"  <url>")
        lines.append(f"    <loc>{_esc(loc)}</loc>")
        lines.append(f"    <priority>{priority}</priority>")
        if lastmod:
            lines.append(f"    <lastmod>{_esc(lastmod)}</lastmod>")
        lines.append(f"  </url>")
    lines.append("</urlset>")
    lines.append("")

    xml = "\n".join(lines)

    out_path = ROOT / "sitemap.xml"
    if dry_run:
        print(f"[dry-run] Would write {out_path} ({len(urls)} URLs)")
        return None

    out_path.write_text(_strip_lone_surrogates(xml), encoding="utf-8")
    print(f"Wrote {out_path} ({len(urls)} URLs)")
    return out_path


# ---------------------------------------------------------------------------
# 404 page
# ---------------------------------------------------------------------------

def generate_404_page(*, dry_run=False):
    """Generate a custom 404 error page."""
    env = _get_jinja_env()
    template = env.get_template("404.html.j2")

    context = {
        "path_prefix": "",
        "page_title": "Page Not Found | Nerra Network",
        "meta_description": "The page you're looking for doesn't exist.",
        "meta_keywords": "",
        "theme_color": "#6B47FF",
        "og_image": "",  # Falls back to default in base.html.j2
        "canonical_url": "",
        "show_color": "",
        "show_color_dark": "",
        "all_shows": _build_all_shows_list(),
    }

    html = template.render(**context)
    out_path = ROOT / "404.html"

    if dry_run:
        print(f"[dry-run] Would write {out_path}")
        return None

    out_path.write_text(_strip_lone_surrogates(html), encoding="utf-8")
    print(f"Wrote {out_path}")
    return out_path


def generate_start_here_page(*, dry_run=False):
    """Generate the 'Start Here' guided entry page for new listeners."""
    env = _get_jinja_env()
    template = env.get_template("start_here.html.j2")

    context = {
        "path_prefix": "",
        "page_title": "Start Here | Nerra Network",
        "page_description": "Not sure where to start? Find the perfect show for your interests across AI, news, science, investing, and more.",
        "meta_description": "Find your perfect Nerra Network show. 11 ad-free daily podcasts covering AI, Tesla, world news, science, investing, and more.",
        "meta_keywords": "podcast recommendations, best podcasts, AI podcasts, Tesla podcasts, science podcasts",
        "theme_color": "#6B47FF",
        "og_image": "",
        "canonical_url": "https://nerranetwork.com/start-here.html",
        "show_color": "",
        "show_color_dark": "",
        "all_shows": _build_all_shows_list(),
    }

    html = template.render(**context)
    out_path = ROOT / "start-here.html"

    if dry_run:
        print(f"[dry-run] Would write {out_path}")
        return None

    out_path.write_text(_strip_lone_surrogates(html), encoding="utf-8")
    print(f"Wrote {out_path}")
    return out_path


def _count_total_episodes() -> int:
    """Sum episode counts across all podcast RSS feeds (best-effort, cached)."""
    total = 0
    for cfg in NETWORK_SHOWS.values():
        rss = ROOT / cfg.get("rss_file", "")
        if not rss.exists():
            continue
        try:
            text = rss.read_text(encoding="utf-8", errors="ignore")
            total += text.count("<item>")
        except Exception:
            pass
    return total


def _count_languages() -> int:
    """Count distinct languages across shows (en / ru currently)."""
    langs = set()
    for cfg in NETWORK_SHOWS.values():
        if cfg.get("slug") in ("finansy_prosto", "privet_russian"):
            langs.add("ru")
        else:
            langs.add("en")
    return len(langs)


def generate_data_hub_page(*, dry_run=False):
    """Render the /data.html hub linking every public data dashboard
    (SpaceX, Tesla, Modern Investing performance, gallery) so the audience
    can discover them from one place. Static — no runtime data; the linked
    dashboards read their own same-origin caches client-side."""
    env = _get_jinja_env()
    template = env.get_template("data_hub.html.j2")
    context = {
        "path_prefix": "",
        "page_lang": "en",
        "page_title": "Data & Dashboards | Nerra Network",
        "meta_description": (
            "Live data dashboards from Nerra Network — SpaceX launch countdown "
            "and fleet records, Tesla TSLA price and deliveries, and the Modern "
            "Investing simulated-portfolio performance page."
        ),
        "theme_color": "#6B47FF",
        "og_image": f"{GITHUB_RAW}/assets/og-default.png",
        "canonical_url": f"{GITHUB_RAW}/data.html",
        "t": _NAV_T,
        "all_shows": _build_all_shows_list(),
    }
    html = template.render(**context)
    out_path = ROOT / "data.html"
    if dry_run:
        print(f"[dry-run] Would write {out_path} ({len(html):,} bytes)")
        return out_path
    out_path.write_text(_strip_lone_surrogates(html), encoding="utf-8")
    print(f"Wrote {out_path} ({len(html):,} bytes)")
    return out_path


def generate_gallery_page(*, dry_run=False):
    """Generate the network-wide /gallery.html browse page.

    The page renders an empty mount-point that ``assets/js/gallery.js``
    hydrates client-side from ``site/data/gallery-manifest.json`` (built
    nightly by ``scripts/build_gallery_manifest.py``). All filtering,
    sorting, and lightbox UX is client-side.
    """
    env = _get_jinja_env()
    template = env.get_template("gallery_page.html.j2")

    context = {
        "path_prefix": "",
        "page_title": "Gallery — Nerra Network",
        "page_description": (
            "Every AI-generated visual produced for Nerra Network "
            "episodes. Browse by show, search, and download under "
            "CC BY-SA 4.0."
        ),
        "meta_description": (
            "Browse the Nerra Network image gallery — AI-generated "
            "thumbnails, segment cards, and Shorts art from every "
            "episode, filterable by show and date."
        ),
        "meta_keywords": (
            "Nerra Network gallery, AI generated images, podcast "
            "artwork, Grok Imagine, episode thumbnails"
        ),
        "theme_color": "#6B47FF",
        "og_image": "",
        "canonical_url": "https://nerranetwork.com/gallery.html",
        "show_color": "",
        "show_color_dark": "",
        "all_shows": _build_all_shows_list(),
        # Params for the _gallery_section.html.j2 partial. The hero
        # already has a title so the section itself runs untitled.
        "section_id": "gallery",
        "section_title": "",
        "section_intro": "",
        "show_slug": "",
        "page_size": 60,
        "hide_controls": False,
    }

    html = template.render(**context)
    out_path = ROOT / "gallery.html"

    if dry_run:
        print(f"[dry-run] Would write {out_path}")
        return None

    out_path.write_text(_strip_lone_surrogates(html), encoding="utf-8")
    print(f"Wrote {out_path}")
    return out_path


def generate_about_page(*, dry_run=False):
    """Generate the About page with founder, mission, and network stats."""
    env = _get_jinja_env()
    template = env.get_template("about.html.j2")

    context = {
        "path_prefix": "",
        "page_title": "About — Nerra Network",
        "page_description": "Meet the independent podcast network producing 11 ad-free daily shows on AI, Tesla, investing, space, science, and environmental policy. Based in Vancouver, Canada.",
        "meta_description": f"About Nerra Network — an independent, ad-free podcast network producing {len(NETWORK_SHOWS)} daily shows in Vancouver, Canada. Founded by Patrick Novak.",
        "meta_keywords": "about Nerra Network, Patrick Novak, independent podcast network, Vancouver podcasts, ad-free podcasts",
        "theme_color": "#6B47FF",
        "og_image": "",
        "canonical_url": "https://nerranetwork.com/about.html",
        "show_color": "",
        "show_color_dark": "",
        "all_shows": _build_all_shows_list(),
        # Stats
        "shows_count": len(NETWORK_SHOWS),
        "total_episodes": _count_total_episodes(),
        "languages_count": _count_languages(),
        "founding_date": "2024-07-01",
    }

    html = template.render(**context)
    out_path = ROOT / "about.html"

    if dry_run:
        print(f"[dry-run] Would write {out_path}")
        return None

    out_path.write_text(_strip_lone_surrogates(html), encoding="utf-8")
    print(f"Wrote {out_path}")
    return out_path


def generate_press_page(*, dry_run=False):
    """Generate the press kit / media-resources page."""
    env = _get_jinja_env()
    template = env.get_template("press.html.j2")

    context = {
        "path_prefix": "",
        "page_title": "Press & Media Kit — Nerra Network",
        "page_description": "Media resources for journalists and partners covering Nerra Network. Boilerplate, logo, founder contact, and a complete show directory.",
        "meta_description": "Nerra Network press kit — boilerplate, logo assets, founder contact, and a complete directory of our 11 daily podcast shows.",
        "meta_keywords": "Nerra Network press kit, media resources, podcast press, Patrick Novak, Vancouver podcast",
        "theme_color": "#6B47FF",
        "og_image": "",
        "canonical_url": "https://nerranetwork.com/press.html",
        "show_color": "",
        "show_color_dark": "",
        "all_shows": _build_all_shows_list(),
        "shows_count": len(NETWORK_SHOWS),
        "total_episodes": _count_total_episodes(),
    }

    html = template.render(**context)
    out_path = ROOT / "press.html"

    if dry_run:
        print(f"[dry-run] Would write {out_path}")
        return None

    out_path.write_text(_strip_lone_surrogates(html), encoding="utf-8")
    print(f"Wrote {out_path}")
    return out_path


def generate_editorial_page(*, dry_run=False):
    """Generate ``editorial.html`` — the methodology / editorial-process
    page added in Phase 5 of the May 2026 strategic audit. It's the
    highest-leverage trust artifact for an AI-narrated network because
    listeners can see *how* stories are selected, *how* the LLM is
    constrained, and *how* fallback paths work, separate from the
    AI-disclosure page (which only covers *that* AI is used)."""
    env = _get_jinja_env()
    template = env.get_template("editorial.html.j2")

    context = {
        "path_prefix": "",
        "page_title": "Editorial process — Nerra Network",
        "page_description": "How Nerra Network selects, fact-checks, and produces every episode. The editorial process behind 11 AI-narrated podcasts.",
        "meta_description": "How Nerra Network selects, fact-checks, and produces every episode. The editorial process behind 11 AI-narrated podcasts.",
        "meta_keywords": "Nerra Network editorial, podcast methodology, AI podcast process, how AI podcasts are made",
        "theme_color": "#6B47FF",
        "og_image": "",
        "canonical_url": "https://nerranetwork.com/editorial.html",
        "show_color": "",
        "show_color_dark": "",
        "all_shows": _build_all_shows_list(),
    }

    html = template.render(**context)
    out_path = ROOT / "editorial.html"

    if dry_run:
        print(f"[dry-run] Would write {out_path}")
        return None

    out_path.write_text(_strip_lone_surrogates(html), encoding="utf-8")
    print(f"Wrote {out_path}")
    return out_path


def generate_contact_page(*, dry_run=False):
    """Generate the contact page."""
    env = _get_jinja_env()
    template = env.get_template("contact.html.j2")

    context = {
        "path_prefix": "",
        "page_title": "Contact — Nerra Network",
        "page_description": "Get in touch with Nerra Network. Separate channels for press, partnerships, technical issues, privacy, and general inquiries.",
        "meta_description": "Contact Nerra Network — separate email channels for press, partnerships, technical issues, privacy, and general feedback.",
        "meta_keywords": "contact Nerra Network, press contact, podcast partnership, technical support",
        "theme_color": "#6B47FF",
        "og_image": "",
        "canonical_url": "https://nerranetwork.com/contact.html",
        "show_color": "",
        "show_color_dark": "",
        "all_shows": _build_all_shows_list(),
    }

    html = template.render(**context)
    out_path = ROOT / "contact.html"

    if dry_run:
        print(f"[dry-run] Would write {out_path}")
        return None

    out_path.write_text(_strip_lone_surrogates(html), encoding="utf-8")
    print(f"Wrote {out_path}")
    return out_path


def generate_faq_page(*, dry_run=False):
    """Generate the FAQ page with FAQPage JSON-LD schema."""
    env = _get_jinja_env()
    template = env.get_template("faq.html.j2")

    context = {
        "path_prefix": "",
        "page_title": "FAQ — Nerra Network",
        "page_description": "Common questions about Nerra Network, our shows, our AI-assisted editorial process, and how to support the network.",
        "meta_description": "Nerra Network FAQ — how we use AI, who hosts, when episodes release, how to subscribe and support, and our editorial stance.",
        "meta_keywords": "Nerra Network FAQ, podcast questions, AI podcast disclosure, podcast support",
        "theme_color": "#6B47FF",
        "og_image": "",
        "canonical_url": "https://nerranetwork.com/faq.html",
        "show_color": "",
        "show_color_dark": "",
        "all_shows": _build_all_shows_list(),
    }

    html = template.render(**context)
    out_path = ROOT / "faq.html"

    if dry_run:
        print(f"[dry-run] Would write {out_path}")
        return None

    out_path.write_text(_strip_lone_surrogates(html), encoding="utf-8")
    print(f"Wrote {out_path}")
    return out_path


def generate_how_to_listen_page(*, dry_run=False):
    """Generate the How-to-Listen guide page."""
    env = _get_jinja_env()
    template = env.get_template("how_to_listen.html.j2")

    context = {
        "path_prefix": "",
        "page_title": "How to Listen — Nerra Network",
        "page_description": "Subscribe to Nerra Network shows on Apple Podcasts, Spotify, or any RSS-compatible podcast app. Step-by-step guide for every show.",
        "meta_description": "How to subscribe to Nerra Network podcasts on Apple Podcasts, Spotify, and any RSS-compatible app. Complete show directory included.",
        "meta_keywords": "how to listen, subscribe podcast, Apple Podcasts, Spotify, RSS, Nerra Network",
        "theme_color": "#6B47FF",
        "og_image": "",
        "canonical_url": "https://nerranetwork.com/how-to-listen.html",
        "show_color": "",
        "show_color_dark": "",
        "all_shows": _build_all_shows_list(),
    }

    html = template.render(**context)
    out_path = ROOT / "how-to-listen.html"

    if dry_run:
        print(f"[dry-run] Would write {out_path}")
        return None

    out_path.write_text(_strip_lone_surrogates(html), encoding="utf-8")
    print(f"Wrote {out_path}")
    return out_path


def generate_player_page(*, dry_run=False):
    """Generate the cross-show podcast player page."""
    env = _get_jinja_env()
    template = env.get_template("player_page.html.j2")

    # Build show list for the player's JS config
    player_shows = []
    for cfg in NETWORK_SHOWS.values():
        player_shows.append({
            "slug": cfg["slug"],
            "name": cfg["name"],
            "json_path": cfg["json_path"],
            "podcast_image": cfg["podcast_image"],
            "brand_color": cfg["brand_color"],
        })

    context = {
        "path_prefix": "",
        "page_title": "Player | Nerra Network",
        "meta_description": f"Listen to all Nerra Network shows in one player. Build your queue, reorder episodes, and discover new content across {len(NETWORK_SHOWS)} daily podcasts.",
        "meta_keywords": "podcast player, Nerra Network, queue, playlist",
        "theme_color": "#6B47FF",
        "og_image": None,
        "canonical_url": f"{GITHUB_RAW}/player.html",
        "rss_url": "network.rss",
        "show_color": "",
        "show_color_dark": "",
        "all_shows": _build_all_shows_list(),
        "player_shows": player_shows,
    }

    html = template.render(**context)
    out_path = ROOT / "player.html"

    if dry_run:
        print(f"[dry-run] Would write {out_path}")
        return None

    out_path.write_text(_strip_lone_surrogates(html), encoding="utf-8")
    print(f"Wrote {out_path}")
    return out_path


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate static HTML pages for the Nerra Network."
    )
    parser.add_argument(
        "--summaries",
        action="store_true",
        help="Generate summaries pages",
    )
    parser.add_argument(
        "--shows",
        action="store_true",
        help="Generate show pages",
    )
    parser.add_argument(
        "--network",
        action="store_true",
        help="Generate network landing page",
    )
    parser.add_argument(
        "--blogs",
        action="store_true",
        help="Generate blog posts and index pages",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate all pages (default if no flags given)",
    )
    parser.add_argument(
        "--show",
        type=str,
        help="Generate pages for a specific show slug (e.g. tesla, omni_view)",
    )
    parser.add_argument(
        "--sitemap",
        action="store_true",
        help="Generate sitemap.xml",
    )
    parser.add_argument(
        "--player",
        action="store_true",
        help="Generate the cross-show podcast player page",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview output without writing files",
    )

    args = parser.parse_args()

    # Default to --all if no specific flag
    if not args.summaries and not args.shows and not args.network and not args.all and not args.show and not args.blogs and not args.sitemap and not args.player:
        args.all = True

    if args.show:
        if args.show not in NETWORK_SHOWS:
            print(f"Error: unknown show '{args.show}'. Valid: {', '.join(NETWORK_SHOWS)}", file=sys.stderr)
            sys.exit(1)
        # Always generate the show page and summaries page
        generate_show_page(args.show, dry_run=args.dry_run)
        generate_summaries_page(args.show, dry_run=args.dry_run)

        # Dedicated MIT performance page
        if args.show == "modern_investing":
            generate_mit_performance_page(dry_run=args.dry_run)
        # Tesla Narrative page + Tesla data dashboard
        if args.show == "tesla":
            generate_tesla_narrative_page(dry_run=args.dry_run)
            generate_tesla_dashboard(dry_run=args.dry_run)
        # SpaceX Launch Dashboard
        if args.show == "spacex":
            generate_spacex_dashboard(dry_run=args.dry_run)
        # Phase 3 narrative page for other memory-enabled shows (no-op otherwise)
        generate_narrative_page(args.show, dry_run=args.dry_run)
        if args.blogs:
            generate_blog_posts(args.show, dry_run=args.dry_run)
            generate_blog_index(args.show, dry_run=args.dry_run)
        if args.network:
            generate_network_page(dry_run=args.dry_run)
        return

    if args.all:
        generate_all_show_pages(dry_run=args.dry_run)
        generate_all_summaries(dry_run=args.dry_run)
        generate_network_page(dry_run=args.dry_run)
        generate_all_blogs(dry_run=args.dry_run)
        generate_404_page(dry_run=args.dry_run)
        generate_player_page(dry_run=args.dry_run)
        generate_start_here_page(dry_run=args.dry_run)
        generate_about_page(dry_run=args.dry_run)
        generate_gallery_page(dry_run=args.dry_run)
        generate_spacex_dashboard(dry_run=args.dry_run)
        generate_tesla_dashboard(dry_run=args.dry_run)
        generate_data_hub_page(dry_run=args.dry_run)
        generate_how_to_listen_page(dry_run=args.dry_run)
        generate_press_page(dry_run=args.dry_run)
        generate_contact_page(dry_run=args.dry_run)
        generate_editorial_page(dry_run=args.dry_run)
        generate_faq_page(dry_run=args.dry_run)
        # Sitemap last so it picks up every page generated above
        generate_sitemap(dry_run=args.dry_run)
        # Regenerate JSON API for mobile app
        try:
            import subprocess
            api_script = ROOT / "scripts" / "generate_api.py"
            if api_script.exists():
                _api_cmd = [sys.executable, str(api_script)]
                if args.dry_run:
                    print(f"[dry-run] Would run: {' '.join(_api_cmd)}")
                else:
                    subprocess.run(_api_cmd, check=True, cwd=str(ROOT))
                    print("API regenerated successfully")
        except Exception as exc:
            print(f"Warning: API regeneration failed (non-fatal): {exc}", file=sys.stderr)
        return

    if args.shows:
        generate_all_show_pages(dry_run=args.dry_run)
    if args.summaries:
        generate_all_summaries(dry_run=args.dry_run)
    if args.network:
        generate_network_page(dry_run=args.dry_run)
        # The data dashboards are data-light (read same-origin caches at
        # runtime) so they're cheap to regenerate on every network rebuild.
        generate_spacex_dashboard(dry_run=args.dry_run)
        generate_tesla_dashboard(dry_run=args.dry_run)
        generate_data_hub_page(dry_run=args.dry_run)
        # --network --blogs: regenerate network blog index only (not all posts)
        if args.blogs:
            generate_network_blog_index(dry_run=args.dry_run)
    elif args.blogs:
        generate_all_blogs(dry_run=args.dry_run)
    if args.sitemap:
        generate_sitemap(dry_run=args.dry_run)
    if args.player:
        generate_player_page(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
