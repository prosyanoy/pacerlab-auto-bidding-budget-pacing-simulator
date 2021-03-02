"""Runtime defaults, overridable through PACERLAB_* environment variables."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    n_auctions: int = 300_000
    n_buckets: int = 288  # 5-minute control interval over one day
    budget_ratio: float = 0.35  # budget as a fraction of unconstrained spend
    auction_rule: str = "second_price"
    seed: int = 7

    @classmethod
    def from_env(cls) -> "Settings":
        d = cls()
        g = os.environ.get
        return cls(
            n_auctions=int(g("PACERLAB_N_AUCTIONS", d.n_auctions)),
            n_buckets=int(g("PACERLAB_N_BUCKETS", d.n_buckets)),
            budget_ratio=float(g("PACERLAB_BUDGET_RATIO", d.budget_ratio)),
            auction_rule=g("PACERLAB_AUCTION_RULE", d.auction_rule),
            seed=int(g("PACERLAB_SEED", d.seed)),
        )
