"""Python vs Rust(pyo3) prototype benchmark across the nbformat hot path.

Prints one table per stage (reads/writes/validate + fused read+validate),
timings and memory. Two memory numbers are reported per cell because they
measure different things:

  * tracemalloc peak (Python side): only sees allocations made through
    CPython's allocator. It is blind to memory the Rust extension allocates
    itself (serde_json::Value trees, the jsonschema validator's internal
    structures, Rust-side Strings/Vecs) -- those never go through
    PyMem/obmalloc, so a Rust variant can look artificially "cheap" on this
    metric even when it is allocating plenty of heap.
  * RSS delta (via resource.getrusage(RUSAGE_SELF).ru_maxrss, sampled
    before/after a batch): catches process-wide memory including Rust's own
    heap, but is noisier (allocator retains freed pages, GC timing, page
    granularity) and is a high-water-mark over the whole run, not a single
    call's peak.

Neither is perfect. Use tracemalloc to see "how much Python-object weight
did this add", and the RSS delta to sanity check total process growth
(especially for the Rust variants, where tracemalloc alone would be
misleading).
"""
import gc
import json
import os
import resource
import statistics
import sys
import time
import tracemalloc

SCRATCH = "/tmp/claude-0/-home-user-nbformat/4daa7540-3a45-57cd-84ee-987a6735721f/scratchpad"
CORPUS = os.path.join(SCRATCH, "corpus")

import nbformat
from nbformat import validate, reads, writes

import nbf_rust

NOTEBOOKS = ["tiny", "small", "medium", "large", "image_heavy"]


def timeit(fn, arg, min_time=0.35, min_reps=5):
    fn(arg)  # warm
    reps, t0 = 0, time.perf_counter()
    while True:
        fn(arg)
        reps += 1
        el = time.perf_counter() - t0
        if el > min_time and reps >= min_reps:
            return el / reps


def peak_mb_tracemalloc(fn, arg):
    gc.collect()
    tracemalloc.start()
    fn(arg)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak / 1e6


def rss_delta_mb(fn, arg, reps=30):
    gc.collect()
    rss0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    for _ in range(reps):
        fn(arg)
    gc.collect()
    rss1 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # ru_maxrss is KB on Linux, a monotonic high-water-mark for the process
    return max(0, rss1 - rss0) / 1e3


def fmt_ms(t):
    return f"{t*1e3:8.3f}ms"


def fmt_mb(m):
    return f"{m:7.2f}MB"


def section(title):
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)


# ------------------------------------------------------------------
# Load corpus
# ------------------------------------------------------------------
data = {}
for name in NOTEBOOKS:
    p = os.path.join(CORPUS, name + ".ipynb")
    src = open(p, encoding="utf-8").read()
    nb = reads(src, as_version=4)
    data[name] = dict(src=src, size_mb=len(src.encode("utf-8")) / 1e6, nb=nb)

# ======================================================================
# STAGE 1: reads()  --  json.loads (floor) vs nbformat.reads vs rust V1
# ======================================================================
section("STAGE 1 -- reads(): json.loads (floor) vs nbformat.reads (python) vs nbf_rust.reads (V1)")
hdr = (
    f"{'notebook':12s} {'MB':>6s} {'json.loads':>11s} {'nbf.reads':>10s} {'rust.reads':>11s} "
    f"{'rust/loads':>10s} {'rust/nbf':>9s} | {'mem loads':>9s} {'mem nbf':>8s} {'mem rust(tm)':>12s} {'rssΔ nbf':>9s} {'rssΔ rust':>9s}"
)
print(hdr)
print("-" * len(hdr))
reads_rows = []
for name in NOTEBOOKS:
    src = data[name]["src"]
    t_loads = timeit(json.loads, src)
    t_nbf = timeit(lambda s: reads(s, as_version=4), src)
    t_rust = timeit(nbf_rust.reads, src)

    m_loads = peak_mb_tracemalloc(json.loads, src)
    m_nbf = peak_mb_tracemalloc(lambda s: reads(s, as_version=4), src)
    m_rust_tm = peak_mb_tracemalloc(nbf_rust.reads, src)  # only sees the Python-object part
    rss_nbf = rss_delta_mb(lambda s: reads(s, as_version=4), src)
    rss_rust = rss_delta_mb(nbf_rust.reads, src)

    reads_rows.append((name, t_loads, t_nbf, t_rust, m_loads, m_nbf, m_rust_tm, rss_nbf, rss_rust))
    print(
        f"{name:12s} {data[name]['size_mb']:6.2f} {fmt_ms(t_loads)} {fmt_ms(t_nbf)} {fmt_ms(t_rust)} "
        f"{t_rust/t_loads:9.2f}x {t_rust/t_nbf:8.2f}x | {fmt_mb(m_loads)} {fmt_mb(m_nbf)} {fmt_mb(m_rust_tm)} "
        f"{fmt_mb(rss_nbf)} {fmt_mb(rss_rust)}"
    )

