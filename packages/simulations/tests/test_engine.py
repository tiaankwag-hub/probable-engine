import statistics as pystats

from packages.simulations.distributions import DistributionType
from packages.simulations.engine import (
    RiskSimulationInput,
    SimulationParams,
    build_histogram,
    compute_statistics,
    correlate_series,
    generate_reference_normals,
    probability_exceeding,
    run_annual_loss_simulation,
    run_portfolio_simulation,
)

BASE_PARAMS = SimulationParams(
    distribution_type=DistributionType.TRIANGULAR,
    loss_min=1_000,
    loss_most_likely=10_000,
    loss_max=100_000,
    annual_event_frequency=2.0,
    iterations=5_000,
    seed=42,
)


class TestRunAnnualLossSimulation:
    def test_deterministic_given_same_seed(self):
        a = run_annual_loss_simulation(BASE_PARAMS)
        b = run_annual_loss_simulation(BASE_PARAMS)
        assert a == b

    def test_different_seed_gives_different_results(self):
        a = run_annual_loss_simulation(BASE_PARAMS)
        b = run_annual_loss_simulation(SimulationParams(**{**BASE_PARAMS.__dict__, "seed": 99}))
        assert a != b

    def test_zero_frequency_means_zero_loss_every_year(self):
        params = SimulationParams(**{**BASE_PARAMS.__dict__, "annual_event_frequency": 0.0})
        losses = run_annual_loss_simulation(params)
        assert all(loss == 0 for loss in losses)

    def test_returns_one_value_per_iteration(self):
        losses = run_annual_loss_simulation(BASE_PARAMS)
        assert len(losses) == BASE_PARAMS.iterations

    def test_higher_frequency_increases_expected_annual_loss(self):
        low_freq = run_annual_loss_simulation(SimulationParams(**{**BASE_PARAMS.__dict__, "annual_event_frequency": 0.5, "seed": 1}))
        high_freq = run_annual_loss_simulation(SimulationParams(**{**BASE_PARAMS.__dict__, "annual_event_frequency": 5.0, "seed": 1}))
        assert pystats.fmean(high_freq) > pystats.fmean(low_freq)


class TestComputeStatistics:
    def test_percentiles_are_non_decreasing(self):
        losses = run_annual_loss_simulation(BASE_PARAMS)
        stats = compute_statistics(losses)
        assert stats.median <= stats.p75 <= stats.p90 <= stats.p95 <= stats.p99

    def test_empty_input_returns_zeros(self):
        stats = compute_statistics([])
        assert stats.expected_annual_loss == 0.0
        assert stats.p99 == 0.0

    def test_histogram_bin_counts_sum_to_sample_size(self):
        losses = run_annual_loss_simulation(BASE_PARAMS)
        histogram = build_histogram(losses)
        assert sum(b["count"] for b in histogram) == len(losses)


class TestProbabilityExceeding:
    def test_zero_threshold_with_any_losses_is_high(self):
        losses = run_annual_loss_simulation(BASE_PARAMS)
        assert probability_exceeding(losses, 0) > 0.5

    def test_huge_threshold_is_near_zero(self):
        losses = run_annual_loss_simulation(BASE_PARAMS)
        assert probability_exceeding(losses, 10_000_000) == 0.0


class TestCorrelateSeries:
    def test_preserves_the_exact_multiset_of_values(self):
        series = [5.0, 1.0, 3.0, 2.0, 4.0]
        reference = [10.0, 20.0, 30.0, 40.0, 50.0]
        correlated = correlate_series(reference, series)
        assert sorted(correlated) == sorted(series)

    def test_matches_rank_order_of_reference(self):
        series = [5.0, 1.0, 3.0, 2.0, 4.0]
        reference = [10.0, 20.0, 30.0, 40.0, 50.0]
        correlated = correlate_series(reference, series)
        # reference is already ascending, so correlated should be too
        assert correlated == sorted(series)

    def test_rejects_mismatched_lengths(self):
        import pytest

        with pytest.raises(ValueError):
            correlate_series([1.0, 2.0], [1.0])


class TestPortfolioSimulation:
    def test_portfolio_total_equals_sum_of_per_risk_losses(self):
        inputs = [
            RiskSimulationInput(risk_id="r1", params=BASE_PARAMS),
            RiskSimulationInput(risk_id="r2", params=BASE_PARAMS),
        ]
        result = run_portfolio_simulation(inputs, iterations=1000, seed=1)
        for k in range(1000):
            expected = result.per_risk_annual_losses["r1"][k] + result.per_risk_annual_losses["r2"][k]
            assert result.portfolio_annual_losses[k] == expected

    def test_per_risk_contribution_sums_to_one(self):
        inputs = [
            RiskSimulationInput(risk_id="r1", params=BASE_PARAMS, correlation_group="cluster-a"),
            RiskSimulationInput(risk_id="r2", params=BASE_PARAMS, correlation_group="cluster-a"),
            RiskSimulationInput(risk_id="r3", params=BASE_PARAMS),
        ]
        result = run_portfolio_simulation(inputs, iterations=1000, seed=1)
        assert abs(sum(result.per_risk_contribution.values()) - 1.0) < 1e-9

    def test_correlated_group_moves_together_more_than_independent_pair(self):
        correlated_inputs = [
            RiskSimulationInput(risk_id="r1", params=BASE_PARAMS, correlation_group="g", correlation_strength=0.9),
            RiskSimulationInput(risk_id="r2", params=BASE_PARAMS, correlation_group="g", correlation_strength=0.9),
        ]
        independent_inputs = [
            RiskSimulationInput(risk_id="r1", params=BASE_PARAMS),
            RiskSimulationInput(risk_id="r2", params=BASE_PARAMS),
        ]
        correlated_result = run_portfolio_simulation(correlated_inputs, iterations=3000, seed=7)
        independent_result = run_portfolio_simulation(independent_inputs, iterations=3000, seed=7)

        def pearson(xs, ys):
            mean_x, mean_y = pystats.fmean(xs), pystats.fmean(ys)
            cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / len(xs)
            std_x = pystats.pstdev(xs)
            std_y = pystats.pstdev(ys)
            return cov / (std_x * std_y) if std_x and std_y else 0.0

        correlated_corr = pearson(
            correlated_result.per_risk_annual_losses["r1"], correlated_result.per_risk_annual_losses["r2"]
        )
        independent_corr = pearson(
            independent_result.per_risk_annual_losses["r1"], independent_result.per_risk_annual_losses["r2"]
        )
        assert correlated_corr > independent_corr

    def test_reproducible_given_same_seed(self):
        inputs = [
            RiskSimulationInput(risk_id="r1", params=BASE_PARAMS, correlation_group="g"),
            RiskSimulationInput(risk_id="r2", params=BASE_PARAMS, correlation_group="g"),
        ]
        a = run_portfolio_simulation(inputs, iterations=500, seed=3)
        b = run_portfolio_simulation(inputs, iterations=500, seed=3)
        assert a.portfolio_annual_losses == b.portfolio_annual_losses


class TestGenerateReferenceNormals:
    def test_same_common_seed_gives_same_common_component(self):
        a = generate_reference_normals(common_seed=1, idiosyncratic_seed=10, correlation_strength=1.0, iterations=100)
        b = generate_reference_normals(common_seed=1, idiosyncratic_seed=20, correlation_strength=1.0, iterations=100)
        # correlation_strength=1.0 means idiosyncratic component has zero weight
        assert a == b
