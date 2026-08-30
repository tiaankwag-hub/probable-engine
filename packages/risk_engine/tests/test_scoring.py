import pytest

from packages.risk_engine.scoring import (
    ImpactScores,
    ScoringConfigData,
    band_for_score,
    compute_inherent_score,
    compute_overall_impact,
    compute_reduction_fraction,
    compute_residual_score,
    default_scoring_config,
    score_risk,
)


def make_scores(**overrides) -> ImpactScores:
    defaults = dict(
        financial=3,
        customer_service=3,
        operational_delivery=3,
        legal_regulatory=3,
        reputation=3,
        health_safety=3,
    )
    defaults.update(overrides)
    return ImpactScores(**defaults)


class TestImpactScoresValidation:
    def test_valid_scores_construct(self):
        scores = make_scores()
        assert scores.financial == 3

    @pytest.mark.parametrize("value", [0, -1, 6, 100])
    def test_out_of_range_raises(self, value):
        with pytest.raises(ValueError):
            make_scores(financial=value)


class TestScoringConfigValidation:
    def test_default_config_is_valid(self):
        config = default_scoring_config()
        assert config.version == 1

    def test_weights_must_sum_to_one(self):
        with pytest.raises(ValueError, match="sum to 1.0"):
            ScoringConfigData(
                version=1,
                dimension_weights={
                    "financial": 0.5,
                    "customer_service": 0.5,
                    "operational_delivery": 0.5,
                    "legal_regulatory": 0.0,
                    "reputation": 0.0,
                    "health_safety": 0.0,
                },
                band_thresholds=((25.0, "extreme"),),
            )

    def test_missing_dimension_weight_raises(self):
        with pytest.raises(ValueError, match="missing weights"):
            ScoringConfigData(
                version=1,
                dimension_weights={"financial": 1.0},
                band_thresholds=((25.0, "extreme"),),
            )

    def test_unsorted_thresholds_raise(self):
        with pytest.raises(ValueError, match="sorted ascending"):
            default = default_scoring_config()
            ScoringConfigData(
                version=1,
                dimension_weights=default.dimension_weights,
                band_thresholds=((18.0, "high"), (6.0, "low")),
            )

    def test_empty_thresholds_raise(self):
        with pytest.raises(ValueError, match="must not be empty"):
            default = default_scoring_config()
            ScoringConfigData(
                version=1, dimension_weights=default.dimension_weights, band_thresholds=()
            )


class TestOverallImpact:
    def test_equal_weights_average_uniform_scores(self):
        config = default_scoring_config()
        result = compute_overall_impact(make_scores(), config)
        assert result == 3.0

    def test_min_and_max_bounds(self):
        config = default_scoring_config()
        assert compute_overall_impact(make_scores(**{d: 1 for d in [
            "financial", "customer_service", "operational_delivery",
            "legal_regulatory", "reputation", "health_safety",
        ]}), config) == 1.0
        assert compute_overall_impact(make_scores(**{d: 5 for d in [
            "financial", "customer_service", "operational_delivery",
            "legal_regulatory", "reputation", "health_safety",
        ]}), config) == 5.0

    def test_weighted_config_changes_result(self):
        config = ScoringConfigData(
            version=2,
            dimension_weights={
                "financial": 1.0,
                "customer_service": 0.0,
                "operational_delivery": 0.0,
                "legal_regulatory": 0.0,
                "reputation": 0.0,
                "health_safety": 0.0,
            },
            band_thresholds=default_scoring_config().band_thresholds,
        )
        result = compute_overall_impact(make_scores(financial=5, customer_service=1), config)
        assert result == 5.0


class TestInherentScore:
    def test_multiplies_impact_by_likelihood(self):
        assert compute_inherent_score(overall_impact=4.0, likelihood=3) == 12.0

    @pytest.mark.parametrize("likelihood", [0, 6, -1])
    def test_invalid_likelihood_raises(self, likelihood):
        with pytest.raises(ValueError):
            compute_inherent_score(overall_impact=3.0, likelihood=likelihood)


class TestBanding:
    @pytest.mark.parametrize(
        "score,expected_band",
        [
            (1.0, "low"),
            (6.0, "low"),
            (6.01, "moderate"),
            (12.0, "moderate"),
            (12.5, "high"),
            (18.0, "high"),
            (18.5, "extreme"),
            (25.0, "extreme"),
        ],
    )
    def test_band_thresholds(self, score, expected_band):
        config = default_scoring_config()
        assert band_for_score(score, config) == expected_band

    def test_score_above_all_thresholds_falls_into_last_band(self):
        config = default_scoring_config()
        assert band_for_score(999.0, config) == "extreme"


class TestControlReduction:
    def test_no_control_effectiveness_means_no_reduction(self):
        assert compute_reduction_fraction(None, default_scoring_config()) == 0.0

    def test_max_effectiveness_yields_max_reduction(self):
        config = default_scoring_config()
        assert compute_reduction_fraction(5, config) == config.max_reduction_fraction

    def test_min_effectiveness_yields_partial_reduction(self):
        config = default_scoring_config()
        expected = round((1 / 5) * config.max_reduction_fraction, 4)
        assert compute_reduction_fraction(1, config) == expected

    @pytest.mark.parametrize("value", [0, 6, -1])
    def test_invalid_effectiveness_raises(self, value):
        with pytest.raises(ValueError):
            compute_reduction_fraction(value, default_scoring_config())

    def test_residual_score_reduces_inherent_score(self):
        residual, reduction = compute_residual_score(20.0, 5, default_scoring_config())
        assert reduction == 0.6
        assert residual == 8.0

    def test_residual_score_without_controls_equals_inherent(self):
        residual, reduction = compute_residual_score(15.0, None, default_scoring_config())
        assert reduction == 0.0
        assert residual == 15.0


class TestScoreRiskEndToEnd:
    def test_full_pipeline_uniform_medium_risk(self):
        result = score_risk(
            scores=make_scores(), likelihood=3, control_effectiveness=3
        )
        assert result.overall_impact == 3.0
        assert result.inherent_score == 9.0
        assert result.inherent_band == "moderate"
        assert result.residual_score < result.inherent_score
        assert result.residual_band in {"low", "moderate"}

    def test_extreme_risk_with_no_controls(self):
        scores = make_scores(
            financial=5, customer_service=5, operational_delivery=5,
            legal_regulatory=5, reputation=5, health_safety=5,
        )
        result = score_risk(scores=scores, likelihood=5, control_effectiveness=None)
        assert result.inherent_score == 25.0
        assert result.inherent_band == "extreme"
        assert result.residual_score == 25.0
        assert result.residual_band == "extreme"

    def test_deterministic_repeated_calls(self):
        scores = make_scores(financial=4)
        first = score_risk(scores=scores, likelihood=2, control_effectiveness=3)
        second = score_risk(scores=scores, likelihood=2, control_effectiveness=3)
        assert first == second

    def test_result_records_config_version(self):
        config = default_scoring_config()
        result = score_risk(
            scores=make_scores(), likelihood=1, control_effectiveness=1, config=config
        )
        assert result.scoring_config_version == config.version
