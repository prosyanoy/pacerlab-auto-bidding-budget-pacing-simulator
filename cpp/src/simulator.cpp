#include "pacerlab/simulator.hpp"

#include <algorithm>
#include <stdexcept>

namespace pacerlab {

double clearing_price(AuctionRule rule, double bid, double comp_bid, double reserve) {
  if (rule == AuctionRule::FirstPrice) return bid;
  return std::max(comp_bid, reserve);
}

Result simulate(const Traffic& tr, const AuctionConfig& cfg, const Schedule& schedule,
                Strategy& strategy) {
  const int B = schedule.n_buckets();
  if (B < 1) throw std::invalid_argument("schedule needs at least one bucket");
  Result r;
  r.spend.assign(B, 0.0);
  r.value.assign(B, 0.0);
  r.auctions.assign(B, 0);
  r.entered.assign(B, 0);
  r.wins.assign(B, 0);

  double spent = 0.0;
  int cur = 0;
  double prev_t = 0.0;
  for (std::size_t i = 0; i < tr.n; ++i) {
    const double t = tr.time[i];
    if (!(t >= prev_t) || t < 0.0 || t >= 1.0)
      throw std::invalid_argument("traffic time must be non-decreasing within [0, 1)");
    prev_t = t;
    const int b = std::min(B - 1, static_cast<int>(t * B));
    while (cur < b) strategy.on_bucket_end(cur++, spent);

    r.auctions[b]++;
    const double bid = strategy.bid(tr.value[i]);
    if (!(bid > 0.0)) continue;
    r.entered[b]++;
    if (bid < cfg.reserve || bid <= tr.comp_bid[i]) continue;
    const double price = clearing_price(cfg.rule, bid, tr.comp_bid[i], cfg.reserve);
    if (spent + price > schedule.budget) continue;  // cannot afford
    spent += price;
    r.spend[b] += price;
    r.value[b] += tr.value[i];
    r.wins[b]++;
  }
  while (cur < B) strategy.on_bucket_end(cur++, spent);
  return r;
}

}  // namespace pacerlab
