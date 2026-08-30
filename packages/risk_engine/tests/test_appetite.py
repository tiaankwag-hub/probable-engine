import pytest

from packages.risk_engine.appetite import AppetiteThresholds, evaluate_appetite


def make_thresholds(**overrides):
    defaults = dict(appetite_band="low", tolerance_band="moderate", limit_value=None)
    defaults.update(overrides)
    return AppetiteThresholds(**defaults)


class TestAppetiteThresholdsValidation:
    def test_valid_thresholds_construct(self):
        make_thresholds()

    def test_invalid_band_name_raises(self):
        with pytest.raises(ValueError, match="must be one of"):
            make_thresholds(appetite_band="critical")

    def test_tolerance_below_appetite_raises(self):
        with pytest.raises(ValueError, match="at or above"):
            make_thresholds(appetite_band="high", tolerance_band="low")

    def test_equal_appetite_and_tolerance_is_valid(self):
        make_thresholds(appetite_band="moderate", tolerance_band="moderate")


class TestEvaluateAppetite:
    def test_no_thresholds_is_not_configured(self):
        assert evaluate_appetite("high", 15.0, None) == "not_configured"

    def test_no_band_is_not_configured(self):
        assert evaluate_appetite(None, None, make_thresholds()) == "not_configured"

    def test_band_at_or_below_appetite_is_within(self):
        thresholds = make_thresholds(appetite_band="moderate", tolerance_band="high")
        assert evaluate_appetite("low", 5.0, thresholds) == "within_appetite"
        assert evaluate_appetite("moderate", 10.0, thresholds) == "within_appetite"

    def test_band_between_appetite_and_tolerance_is_approaching(self):
        thresholds = make_thresholds(appetite_band="low", tolerance_band="high")
        assert evaluate_appetite("moderate", 10.0, thresholds) == "approaching_tolerance"
        assert evaluate_appetite("high", 18.0, thresholds) == "approaching_tolerance"

    def test_band_above_tolerance_is_outside(self):
        thresholds = make_thresholds(appetite_band="low", tolerance_band="moderate")
        assert evaluate_appetite("high", 18.0, thresholds) == "outside_appetite"
        assert evaluate_appetite("extreme", 25.0, thresholds) == "outside_appetite"

    def test_exceeding_limit_value_is_material_breach_even_within_band(self):
        thresholds = make_thresholds(appetite_band="low", tolerance_band="extreme", limit_value=10.0)
        assert evaluate_appetite("moderate", 12.0, thresholds) == "material_breach"

    def test_limit_value_not_exceeded_falls_back_to_band_logic(self):
        thresholds = make_thresholds(appetite_band="low", tolerance_band="moderate", limit_value=100.0)
        assert evaluate_appetite("low", 10.0, thresholds) == "within_appetite"

    def test_no_residual_score_skips_limit_check(self):
        thresholds = make_thresholds(appetite_band="low", tolerance_band="moderate", limit_value=1.0)
        assert evaluate_appetite("low", None, thresholds) == "within_appetite"
