#pragma once
#include <map>
#include <memory>
#include <string>
#include <vector>

namespace pacerlab {

// Pacing schedule shared by all strategies: the budget, and the target
// *cumulative* spend at every bucket edge (size n_buckets + 1).
struct Schedule {
  double budget = 0.0;
  std::vector<double> target_cum;
  int n_buckets() const { return static_cast<int>(target_cum.size()) - 1; }
};

// One interface for every bidding / pacing algorithm.
//   bid():           called once per auction; returns the bid, or <= 0 to abstain
//                    (throttling strategies abstain instead of lowering the bid).
//   on_bucket_end(): called after each control interval with the cumulative spend,
//                    which is where feedback controllers update their state.
class Strategy {
 public:
  virtual ~Strategy() = default;
  virtual double bid(double value) = 0;
  virtual void on_bucket_end(int bucket, double spent_cum) = 0;
  virtual std::string name() const = 0;
};

using Params = std::map<std::string, double>;

// Factory. Names: "flat", "pid", "dual", "multiplicative". Throws
// std::invalid_argument on an unknown name or unknown/invalid parameter.
std::unique_ptr<Strategy> make_strategy(const std::string& name, const Params& params,
                                        const Schedule& schedule, unsigned long long seed);

}  // namespace pacerlab
