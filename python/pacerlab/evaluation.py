"""Evaluation harness: run strategies on shared traffic and report metrics."""
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from . import _core
from .strategies import FlatBid, Strategy, default_strategies
from .traffic import Traffic, TrafficConfig, generate_traffic

RULES = ("first_price", "second_price")


def traffic_target(traffic: Traffic, n_buckets: int, budget: float, kind: str = "traffic") -> np.ndarray:
    """Target cumulative spend at the n_buckets+1 bucket edges.

    'traffic': proportional to the cumulative share of auctions (a perfect
    traffic forecast); 'linear': spend evenly over the day.
    """
    if kind == "linear":
        return budget * np.linspace(0.0, 1.0, n_buckets + 1)
    if kind != "traffic":
        raise ValueError("target kind must be 'traffic' or 'linear'")
    b = np.minimum((traffic.time * n_buckets).astype(int), n_buckets - 1)
    counts = np.bincount(b, minlength=n_buckets)
    return budget * np.concatenate([[0.0], np.cumsum(counts) / counts.sum()])


def unconstrained_spend(traffic: Traffic, rule: str, base_mult: float, n_buckets: int = 1) -> float:
    """Spend of the flat strategy with an unlimited budget."""
    res = run(traffic, FlatBid(base_mult), rule, budget=1e18, n_buckets=n_buckets,
              target=np.linspace(0, 1e18, n_buckets + 1))
    return float(res.spend.sum())


@dataclass
class RunResult:
    strategy: str
    budget: float
    target_cum: np.ndarray  # n_buckets + 1
    spend: np.ndarray  # per bucket
    value: np.ndarray
    auctions: np.ndarray
    entered: np.ndarray
    wins: np.ndarray

    @property
    def spend_cum(self) -> np.ndarray:
        return np.concatenate([[0.0], np.cumsum(self.spend)])

    @property
    def time_axis(self) -> np.ndarray:
        return np.linspace(0.0, 1.0, len(self.spend) + 1)

    def metrics(self) -> Dict[str, float]:
        spent = float(self.spend.sum())
        dev = (self.spend_cum - self.target_cum) / self.budget
        total_auctions = int(self.auctions.sum())
        total_value = float(self.value.sum())
        exhausted = np.nonzero(self.spend_cum >= self.budget * (1 - 1e-3))[0]
        return {
            "budget_utilization": spent / self.budget,
            "spend_rmse": float(np.sqrt(np.mean(dev ** 2))),
            "spend_max_dev": float(np.max(np.abs(dev))),
            "win_rate": int(self.wins.sum()) / total_auctions if total_auctions else 0.0,
            "total_value": total_value,
            "roas": total_value / spent if spent > 0 else 0.0,
            "budget_exhausted_at": float(exhausted[0] / len(self.spend)) if len(exhausted) else 1.0,
        }


def run(traffic: Traffic, strategy: Strategy, rule: str, budget: float, n_buckets: int = 288,
        target: Optional[np.ndarray] = None, reserve: float = 0.0, seed: int = 0) -> RunResult:
    if rule not in RULES:
        raise ValueError(f"rule must be one of {RULES}")
    if budget <= 0:
        raise ValueError("budget must be positive")
    if target is None:
        target = traffic_target(traffic, n_buckets, budget)
    target = np.ascontiguousarray(target, dtype=float)
    if len(target) != n_buckets + 1:
        raise ValueError("target must have n_buckets + 1 entries")
    out = _core.run(traffic.time, traffic.value, traffic.comp_bid, rule, reserve, budget,
                    target, strategy.name, strategy.params(), seed)
    return RunResult(strategy.name, budget, target, out["spend"], out["value"],
                     out["auctions"], out["entered"], out["wins"])


def compare(traffic: Traffic, strategies: Optional[Sequence[Strategy]] = None,
            rule: str = "second_price", budget_ratio: float = 0.35, n_buckets: int = 288,
            target_kind: str = "traffic", reserve: float = 0.0, seed: int = 0):
    """Run every strategy on the same traffic and budget.

    Budget = budget_ratio * what the flat bidder would spend with no limit, so
    ratios < 1 make the budget bind. Returns (metrics DataFrame, {label: RunResult}).
    """
    strategies = list(strategies) if strategies is not None else default_strategies(rule)
    base = strategies[0].params().get("base_mult", 1.0)
    budget = budget_ratio * unconstrained_spend(traffic, rule, base)
    target = traffic_target(traffic, n_buckets, budget, target_kind)
    results, rows = {}, []
    for s in strategies:
        r = run(traffic, s, rule, budget, n_buckets, target, reserve, seed)
        results[s.label] = r
        rows.append({"strategy": s.label, **r.metrics()})
    return pd.DataFrame(rows).set_index("strategy"), results


def evaluate(seeds: Iterable[int], traffic_cfg: TrafficConfig = TrafficConfig(),
             **kwargs) -> pd.DataFrame:
    """Repeat compare() over independent traffic seeds; return mean and std per metric."""
    frames = []
    for sd in seeds:
        df, _ = compare(generate_traffic(traffic_cfg, sd), seed=sd, **kwargs)
        frames.append(df)
    cat = pd.concat(frames, keys=list(range(len(frames))), names=["run"])
    g = cat.groupby("strategy", sort=False)
    return pd.concat({"mean": g.mean(), "std": g.std(ddof=0)}, axis=1)
