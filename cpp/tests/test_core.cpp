#include <gtest/gtest.h>

#include <cmath>
#include <stdexcept>
#include <vector>

#include "pacerlab/simulator.hpp"

using namespace pacerlab;

namespace {

Schedule linear_schedule(double budget, int buckets) {
  Schedule s;
  s.budget = budget;
  for (int i = 0; i <= buckets; ++i) s.target_cum.push_back(budget * i / buckets);
  return s;
}

struct Stream {
  std::vector<double> t, v, c;
  Traffic view() const { return {t.data(), v.data(), c.data(), t.size()}; }
};

Stream make_stream(int n, double value, double comp) {
  Stream s;
  for (int i = 0; i < n; ++i) {
    s.t.push_back((i + 0.5) / n);
    s.v.push_back(value);
    s.c.push_back(comp);
  }
  return s;
}

double total(const std::vector<double>& v) {
  double x = 0;
  for (double d : v) x += d;
  return x;
}

}  // namespace

TEST(Price, SecondPriceIgnoresOwnBid) {
  EXPECT_DOUBLE_EQ(clearing_price(AuctionRule::SecondPrice, 5.0, 2.0, 0.0), 2.0);
  EXPECT_DOUBLE_EQ(clearing_price(AuctionRule::SecondPrice, 5.0, 1.0, 1.5), 1.5);
  EXPECT_DOUBLE_EQ(clearing_price(AuctionRule::FirstPrice, 5.0, 2.0, 0.0), 5.0);
}

TEST(Simulator, SecondPriceWinsAndPays) {
  auto s = make_stream(100, 3.0, 1.0);
  auto sched = linear_schedule(1e9, 10);
  auto strat = make_strategy("flat", {}, sched, 1);
  auto r = simulate(s.view(), {AuctionRule::SecondPrice, 0.0}, sched, *strat);
  EXPECT_DOUBLE_EQ(total(r.spend), 100.0);
  EXPECT_DOUBLE_EQ(total(r.value), 300.0);
  long long wins = 0;
  for (auto w : r.wins) wins += w;
  EXPECT_EQ(wins, 100);
}

TEST(Simulator, FirstPricePaysBid) {
  auto s = make_stream(50, 3.0, 1.0);
  auto sched = linear_schedule(1e9, 5);
  auto strat = make_strategy("flat", {{"base_mult", 0.5}}, sched, 1);
  auto r = simulate(s.view(), {AuctionRule::FirstPrice, 0.0}, sched, *strat);
  EXPECT_DOUBLE_EQ(total(r.spend), 50 * 1.5);
}

TEST(Simulator, TieAndReserveLose) {
  auto s = make_stream(10, 2.0, 2.0);  // bid == comp -> loss
  auto sched = linear_schedule(100, 2);
  auto strat = make_strategy("flat", {}, sched, 1);
  auto r = simulate(s.view(), {AuctionRule::SecondPrice, 0.0}, sched, *strat);
  EXPECT_DOUBLE_EQ(total(r.spend), 0.0);
  auto s2 = make_stream(10, 2.0, 0.5);  // bid 2 < reserve 3 -> loss
  auto strat2 = make_strategy("flat", {}, sched, 1);
  auto r2 = simulate(s2.view(), {AuctionRule::SecondPrice, 3.0}, sched, *strat2);
  EXPECT_DOUBLE_EQ(total(r2.spend), 0.0);
}

TEST(Simulator, BudgetIsNeverExceeded) {
  auto s = make_stream(1000, 3.0, 1.0);
  auto sched = linear_schedule(37.5, 10);
  auto strat = make_strategy("flat", {}, sched, 1);
  auto r = simulate(s.view(), {AuctionRule::SecondPrice, 0.0}, sched, *strat);
  EXPECT_LE(total(r.spend), 37.5);
  EXPECT_DOUBLE_EQ(total(r.spend), 37.0);
  // Flat exhausts early: all spend lands in the first buckets.
  EXPECT_DOUBLE_EQ(r.spend.back(), 0.0);
}

TEST(Simulator, RejectsUnsortedTime) {
  Stream s = make_stream(3, 1.0, 0.1);
  s.t[1] = 0.9;
  s.t[2] = 0.1;
  auto sched = linear_schedule(10, 2);
  auto strat = make_strategy("flat", {}, sched, 1);
  EXPECT_THROW(simulate(s.view(), {}, sched, *strat), std::invalid_argument);
}

TEST(Strategies, FactoryValidates) {
  auto sched = linear_schedule(10, 2);
  EXPECT_THROW(make_strategy("nope", {}, sched, 1), std::invalid_argument);
  EXPECT_THROW(make_strategy("flat", {{"typo", 1.0}}, sched, 1), std::invalid_argument);
  EXPECT_THROW(make_strategy("pid", {{"initial_rate", 2.0}}, sched, 1), std::invalid_argument);
  for (const char* n : {"flat", "pid", "dual", "multiplicative"})
    EXPECT_EQ(make_strategy(n, {}, sched, 1)->name(), n);
}

TEST(Strategies, DualRaisesLambdaWhenOverspending) {
  auto sched = linear_schedule(100, 4);
  auto strat = make_strategy("dual", {{"eta", 1.0}}, sched, 1);
  const double before = strat->bid(1.0);
  strat->on_bucket_end(0, 80.0);  // target is 25 -> overspent
  EXPECT_LT(strat->bid(1.0), before);
}

TEST(Strategies, PidThrottlesWhenOverspendingAndRecovers) {
  auto sched = linear_schedule(100, 4);
  auto strat = make_strategy("pid", {{"kp", 1.0}, {"ki", 0.0}}, sched, 7);
  strat->on_bucket_end(0, 100.0);  // massively overspent -> rate 0
  int entered = 0;
  for (int i = 0; i < 200; ++i) entered += strat->bid(1.0) > 0;
  EXPECT_EQ(entered, 0);
  strat->on_bucket_end(1, 0.0);  // now underspent -> rate back at 1
  for (int i = 0; i < 200; ++i) entered += strat->bid(1.0) > 0;
  EXPECT_EQ(entered, 200);
}

TEST(Strategies, SeededThrottlingIsDeterministic) {
  auto sched = linear_schedule(100, 4);
  auto a = make_strategy("pid", {{"initial_rate", 0.5}}, sched, 42);
  auto b = make_strategy("pid", {{"initial_rate", 0.5}}, sched, 42);
  for (int i = 0; i < 100; ++i) EXPECT_EQ(a->bid(1.0) > 0, b->bid(1.0) > 0);
}
