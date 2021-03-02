import numpy as np
import pytest

from pacerlab import _core


def run(time, value, comp, rule="second_price", budget=1e9, buckets=4, strategy="flat",
        params=None, reserve=0.0, seed=0):
    target = np.linspace(0, budget, buckets + 1)
    return _core.run(np.asarray(time, float), np.asarray(value, float), np.asarray(comp, float),
                     rule, reserve, budget, target, strategy, params or {}, seed)


def test_second_price_pays_competitor_bid():
    r = run([0.1, 0.6], [5, 5], [2, 3])
    assert r["spend"].sum() == 5 and r["wins"].sum() == 2 and r["value"].sum() == 10


def test_first_price_pays_own_bid():
    r = run([0.1, 0.6], [5, 5], [2, 3], rule="first_price", params={"base_mult": 0.8})
    assert r["spend"].sum() == pytest.approx(8.0)


def test_ties_and_reserve_lose():
    assert run([0.1], [2], [2])["wins"].sum() == 0
    assert run([0.1], [2], [0.5], reserve=3)["wins"].sum() == 0


def test_reserve_is_the_second_price_floor():
    assert run([0.1], [5], [0.5], reserve=2)["spend"].sum() == 2


def test_budget_never_exceeded_and_buckets_line_up():
    t = (np.arange(1000) + 0.5) / 1000
    r = run(t, np.full(1000, 3.0), np.full(1000, 1.0), budget=37.5)
    assert r["spend"].sum() == 37.0
    assert r["auctions"].sum() == 1000 and list(r["auctions"]) == [250] * 4


def test_rejects_bad_input():
    with pytest.raises(ValueError):
        run([0.5, 0.1], [1, 1], [0, 0])  # unsorted
    with pytest.raises(ValueError):
        run([0.1], [1, 1], [0])  # length mismatch
    with pytest.raises(ValueError):
        run([0.1], [1], [0], rule="vickrey")
    with pytest.raises(ValueError):
        run([0.1], [1], [0], strategy="nope")
    with pytest.raises(ValueError):
        run([0.1], [1], [0], params={"bogus": 1})


def test_throttling_is_seeded():
    t = (np.arange(500) + 0.5) / 500
    args = (t, np.ones(500), np.zeros(500))
    a = run(*args, strategy="pid", params={"initial_rate": 0.5}, seed=3)
    b = run(*args, strategy="pid", params={"initial_rate": 0.5}, seed=3)
    c = run(*args, strategy="pid", params={"initial_rate": 0.5}, seed=4)
    assert (a["entered"] == b["entered"]).all()
    assert (a["entered"] != c["entered"]).any()
