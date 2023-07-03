#!/usr/bin/env python3

import perkytestlib
perky_dir = perkytestlib.preload_local_perky()

import perky
import sys
import time

TEST_INPUT_TEXT = """

a = b
c = d
# comment inside dict
key with empty value =
dict = {
    inner1=value1
      inner 2 = " value 2  "
      list = [

      a
        b
      # comment inside list


    c
        ]
}

list = [

    1
    2
    3
]

text = '''
    hello

    this is indented

    etc.
    '''

"""

loads = perky.loads
perf_counter = time.perf_counter

stop_after = 0.5

if len(sys.argv) > 1:
    stop_after = float(sys.argv[1])

start_time = perf_counter()
i = 0
while True:
    d = loads(TEST_INPUT_TEXT)
    i += 1
    end_time = perf_counter()
    delta = end_time - start_time
    if delta >= stop_after:
        break

print(f"{i} iterations in {delta} seconds.")
print(f"{i/delta} iterations per second.")
lines = len(TEST_INPUT_TEXT.strip().split("\n"))
print(f"Oooh, call it {(lines*i)/delta} lines per second.")
