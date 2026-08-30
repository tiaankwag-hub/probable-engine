import pytest

from packages.shared.dashboard_service import round_to_grid


class TestRoundToGrid:
    def test_none_passes_through(self):
        assert round_to_grid(None) is None

    @pytest.mark.parametrize(
        "value,expected",
        [
            (1.0, 1),
            (1.49, 1),
            (1.5, 2),
            (2.83, 3),
            (5.0, 5),
        ],
    )
    def test_rounds_to_nearest_int(self, value, expected):
        assert round_to_grid(value) == expected

    def test_clamps_below_minimum(self):
        assert round_to_grid(0.2) == 1

    def test_clamps_above_maximum(self):
        assert round_to_grid(5.9) == 5
