cmake_minimum_required(VERSION 3.14)
project(pacerlab LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

add_library(pacerlab_core STATIC cpp/src/simulator.cpp cpp/src/strategy.cpp)
target_include_directories(pacerlab_core PUBLIC cpp/include)

# C++ unit tests (GoogleTest is fetched at configure time; needs network once).
enable_testing()
include(FetchContent)
FetchContent_Declare(googletest
  URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.zip)
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)
add_executable(pacerlab_tests cpp/tests/test_core.cpp)
target_link_libraries(pacerlab_tests PRIVATE pacerlab_core GTest::gtest_main)
include(GoogleTest)
gtest_discover_tests(pacerlab_tests)
