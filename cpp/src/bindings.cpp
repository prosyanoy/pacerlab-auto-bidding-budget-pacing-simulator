#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "pacerlab/simulator.hpp"

namespace py = pybind11;
using namespace pacerlab;

using DArr = py::array_t<double, py::array::c_style | py::array::forcecast>;

template <class T>
static py::array_t<T> to_np(const std::vector<T>& v) {
  py::array_t<T> a(v.size());
  std::copy(v.begin(), v.end(), a.mutable_data());
  return a;
}

static py::dict run(DArr time, DArr value, DArr comp_bid, const std::string& rule,
                    double reserve, double budget, DArr target_cum,
                    const std::string& strategy, const Params& params,
                    unsigned long long seed) {
  if (time.ndim() != 1 || value.ndim() != 1 || comp_bid.ndim() != 1 || target_cum.ndim() != 1)
    throw std::invalid_argument("arrays must be 1-D");
  if (value.size() != time.size() || comp_bid.size() != time.size())
    throw std::invalid_argument("time, value and comp_bid must have equal length");
  AuctionConfig cfg;
  if (rule == "first_price") cfg.rule = AuctionRule::FirstPrice;
  else if (rule == "second_price") cfg.rule = AuctionRule::SecondPrice;
  else throw std::invalid_argument("rule must be 'first_price' or 'second_price'");
  if (reserve < 0.0) throw std::invalid_argument("reserve must be >= 0");
  cfg.reserve = reserve;
  Schedule sched;
  sched.budget = budget;
  sched.target_cum.assign(target_cum.data(), target_cum.data() + target_cum.size());
  auto strat = make_strategy(strategy, params, sched, seed);
  Traffic tr{time.data(), value.data(), comp_bid.data(), static_cast<std::size_t>(time.size())};
  Result res;
  {
    py::gil_scoped_release release;
    res = simulate(tr, cfg, sched, *strat);
  }
  py::dict d;
  d["spend"] = to_np(res.spend);
  d["value"] = to_np(res.value);
  d["auctions"] = to_np(res.auctions);
  d["entered"] = to_np(res.entered);
  d["wins"] = to_np(res.wins);
  return d;
}

PYBIND11_MODULE(_core, m) {
  m.doc() = "PacerLab C++ auction simulation core";
  m.def("run", &run, py::arg("time"), py::arg("value"), py::arg("comp_bid"), py::arg("rule"),
        py::arg("reserve"), py::arg("budget"), py::arg("target_cum"), py::arg("strategy"),
        py::arg("params"), py::arg("seed"),
        "Simulate one day of auctions; returns per-bucket spend/value/auction/entered/win arrays.");
}
