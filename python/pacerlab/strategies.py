"""Strategy objects: one interface, executed by the C++ core.

Every strategy is a small dataclass whose fields are the algorithm's
parameters; ``name`` selects the C++ implementation.
"""
from dataclasses import asdict, dataclass
from typing import ClassVar, Dict


class Strategy:
    name: ClassVar[str]
    label: ClassVar[str]

    def params(self) -> Dict[str, float]:
        return {k: float(v) for k, v in asdict(self).items()}


@dataclass(frozen=True)
class FlatBid(Strategy):
    """Baseline: bid base_mult * value in every auction until the budget runs out."""
    name: ClassVar[str] = "flat"
    label: ClassVar[str] = "Flat bid"
    base_mult: float = 1.0


@dataclass(frozen=True)
class PidThrottle(Strategy):
    """PID-controlled throttling of participation probability."""
    name: ClassVar[str] = "pid"
    label: ClassVar[str] = "PID throttling"
    base_mult: float = 1.0
    kp: float = 0.05
    ki: float = 0.01
    kd: float = 0.0
    initial_rate: float = 1.0
    min_rate: float = 0.0


@dataclass(frozen=True)
class DualAscent(Strategy):
    """Lagrangian bid multiplier: bid = value / (1 + lambda), lambda by dual ascent."""
    name: ClassVar[str] = "dual"
    label: ClassVar[str] = "Dual ascent"
    base_mult: float = 1.0
    eta: float = 0.3
    lambda0: float = 0.0


@dataclass(frozen=True)
class MultiplicativePacing(Strategy):
    """Multiplicative pacing: bid multiplier scaled by exp(gain * spend error)."""
    name: ClassVar[str] = "multiplicative"
    label: ClassVar[str] = "Multiplicative pacing"
    base_mult: float = 1.0
    gain: float = 0.1
    initial_m: float = 1.0
    m_min: float = 0.05
    m_max: float = 1.0


def default_strategies(rule: str = "second_price"):
    """Default line-up. First-price bids are shaded (base_mult < 1) for every
    strategy so the comparison is not dominated by zero-surplus bidding."""
    base = 1.0 if rule == "second_price" else 0.6
    return [FlatBid(base), PidThrottle(base_mult=base), DualAscent(base_mult=base),
            MultiplicativePacing(base_mult=base)]
