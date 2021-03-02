"""Streamlit dashboard: spend-vs-time curves for each strategy, side by side."""
import matplotlib

matplotlib.use("Agg")
import streamlit as st

from pacerlab import (DualAscent, FlatBid, MultiplicativePacing, PidThrottle, TrafficConfig,
                      compare, generate_traffic)
from pacerlab.config import Settings
from pacerlab.plotting import spend_curve_figure

S = Settings.from_env()
LABELS = [FlatBid.label, PidThrottle.label, DualAscent.label, MultiplicativePacing.label]
st.set_page_config(page_title="PacerLab", layout="wide")
st.title("PacerLab: auto-bidding & budget pacing simulator")
st.caption("Same traffic, same budget, four bidding strategies. The dashed line is the target spend curve.")


@st.cache_data(show_spinner=False)
def simulate(n, seed, rule, ratio, buckets, target_kind, shade, pid, dual_eta, mult_gain):
    tr = generate_traffic(TrafficConfig(n_auctions=n), seed)
    strategies = [FlatBid(shade), PidThrottle(base_mult=shade, kp=pid[0], ki=pid[1], kd=pid[2]),
                  DualAscent(base_mult=shade, eta=dual_eta),
                  MultiplicativePacing(base_mult=shade, gain=mult_gain)]
    df, res = compare(tr, strategies, rule, ratio, buckets, target_kind, seed=seed)
    return tr, df, res


with st.sidebar:
    st.header("Scenario")
    rule = st.radio("Auction rule", ["second_price", "first_price"],
                    index=0 if S.auction_rule == "second_price" else 1, horizontal=True)
    n = st.slider("Auctions per day", 20_000, 2_000_000, S.n_auctions, step=20_000)
    ratio = st.slider("Budget / unconstrained spend", 0.05, 1.0, S.budget_ratio, step=0.05)
    target_kind = st.radio("Target curve", ["traffic", "linear"], horizontal=True)
    seed = st.number_input("Seed", 0, 10_000, S.seed)
    buckets = st.select_slider("Control buckets per day", [48, 96, 144, 288, 576],
                               value=S.n_buckets if S.n_buckets in (48, 96, 144, 288, 576) else 288)
    shade = st.slider("Bid multiplier (shading)", 0.3, 1.0, 1.0 if rule == "second_price" else 0.6, 0.05)
    shown = st.multiselect("Strategies shown", LABELS, default=LABELS)
    st.header("Controller gains")
    kp = st.number_input("PID kp", 0.0, 5.0, 0.05, 0.01, format="%.3f")
    ki = st.number_input("PID ki", 0.0, 5.0, 0.01, 0.005, format="%.3f")
    kd = st.number_input("PID kd", 0.0, 5.0, 0.0, 0.01, format="%.3f")
    eta = st.number_input("Dual-ascent step size", 0.001, 5.0, 0.3, 0.05)
    gain = st.number_input("Multiplicative gain", 0.001, 2.0, 0.1, 0.01)

tr, df, res = simulate(n, int(seed), rule, ratio, buckets, target_kind, shade, (kp, ki, kd), eta, gain)

if not shown:
    st.info("Pick at least one strategy in the sidebar.")
    st.stop()
res = {k: v for k, v in res.items() if k in shown}
df = df.loc[list(res)]

st.subheader("Cumulative spend vs. time")
st.pyplot(spend_curve_figure(res), clear_figure=True)

st.subheader("Metrics")
st.dataframe(df.style.format({
    "budget_utilization": "{:.1%}", "spend_rmse": "{:.4f}", "spend_max_dev": "{:.4f}",
    "win_rate": "{:.1%}", "total_value": "{:,.0f}", "roas": "{:.3f}", "budget_exhausted_at": "{:.2f}"}),
    width="stretch")
st.caption("spend_rmse / spend_max_dev: deviation of cumulative spend from target, as a fraction of budget. "
           "budget_exhausted_at: day fraction at which the budget ran out (1.0 = never early).")
