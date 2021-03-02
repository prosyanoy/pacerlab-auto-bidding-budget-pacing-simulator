"""Synthetic auction traffic with diurnal seasonality."""
from dataclasses import dataclass, field

import numpy as np

# (share of traffic, log-mean of value, log-sigma of value) per query class,
# e.g. generic browse / product-intent / high-intent brand queries.
DEFAULT_QUERY_CLASSES = ((0.55, -0.4, 0.5), (0.35, 0.3, 0.6), (0.10, 1.1, 0.5))


@dataclass(frozen=True)
class TrafficConfig:
    n_auctions: int = 300_000
    # Intensity(t) = 1 + a1*cos(2pi(t - peak)) + a2*cos(4pi(t - peak2)), t in [0,1) = one day.
    amp_daily: float = 0.6
    peak: float = 0.80  # ~19:00 evening peak
    amp_second: float = 0.2
    peak2: float = 0.55  # smaller lunchtime bump
    query_classes: tuple = DEFAULT_QUERY_CLASSES
    # Competitor top bid: log c = mu + rho*(log v - E log v) + noise; rho couples it to value.
    comp_log_mean: float = -0.35
    comp_log_sigma: float = 0.45
    comp_value_corr: float = 0.5
    # Competition intensifies at traffic peaks: bids scaled by (1 + k * (intensity - 1)).
    comp_peak_sensitivity: float = 0.25


@dataclass
class Traffic:
    time: np.ndarray  # sorted, in [0, 1)
    value: np.ndarray  # expected conversion value if we win the impression
    comp_bid: np.ndarray  # highest competing bid
    query_class: np.ndarray
    config: TrafficConfig = field(repr=False, default=None)

    def __len__(self) -> int:
        return len(self.time)


def intensity(t, cfg: TrafficConfig = TrafficConfig()):
    """Relative traffic intensity (mean ~1 over the day, always positive)."""
    t = np.asarray(t, dtype=float)
    out = (1.0 + cfg.amp_daily * np.cos(2 * np.pi * (t - cfg.peak))
           + cfg.amp_second * np.cos(4 * np.pi * (t - cfg.peak2)))
    return out


def _sample_times(rng, n, cfg):
    # Inverse-CDF sampling from the intensity on a fine grid.
    grid = np.linspace(0.0, 1.0, 4097)
    lam = np.maximum(intensity(grid, cfg), 1e-6)
    cdf = np.concatenate([[0.0], np.cumsum((lam[1:] + lam[:-1]) / 2)])
    cdf /= cdf[-1]
    t = np.interp(np.sort(rng.random(n)), cdf, grid)
    return np.minimum(t, np.nextafter(1.0, 0.0))


def generate_traffic(cfg: TrafficConfig = TrafficConfig(), seed: int = 0) -> Traffic:
    if cfg.n_auctions < 1:
        raise ValueError("n_auctions must be >= 1")
    if not (cfg.amp_daily + cfg.amp_second < 1.0):
        raise ValueError("amp_daily + amp_second must be < 1 to keep intensity positive")
    rng = np.random.default_rng(seed)
    n = cfg.n_auctions
    t = _sample_times(rng, n, cfg)
    shares = np.array([c[0] for c in cfg.query_classes], dtype=float)
    mus = np.array([c[1] for c in cfg.query_classes])
    sigmas = np.array([c[2] for c in cfg.query_classes])
    qc = rng.choice(len(shares), size=n, p=shares / shares.sum())
    log_v = mus[qc] + sigmas[qc] * rng.standard_normal(n)
    value = np.exp(log_v)
    mean_log_v = float(np.sum(shares / shares.sum() * mus))
    log_c = (cfg.comp_log_mean + cfg.comp_value_corr * (log_v - mean_log_v)
             + cfg.comp_log_sigma * rng.standard_normal(n))
    pressure = 1.0 + cfg.comp_peak_sensitivity * (intensity(t, cfg) - 1.0)
    comp = np.exp(log_c) * pressure
    return Traffic(t, value, comp, qc, cfg)
