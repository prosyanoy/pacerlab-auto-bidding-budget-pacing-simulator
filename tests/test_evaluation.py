import numpy as np
import pytest

from pacerlab import (DualAscent, FlatBid, MultiplicativePacing, PidThrottle, TrafficConfig,
                      compare, evaluate, generate_traffic, run, traffic_target)

RULES = ("second_price", "first_price")


@pytest.fixture(scope="module")
def traffic():
    return generate_traffic(TrafficConfig(n_auctions=120_000), seed=11)


def test_target_curves(traffic):
    t = traffic_target(traffic, 48, 100.0)
    assert t[0] == 0 and t[-1] == pytest.approx(100.0) and (np.diff(t) > 0).all()
    assert np.allclose(traffic_target(traffic, 10, 5.0, "linear"), np.linspace(0, 5, 11))
    with pytest.raises(ValueError):
        traffic_target(traffic, 10, 5.0, "nope")


@pytest.mark.parametrize("rule", RULES)
def test_budget_respected_and_metrics_consistent(traffic, rule):
    df, res = compare(traffic, rule=rule, budget_ratio=0.3)
    for label, r in res.items():
        assert r.spend.sum() <= r.budget + 1e-9
        assert (r.wins <= r.entered).all() and (r.entered <= r.auctions).all()
    m = df.loc["Flat bid"]
    assert m.budget_utilization == pytest.approx(1.0, abs=1e-3)
    assert m.roas == pytest.approx(m.total_value / (m.budget_utilization * res["Flat bid"].budget))
    assert 0 < m.win_rate < 1


@pytest.mark.parametrize("rule", RULES)
def test_pacing_beats_flat_on_smoothness(traffic, rule):
    df, _ = compare(traffic, rule=rule, budget_ratio=0.3)
    flat = df.loc["Flat bid"]
    assert flat.budget_exhausted_at < 0.7
    for label in ("PID throttling", "Dual ascent", "Multiplicative pacing"):
        assert df.loc[label].spend_rmse < 0.25 * flat.spend_rmse, label
        assert df.loc[label].budget_utilization > 0.95, label


def test_bid_shading_methods_gain_roas_in_second_price(traffic):
    df, _ = compare(traffic, rule="second_price", budget_ratio=0.3)
    assert df.loc["Dual ascent"].roas > df.loc["Flat bid"].roas


def test_unlimited_budget_all_strategies_agree_on_flat(traffic):
    df, _ = compare(traffic, [FlatBid(), PidThrottle(), DualAscent(), MultiplicativePacing()],
                    budget_ratio=5.0)
    assert df.loc["Flat bid"].win_rate == pytest.approx(df.loc["Dual ascent"].win_rate)


def test_reproducible_runs(traffic):
    a, _ = compare(traffic, seed=3)
    b, _ = compare(traffic, seed=3)
    assert a.equals(b)


def test_evaluate_aggregates_over_seeds():
    out = evaluate([1, 2], TrafficConfig(n_auctions=20_000), budget_ratio=0.3, n_buckets=48)
    assert out["mean"].shape == (4, 7) and (out["std"] >= 0).all().all()


def test_run_validates_inputs(traffic):
    with pytest.raises(ValueError):
        run(traffic, FlatBid(), "dutch", 10.0)
    with pytest.raises(ValueError):
        run(traffic, FlatBid(), "second_price", -1.0)
    with pytest.raises(ValueError):
        run(traffic, FlatBid(), "second_price", 10.0, n_buckets=10, target=np.zeros(3))
