"""WO-1 regression fixture: the citation-shape lint vocabulary.

The original ``CITATION_SHAPE_PATTERNS`` set caught 4 of 14 fabrications
independently verified by hand fact-check — it measured ONE template, not
exposure. This fixture pins the widened vocabulary against all 14 verified
fabrications (must catch) and the sanctioned general-form escape hatch
(must NOT catch). The distinction that must survive any future tuning:
attributing to unnamed *people* ("contemporary observers warned") is the
sanctioned general form; attributing to non-existent *documents, records,
institutions, or datasets* is the fabrication signature.

A count from these patterns is a FLOOR, not a measurement — they detect
known fabrication templates; novel shapes are not detected.
"""

import pytest

from engine.claims import find_citation_shapes

# ---------------------------------------------------------------------------
# 14 verified fabrications — every one shipped in a published book volume
# and failed hand fact-check. All MUST be caught.
# ---------------------------------------------------------------------------

MUST_CATCH = [
    # -- Caught by the original template set (do not regress) --
    pytest.param(
        "Estimates compiled by the American Medical Association suggest "
        "roughly 50,000 lobotomies performed in the United States.",
        id="uc-v2c12-estimates-compiled",
    ),
    pytest.param(
        "A 1995 survey of U.S. physicians found that more than 80 percent "
        "recommended estrogen to asymptomatic patients.",
        id="uc-v2c15-dated-survey",
    ),
    pytest.param(
        "Estimates from the World Health Organization and national "
        "registries suggest that asbestos-related diseases still claim "
        "roughly 40,000 lives worldwide each year.",
        id="uc-v4c7-estimates-from",
    ),
    pytest.param(
        "Estimates from the Bureau of Labor Statistics suggest that "
        "roughly 1.5 million workers performed driving or delivery tasks "
        "through apps as of 2023.",
        id="uc-v4c9-estimates-from-bls",
    ),
    # -- The gap: missed by the original set --
    pytest.param(
        "In 1962 the World Health Organization issued guidance "
        "discouraging psychosurgery except under strict research protocols.",
        id="uc-v2c12-dated-institutional-action",
    ),
    pytest.param(
        "surviving dial-painter records are preserved by the National "
        "Museum of Nuclear Science & History.",
        id="uc-v2c13-archival-custody",
    ),
    pytest.param(
        "A small number of researchers, including British pharmacologist "
        "Sir Robert Robinson, had noted in the early 1940s that high-dose "
        "estrogens could alter genital-tract development.",
        id="uc-v2c19-named-expert",
    ),
    pytest.param(
        "the 92 million tonnes of annual textile waste now tracked by the "
        "Ellen MacArthur Foundation and national environmental agencies.",
        id="uc-v4c3-institutional-data-custody",
    ),
    pytest.param(
        "A 1974 internal memo from British American Tobacco observed that "
        "'the smoker is obtaining a higher delivery than the figures "
        "suggest.'",
        id="uc-v4c11-quoted-document",
    ),
    pytest.param(
        "The Federal Trade Commission briefly required tar-and-nicotine "
        "disclosures in 1957, then suspended the rule after industry "
        "complaints.",
        id="uc-v4c11-invented-regulatory-history",
    ),
    pytest.param(
        "Maya Bay's coral cover declined by roughly 80 percent in the "
        "decade after the film, according to surveys by Thailand's "
        "Department of National Parks.",
        id="uc-v4c19-attributed-survey",
    ),
    pytest.param(
        "Wastewater sampling in several cities during 2020-2022 detected "
        "elevated alcohol residues near schools and offices.",
        id="uc-v2c16-invented-empirical-finding",
    ),
    pytest.param(
        "A 1954 British textile journal noted that one pound of polyester "
        "could yield garments for several families.",
        id="uc-v2c20-dated-periodical",
    ),
    pytest.param(
        "Accounts from the period describe a bounty that officials "
        "believed would reduce the snake population.",
        id="uc-v1c1-invented-archival-record",
    ),
]

# ---------------------------------------------------------------------------
# General-form prose — the sanctioned escape hatch the prompt constraint
# steers toward. Flagging any of these punishes exactly the behaviour the
# gate asks for. All must pass clean.
# ---------------------------------------------------------------------------

MUST_NOT_CATCH = [
    pytest.param(
        "Contemporary observers warned that the bounty might backfire.",
        id="general-observers-warned",
    ),
    pytest.param(
        "The policy was widely criticised at the time.",
        id="general-criticised",
    ),
    pytest.param(
        "By the late 1960s the practice had largely stopped.",
        id="general-dated-trend",
    ),
    pytest.param(
        "Filters became standard across the industry within a decade.",
        id="general-industry-trend",
    ),
]


class TestWidenedCitationShapes:
    @pytest.mark.parametrize("sentence", MUST_CATCH)
    def test_verified_fabrication_is_caught(self, sentence):
        findings = find_citation_shapes(sentence)
        assert findings, f"verified fabrication not flagged: {sentence!r}"

    @pytest.mark.parametrize("sentence", MUST_NOT_CATCH)
    def test_general_form_is_not_caught(self, sentence):
        findings = find_citation_shapes(sentence)
        assert not findings, (
            f"general form falsely flagged by "
            f"{[f['pattern'] for f in findings]}: {sentence!r}"
        )

    def test_observers_vs_documents_distinction(self):
        """Attributing to unnamed PEOPLE is sanctioned; attributing to
        non-existent DOCUMENTS is not. Both use 'contemporary'."""
        assert not find_citation_shapes(
            "Contemporary observers warned that the lake would change.")
        assert find_citation_shapes(
            "Contemporary accounts describe a bounty paid per snake.")
