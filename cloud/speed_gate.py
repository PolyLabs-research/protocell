"""A pod's speed in one number, asked right after it boots and before anything is staged on it: the seconds a plain
Python loop takes. This box takes about 0.24; a host that takes several times that is given back (a cpu5c pod once ran
a hundred times slow, with nothing in its quota to say why)."""
import time

t = time.perf_counter()
s = 0
for i in range(5_000_000):
    s += i
print(round(time.perf_counter() - t, 3))
