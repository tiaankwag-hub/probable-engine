# packages/simulations

Monte Carlo simulation engines: single-risk (Triangular / PERT / Lognormal loss
distributions) and portfolio-level (with risk correlation), producing Expected Annual Loss,
percentiles (P75/P90/P95/P99), exceedance curves, and tail-risk contribution.

Simulations are seeded for reproducibility, versioned via `simulation_configs`, and always
executed by `apps/worker` — never inline in an API request. This package never invents
financial inputs; it only consumes configuration explicitly supplied and persisted.

Status: not yet implemented. Single-risk simulation lands in Milestone 6; portfolio
simulation (with correlation) in Milestone 7.
