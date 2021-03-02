"""Command line: ``python -m pacerlab`` / ``pacerlab``."""
import argparse
import time

import pandas as pd

from .config import Settings
from .evaluation import RULES, compare, evaluate
from .traffic import TrafficConfig, generate_traffic


def main(argv=None) -> int:
    s = Settings.from_env()
    p = argparse.ArgumentParser(prog="pacerlab", description=__doc__)
    p.add_argument("--rule", choices=RULES, default=s.auction_rule)
    p.add_argument("--auctions", type=int, default=s.n_auctions)
    p.add_argument("--buckets", type=int, default=s.n_buckets)
    p.add_argument("--budget-ratio", type=float, default=s.budget_ratio,
                   help="budget as a fraction of unconstrained spend")
    p.add_argument("--seed", type=int, default=s.seed)
    p.add_argument("--runs", type=int, default=1, help="average over this many traffic seeds")
    p.add_argument("--plot", metavar="PNG", help="save side-by-side spend curves to this file")
    a = p.parse_args(argv)

    pd.set_option("display.width", 200)
    cfg = TrafficConfig(n_auctions=a.auctions)
    kw = dict(rule=a.rule, budget_ratio=a.budget_ratio, n_buckets=a.buckets)
    if a.runs > 1:
        print(evaluate(range(a.seed, a.seed + a.runs), cfg, **kw).round(4).to_string())
        return 0
    tr = generate_traffic(cfg, a.seed)
    t0 = time.perf_counter()
    df, results = compare(tr, seed=a.seed, **kw)
    dt = time.perf_counter() - t0
    print(df.round(4).to_string())
    print(f"\n{len(df)} strategies x {a.auctions:,} auctions in {dt:.3f}s "
          f"({len(df) * a.auctions / dt / 1e6:.1f}M auctions/s incl. Python overhead)")
    if a.plot:
        import matplotlib
        matplotlib.use("Agg")
        from .plotting import spend_curve_figure
        spend_curve_figure(results).savefig(a.plot, dpi=130)
        print(f"saved {a.plot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