# ======================================================================
# STAGE 2: writes()  --  json.dumps (floor) vs nbformat.writes vs rust V2
# ======================================================================
section("STAGE 2 -- writes(): json.dumps (floor) vs nbformat.writes (python, deepcopy+rebuild) vs nbf_rust.writes (V2, in-place)")
hdr = (
    f"{'notebook':12s} {'MB':>6s} {'json.dumps':>11s} {'nbf.writes':>11s} {'rust.writes':>12s} "
    f"{'rust/dumps':>10s} {'rust/nbf':>9s} | {'mem nbf(tm)':>11s} {'mem rust(tm)':>12s} {'rssΔ nbf':>9s} {'rssΔ rust':>9s}"
)
print(hdr)
print("-" * len(hdr))
writes_rows = []
for name in NOTEBOOKS:
    nb = data[name]["nb"]
    nb_plain = json.loads(data[name]["src"])
    t_dumps = timeit(
        lambda n: json.dumps(n, indent=1, sort_keys=True, separators=(",", ": "), ensure_ascii=False),
        nb_plain,
    )
    t_nbf = timeit(writes, nb)
    t_rust = timeit(nbf_rust.writes, nb)

    assert writes(nb) == nbf_rust.writes(nb), f"BYTE MISMATCH for {name}!"

    m_nbf = peak_mb_tracemalloc(writes, nb)
    m_rust_tm = peak_mb_tracemalloc(nbf_rust.writes, nb)
    rss_nbf = rss_delta_mb(writes, nb)
    rss_rust = rss_delta_mb(nbf_rust.writes, nb)

    writes_rows.append((name, t_dumps, t_nbf, t_rust, m_nbf, m_rust_tm, rss_nbf, rss_rust))
    print(
        f"{name:12s} {data[name]['size_mb']:6.2f} {fmt_ms(t_dumps)} {fmt_ms(t_nbf)} {fmt_ms(t_rust)} "
        f"{t_rust/t_dumps:9.2f}x {t_rust/t_nbf:8.2f}x | {fmt_mb(m_nbf)} {fmt_mb(m_rust_tm)} {fmt_mb(rss_nbf)} {fmt_mb(rss_rust)}"
    )
print("(byte-identical output verified for every row above)")

# ======================================================================
# STAGE 3: validate()  --  python (jsonschema/fastjsonschema via nbformat)
#          vs rust V3 (validate straight from source text, no Python objs)
#          + fused read_validate (bytes -> validate -> NotebookNode)
# ======================================================================
section("STAGE 3 -- validate(): nbformat.validate (python, on NotebookNode) vs nbf_rust.validate_json (V3, on raw text)")
hdr = (
    f"{'notebook':12s} {'MB':>6s} {'nbf.validate':>13s} {'rust.validate':>14s} {'speedup':>8s} | "
    f"{'mem nbf(tm)':>11s} {'mem rust(tm)':>12s}"
)
print(hdr)
print("-" * len(hdr))
validate_rows = []
for name in NOTEBOOKS:
    nb = data[name]["nb"]
    src = data[name]["src"]
    t_nbf = timeit(validate, nb)
    t_rust = timeit(nbf_rust.validate_json, src)

    m_nbf = peak_mb_tracemalloc(validate, nb)
    m_rust_tm = peak_mb_tracemalloc(nbf_rust.validate_json, src)

    validate_rows.append((name, t_nbf, t_rust))
    print(
        f"{name:12s} {data[name]['size_mb']:6.2f} {fmt_ms(t_nbf)} {fmt_ms(t_rust)} {t_nbf/t_rust:7.2f}x | "
        f"{fmt_mb(m_nbf)} {fmt_mb(m_rust_tm)}"
    )

section("STAGE 3b -- fused pipeline: bytes -> NotebookNode, validated")
hdr = (
    f"{'notebook':12s} {'MB':>6s} {'python(reads=parse+convert+validate)':>38s} "
    f"{'rust(read_validate fused)':>27s} {'speedup':>8s}"
)
print(hdr)
print("-" * len(hdr))
fused_rows = []
for name in NOTEBOOKS:
    src = data[name]["src"]
    t_py = timeit(lambda s: reads(s, as_version=4), src)  # parse+convert(no-op)+validate
    t_rust = timeit(nbf_rust.read_validate, src)
    fused_rows.append((name, t_py, t_rust))
    print(f"{name:12s} {data[name]['size_mb']:6.2f} {fmt_ms(t_py):>38s} {fmt_ms(t_rust):>27s} {t_py/t_rust:7.2f}x")

# ======================================================================
# SUMMARY
# ======================================================================
section("SUMMARY -- speedup vs python, and vs the json floor")
print(f"{'notebook':12s} {'reads(rust/nbf)':>16s} {'reads(rust/json-floor)':>23s} "
      f"{'writes(rust/nbf)':>17s} {'writes(rust/json-floor)':>24s} {'validate(rust)':>15s} {'fused(rust/nbf.reads)':>22s}")
for i, name in enumerate(NOTEBOOKS):
    _, t_loads, t_nbf_r, t_rust_r, *_ = reads_rows[i]
    _, t_dumps, t_nbf_w, t_rust_w, *_ = writes_rows[i]
    _, tv_nbf, tv_rust = validate_rows[i]
    _, tf_py, tf_rust = fused_rows[i]
    print(
        f"{name:12s} {t_nbf_r/t_rust_r:15.2f}x {t_loads/t_rust_r:22.2f}x "
        f"{t_nbf_w/t_rust_w:16.2f}x {t_dumps/t_rust_w:23.2f}x {tv_nbf/tv_rust:14.2f}x {tf_py/tf_rust:21.2f}x"
    )

print()
print("NOTE: tracemalloc numbers for the rust functions ONLY capture the")
print("Python objects they construct (e.g. reads()'s NotebookNode tree) --")
print("they are blind to memory serde_json / the jsonschema validator")
print("allocate on the Rust heap. rssΔ columns approximate total process")
print("growth instead but are noisy (allocator retains pages, GC timing).")
