from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup

ext = Pybind11Extension(
    "pacerlab._core",
    ["cpp/src/bindings.cpp", "cpp/src/simulator.cpp", "cpp/src/strategy.cpp"],
    include_dirs=["cpp/include"],
    cxx_std=17,
    extra_compile_args=["-O3"],
)

setup(ext_modules=[ext], cmdclass={"build_ext": build_ext})
