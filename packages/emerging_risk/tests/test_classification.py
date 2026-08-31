from packages.emerging_risk.classification import classify

SEED_CATEGORIES = [
    "Operational",
    "Financial",
    "Cyber & Information Security",
    "Legal & Regulatory",
    "Strategic",
    "People & Culture",
    "Third Party & Vendor",
]


class TestClassify:
    def test_ransomware_content_classifies_as_cyber(self):
        assert classify("A wave of ransomware attacks hit CI/CD tooling.") == "Cyber & Information Security"

    def test_attrition_content_classifies_as_people_and_culture(self):
        assert classify("Rising voluntary attrition among senior engineering staff.") == "People & Culture"

    def test_vendor_content_classifies_as_third_party(self):
        assert classify("Single-supplier concentration risk across critical vendors.") == "Third Party & Vendor"

    def test_no_keyword_match_returns_none(self):
        assert classify("The weather was pleasant today.") is None

    def test_deterministic_given_same_content(self):
        text = "A regulatory body issued a draft rule on AI disclosure."
        assert classify(text) == classify(text)

    def test_restricts_to_known_categories_when_given(self):
        # Content would match Cyber, but that category isn't in the known set.
        result = classify(
            "A ransomware attack disrupted operations.",
            known_categories=["Operational", "Financial"],
        )
        assert result in {"Operational", None}
        assert result != "Cyber & Information Security"

    def test_every_seed_category_is_reachable(self):
        # Sanity check: every category this org actually seeds has at least
        # one keyword that can match it, so classification isn't silently dead
        # for a whole category.
        for category in SEED_CATEGORIES:
            from packages.emerging_risk.classification import CATEGORY_KEYWORDS
            assert category in CATEGORY_KEYWORDS
            assert len(CATEGORY_KEYWORDS[category]) > 0
