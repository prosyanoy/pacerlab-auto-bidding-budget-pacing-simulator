import numpy as np
import pytest

from pacerlab import TrafficConfig, generate_traffic, intensity


def test_shapes_sorted_positive():
    tr = generate_traffic(TrafficConfig(n_auctions=5000), seed=1)
    assert len(tr) == 5000
    assert (np.diff(tr.time) >= 0).all() and tr.time.min() >= 0 and tr.time.max() < 1
    assert (tr.value > 0).all() and (tr.comp_bid > 0).all()


def test_seeded_reproducible():
    cfg = TrafficConfig(n_auctions=2000)
    a, b, c = (generate_traffic(cfg, s) for s in (5, 5, 6))
    assert np.array_equal(a.time, b.time) and np.array_equal(a.value, b.value)
    assert not np.array_equal(a.value, c.value)


def test_diurnal_pattern_matches_intensity():
    cfg = TrafficConfig(n_auctions=200_000)
    tr = generate_traffic(cfg, seed=2)
    counts, edges = np.histogram(tr.time, bins=24)
    expected = intensity((edges[:-1] + edges[1:]) / 2, cfg)
    expected = expected / expected.sum() * counts.sum()
    assert np.abs(counts / expected - 1).max() < 0.06
    assert counts.argmax() in (18, 19, 20) and counts.max() / counts.min() > 2


def test_query_classes_differ_in_value():
    tr = generate_traffic(TrafficConfig(n_auctions=50_000), seed=3)
    means = [tr.value[tr.query_class == k].mean() for k in range(3)]
    assert means[0] < means[1] < means[2]


def test_invalid_config():
    with pytest.raises(ValueError):
        generate_traffic(TrafficConfig(amp_daily=0.9, amp_second=0.3))
    with pytest.raises(ValueError):
        generate_traffic(TrafficConfig(n_auctions=0))
