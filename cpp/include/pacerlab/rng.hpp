#pragma once
#include <cstdint>

namespace pacerlab {

// SplitMix64: tiny, fast, deterministic across platforms (unlike std:: distributions).
class Rng {
 public:
  explicit Rng(uint64_t seed = 0) : state_(seed) {}
  uint64_t next_u64() {
    uint64_t z = (state_ += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
  }
  // Uniform in [0, 1).
  double uniform() { return (next_u64() >> 11) * (1.0 / 9007199254740992.0); }

 private:
  uint64_t state_;
};

}  // namespace pacerlab
