#include "pacerlab/strategy.hpp"

#include <algorithm>
#include <cmath>
#include <set>
#include <stdexcept>

#include "pacerlab/rng.hpp"

namespace pacerlab {
namespace {

// Reads parameters with defaults and rejects typos.
class ParamReader {
 public:
  ParamReader(const std::string& who, const Params& p) : who_(who), p_(p) {}
  double get(const std::string& key, double def) {
    known_.insert(key);
    auto it = p_.find(key);
    return it == p_.end() ? def : it->second;
  }
  void finish() const {
    for (const auto& kv : p_)
      if (!known_.count(kv.first))
        throw std::invalid_argument("unknown parameter '" + kv.first + "' for strategy " + who_);
  }

 private:
  std::string who_;
  const Params& p_;
  std::set<std::string> known_;
};

// Spend error in units of "average per-bucket budget": positive = underspending.
double norm_error(const Schedule& s, int bucket, double spent_cum) {
  const double unit = s.budget / s.n_buckets();
  return (s.target_cum[bucket + 1] - spent_cum) / unit;
}

// Baseline: bid base_mult * value, always, until the budget is gone.
class FlatBid : public Strategy {
 public:
  explicit FlatBid(double mult) : mult_(mult) {}
  double bid(double v) override { return mult_ * v; }
  void on_bucket_end(int, double) override {}
  std::string name() const override { return "flat"; }

 private:
  double mult_;
};

// PID-controlled throttling: bid base_mult * value but participate in each
// auction with probability `rate`, which a PID loop steers so cumulative spend
// follows the target curve.
class PidThrottle : public Strategy {
 public:
  PidThrottle(double mult, double kp, double ki, double kd, double rate0, double min_rate,
              const Schedule& s, unsigned long long seed)
      : mult_(mult), kp_(kp), ki_(ki), kd_(kd), base_(rate0), min_rate_(min_rate),
        rate_(rate0), s_(s), rng_(seed) {}
  double bid(double v) override { return rng_.uniform() < rate_ ? mult_ * v : 0.0; }
  void on_bucket_end(int b, double spent) override {
    const double e = norm_error(s_, b, spent);
    const double d = e - prev_e_;
    prev_e_ = e;
    const double u_unsat = base_ + kp_ * e + ki_ * (integral_ + e) + kd_ * d;
    // Anti-windup: freeze the integrator while the output is saturated in the
    // direction the error is pushing.
    if (!((u_unsat > 1.0 && e > 0) || (u_unsat < min_rate_ && e < 0))) integral_ += e;
    rate_ = std::clamp(base_ + kp_ * e + ki_ * integral_ + kd_ * d, min_rate_, 1.0);
  }
  std::string name() const override { return "pid"; }

 private:
  double mult_, kp_, ki_, kd_, base_, min_rate_, rate_;
  double integral_ = 0.0, prev_e_ = 0.0;
  Schedule s_;
  Rng rng_;
};

// Dual ascent on the budget constraint's Lagrange multiplier lambda. The
// Lagrangian-optimal bid is value / (1 + lambda); lambda follows projected
// subgradient ascent: lambda <- max(0, lambda + eta * (spend - target spend)).
class DualAscent : public Strategy {
 public:
  DualAscent(double mult, double eta, double lambda0, const Schedule& s)
      : mult_(mult), eta_(eta), lambda_(lambda0), s_(s) {}
  double bid(double v) override { return mult_ * v / (1.0 + lambda_); }
  void on_bucket_end(int b, double spent) override {
    const double unit = s_.budget / s_.n_buckets();
    const double bucket_spend = spent - last_spent_;
    last_spent_ = spent;
    const double target = s_.target_cum[b + 1] - s_.target_cum[b];
    lambda_ = std::max(0.0, lambda_ + eta_ * (bucket_spend - target) / unit);
  }
  std::string name() const override { return "dual"; }

 private:
  double mult_, eta_, lambda_, last_spent_ = 0.0;
  Schedule s_;
};

// Multiplicative pacing: bid = base_mult * m * value where m is scaled by
// exp(gain * clipped error) every bucket.
class MultiplicativePacing : public Strategy {
 public:
  MultiplicativePacing(double mult, double gain, double m0, double m_min, double m_max,
                       const Schedule& s)
      : mult_(mult), gain_(gain), m_(m0), m_min_(m_min), m_max_(m_max), s_(s) {}
  double bid(double v) override { return mult_ * m_ * v; }
  void on_bucket_end(int b, double spent) override {
    const double e = std::clamp(norm_error(s_, b, spent), -1.0, 1.0);
    m_ = std::clamp(m_ * std::exp(gain_ * e), m_min_, m_max_);
  }
  std::string name() const override { return "multiplicative"; }

 private:
  double mult_, gain_, m_, m_min_, m_max_;
  Schedule s_;
};

}  // namespace

std::unique_ptr<Strategy> make_strategy(const std::string& name, const Params& params,
                                        const Schedule& s, unsigned long long seed) {
  if (s.n_buckets() < 1 || !(s.budget > 0.0))
    throw std::invalid_argument("schedule needs a positive budget and at least one bucket");
  ParamReader p(name, params);
  const double mult = p.get("base_mult", 1.0);
  if (!(mult > 0.0)) throw std::invalid_argument("base_mult must be positive");
  std::unique_ptr<Strategy> out;
  if (name == "flat") {
    out = std::make_unique<FlatBid>(mult);
  } else if (name == "pid") {
    const double min_rate = p.get("min_rate", 0.0);
    const double rate0 = p.get("initial_rate", 1.0);
    if (min_rate < 0.0 || min_rate > 1.0 || rate0 < 0.0 || rate0 > 1.0)
      throw std::invalid_argument("pid rates must lie in [0, 1]");
    out = std::make_unique<PidThrottle>(mult, p.get("kp", 0.05), p.get("ki", 0.01),
                                        p.get("kd", 0.0), rate0, min_rate, s, seed);
  } else if (name == "dual") {
    out = std::make_unique<DualAscent>(mult, p.get("eta", 0.3), p.get("lambda0", 0.0), s);
  } else if (name == "multiplicative") {
    const double lo = p.get("m_min", 0.05), hi = p.get("m_max", 1.0);
    if (!(lo > 0.0) || hi < lo) throw std::invalid_argument("need 0 < m_min <= m_max");
    out = std::make_unique<MultiplicativePacing>(mult, p.get("gain", 0.1),
                                                 p.get("initial_m", 1.0), lo, hi, s);
  } else {
    throw std::invalid_argument("unknown strategy '" + name + "'");
  }
  p.finish();
  return out;
}

}  // namespace pacerlab
