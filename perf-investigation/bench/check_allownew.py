"""Verify the _allownew change preserves semantics, and measure its effect."""
import copy
import gc
import json
import sys
import time
import tracemalloc

from nbformat.notebooknode import NotebookNode
import nbformat

# --- semantics ---
n = NotebookNode({"a": 1})
print("instance __dict__ after init:", n.__dict__)
c = copy.deepcopy(n)
print("deepcopy ok:", c == n, "| copy __dict__:", c.__dict__)
n.allow_new_attr(False)
print("allow_new_attr(False) works, _allownew =", n._allownew)
try:
    n["newkey"] = 1
    print("!! BUG: allowed new key")
except Exception as e:
    print("correctly refused new key:", type(e).__name__)
m = NotebookNode({"b": 2})
m["z"] = 1
print("fresh node still allows new keys:", "z" in m)
d = copy.deepcopy(n)
print("deepcopy preserves _allownew=False:", d._allownew is False)

# --- measurement ---
CORPUS = "/tmp/claude-0/-home-user-nbformat/4daa7540-3a45-57cd-84ee-987a6735721f/scratchpad/corpus"


def timeit(fn, arg, min_time=0.3):
    fn(arg)
    reps, t0 = 0, time.perf_counter()
    while True:
        fn(arg)
        reps += 1
        el = time.perf_counter() - t0
        if el > min_time and reps >= 3:
            return el / reps


def peak_mb(fn, arg):
    gc.collect()
    tracemalloc.start()
    fn(arg)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak / 1e6


print()
hdr = f"{'notebook':12s} {'MB':>6s} {'reads':>9s} {'writes':>10s} {'memNBF':>8s} {'memJSON':>8s} {'ratio':>6s}"
print(hdr)
print("-" * len(hdr))
for name in ["tiny", "small", "medium", "large", "image_heavy"]:
    src = open(f"{CORPUS}/{name}.ipynb", encoding="utf-8").read()
    nb = nbformat.reads(src, as_version=4)
    tr = timeit(lambda s: nbformat.reads(s, as_version=4), src)
    tw = timeit(nbformat.writes, nb)
    mr = peak_mb(lambda s: nbformat.reads(s, as_version=4), src)
    mj = peak_mb(json.loads, src)
    print(
        f"{name:12s} {len(src)/1e6:6.2f} {tr*1e3:7.2f}ms {tw*1e3:8.2f}ms "
        f"{mr:6.2f}MB {mj:6.2f}MB {mr/mj:5.2f}x"
    )
