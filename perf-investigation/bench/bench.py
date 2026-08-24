"""Baseline benchmark of nbformat's common path: read / validate / write."""
import gc, json, os, statistics, sys, time, tracemalloc

CORPUS = sys.argv[1] if len(sys.argv) > 1 else "corpus"
import nbformat
from nbformat import validate, reads, writes

def timeit(fn, arg, n=None, min_time=0.35):
    fn(arg)  # warm
    reps, t0 = 0, time.perf_counter()
    while True:
        fn(arg); reps += 1
        el = time.perf_counter() - t0
        if (n and reps >= n) or (not n and el > min_time and reps >= 3):
            return el / reps

def peak_mb(fn, arg):
    gc.collect(); tracemalloc.start()
    fn(arg)
    _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    return peak / 1e6

rows = []
for name in ["tiny", "small", "medium", "large", "image_heavy"]:
    p = os.path.join(CORPUS, name + ".ipynb")
    src = open(p, encoding="utf-8").read()
    size = len(src) / 1e6
    nb_plain = json.loads(src)
    nb = reads(src, as_version=4)

    t_json = timeit(json.loads, src)
    t_reads = timeit(lambda s: reads(s, as_version=4), src)
    t_valid = timeit(validate, nb)
    t_write = timeit(lambda n: writes(n), nb)
    t_dumps = timeit(lambda n: json.dumps(n, indent=1, sort_keys=True, separators=(",", ": "), ensure_ascii=False), nb_plain)

    m_reads = peak_mb(lambda s: reads(s, as_version=4), src)
    m_json = peak_mb(json.loads, src)
    rows.append((name, size, t_json, t_reads, t_valid, t_write, t_dumps, m_json, m_reads))

hdr = f"{'notebook':12s} {'MB':>6s} {'json.loads':>11s} {'nbf.reads':>10s} {'validate':>9s} {'nbf.writes':>11s} {'json.dumps':>11s} {'memJSON':>8s} {'memNBF':>7s}"
print(hdr); print("-" * len(hdr))
for n, s, tj, tr, tv, tw, td, mj, mr in rows:
    print(f"{n:12s} {s:6.2f} {tj*1e3:9.2f}ms {tr*1e3:8.2f}ms {tv*1e3:7.2f}ms {tw*1e3:9.2f}ms {td*1e3:9.2f}ms {mj:6.1f}MB {mr:5.1f}MB")
print()
print("Ratios (how much slower than raw json):")
for n, s, tj, tr, tv, tw, td, mj, mr in rows:
    print(f"  {n:12s} reads/loads={tr/tj:5.2f}x   writes/dumps={tw/td:5.2f}x   validate={tv/tj:5.2f}x-of-loads   mem={mr/mj:4.2f}x")
