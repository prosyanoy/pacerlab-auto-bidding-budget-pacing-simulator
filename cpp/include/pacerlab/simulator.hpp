#pragma once
#include <cstddef>
#include <vector>

#include "pacerlab/strategy.hpp"

namespace pacerlab {

enum class AuctionRule { FirstPrice, SecondPrice };

// Time-ordered auction stream (non-owning views). time is in [0, 1).
struct Traffic {
  const double* time;      // non-decreasing
  const double* value;     // value to us if we win
  const double* comp_bid;  // highest competing bid
  std::size_t n;
};

struct AuctionConfig {
  AuctionRule rule = AuctionRule::SecondPrice;
  double reserve = 0.0;
};

// Per-bucket accounting.
struct Result {
  std::vector<double> spend, value;
  std::vector<long long> auctions, entered, wins;
};

// Ties go to the competitor. A win that the remaining budget cannot cover is
// not taken, so total spend never exceeds schedule.budget.
Result simulate(const Traffic& traffic, const AuctionConfig& cfg, const Schedule& schedule,
                Strategy& strategy);

// Price paid by a winning bid (exposed for unit tests).
double clearing_price(AuctionRule rule, double bid, double comp_bid, double reserve);

}  // namespace pacerlab
