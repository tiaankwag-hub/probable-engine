import random

import pytest

from packages.simulations.distributions import (
    DistributionType,
    sample_lognormal,
    sample_pert,
    sample_poisson,
    sample_severity,
    sample_triangular,
)


class TestTriangular:
    def test_within_bounds_over_many_samples(self):
        rng = random.Random(42)
        samples = [sample_triangular(rng, 10, 50, 200) for _ in range(2000)]
        assert all(10 <= s <= 200 for s in samples)

    def test_deterministic_given_same_seed(self):
        a = [sample_triangular(random.Random(7), 10, 50, 200) for _ in range(50)]
        b = [sample_triangular(random.Random(7), 10, 50, 200) for _ in range(50)]
        assert a == b


class TestPert:
    def test_within_bounds_over_many_samples(self):
        rng = random.Random(42)
        samples = [sample_pert(rng, 10, 50, 200) for _ in range(2000)]
        assert all(10 <= s <= 200 for s in samples)

    def test_concentrates_more_tightly_around_most_likely_than_triangular(self):
        tri_rng, pert_rng = random.Random(1), random.Random(1)
        tri_samples = [sample_triangular(tri_rng, 0, 50, 200) for _ in range(5000)]
        pert_samples = [sample_pert(pert_rng, 0, 50, 200) for _ in range(5000)]
        tri_std = (sum((s - 50) ** 2 for s in tri_samples) / len(tri_samples)) ** 0.5
        pert_std = (sum((s - 50) ** 2 for s in pert_samples) / len(pert_samples)) ** 0.5
        assert pert_std < tri_std

    def test_degenerate_range_returns_low(self):
        rng = random.Random(1)
        assert sample_pert(rng, 100, 100, 100) == 100


class TestLognormal:
    def test_positive_and_deterministic(self):
        a = [sample_lognormal(random.Random(3), 10, 50, 200) for _ in range(50)]
        b = [sample_lognormal(random.Random(3), 10, 50, 200) for _ in range(50)]
        assert a == b
        assert all(v > 0 for v in a)

    def test_rejects_invalid_parameters(self):
        with pytest.raises(ValueError):
            sample_lognormal(random.Random(1), 10, 0, 200)
        with pytest.raises(ValueError):
            sample_lognormal(random.Random(1), 10, 200, 100)


class TestSampleSeverityDispatch:
    def test_dispatches_to_correct_sampler(self):
        rng = random.Random(9)
        value = sample_severity(rng, DistributionType.TRIANGULAR, 10, 50, 200)
        assert 10 <= value <= 200


class TestSamplePoisson:
    def test_zero_mean_always_zero(self):
        rng = random.Random(1)
        assert all(sample_poisson(rng, 0) == 0 for _ in range(20))

    def test_average_over_many_draws_approximates_mean(self):
        rng = random.Random(123)
        draws = [sample_poisson(rng, 2.5) for _ in range(20000)]
        average = sum(draws) / len(draws)
        assert 2.3 <= average <= 2.7

    def test_deterministic_given_same_seed(self):
        a = [sample_poisson(random.Random(5), 3.0) for _ in range(50)]
        b = [sample_poisson(random.Random(5), 3.0) for _ in range(50)]
        assert a == b
