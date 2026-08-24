"""Single-call, fresh-process peak-RSS measurement.

ru_maxrss is a monotonically non-decreasing high-water mark for the whole
process, so measuring it mid-run (as bench_rust.py does) is contaminated by
whatever the biggest prior stage already allocated. This script runs each
(variant, notebook) pair in its own fresh subprocess, doing import + exactly
one call, then reports that process's final ru_maxrss -- a clean total
(Python + Rust heap) peak-memory number for that single operation.
"""
import json
import resource
import subprocess
import sys

SCRATCH = "/tmp/claude-0/-home-user-nbformat/4daa7540-3a45-57cd-84ee-987a6735721f/scratchpad"
CORPUS = SCRATCH + "/corpus"
PY = SCRATCH + "/venv/bin/python"

NOTEBOOKS = ["tiny", "small", "medium", "large", "image_heavy"]

VARIANTS = {
    "json.loads": "import json; json.loads(SRC)",
    "nbf.reads": "import nbformat; nbformat.reads(SRC, as_version=4)",
    "rust.reads": "import nbf_rust; nbf_rust.reads(SRC)",
    "nbf.writes": "import nbformat; NB=nbformat.reads(SRC, as_version=4); nbformat.writes(NB)",
    "rust.writes": "import nbformat, nbf_rust; NB=nbformat.reads(SRC, as_version=4); nbf_rust.writes(NB)",
    "nbf.validate": "import nbformat; NB=nbformat.reads(SRC, as_version=4); nbformat.validate(NB)",
    "rust.validate": "import nbf_rust; nbf_rust.validate_json(SRC)",
}

TEMPLATE = """
import resource, sys
SRC = open(sys.argv[1], encoding='utf-8').read()
{code}
print(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
"""

rows = {}
for name in NOTEBOOKS:
    path = f"{CORPUS}/{name}.ipynb"
    rows[name] = {}
    for label, code in VARIANTS.items():
        script = TEMPLATE.format(code=code)
        out = subprocess.run([PY, "-c", script, path], capture_output=True, text=True)
        if out.returncode != 0:
            rows[name][label] = None
            print(f"ERROR {name}/{label}: {out.stderr[-500:]}", file=sys.stderr)
        else:
            rows[name][label] = int(out.stdout.strip().splitlines()[-1]) / 1e3  # KB -> MB

hdr = f"{'notebook':12s} {'json.loads':>11s} {'nbf.reads':>10s} {'rust.reads':>11s} {'nbf.writes':>11s} {'rust.writes':>12s} {'nbf.validate':>13s} {'rust.validate':>14s}"
print(hdr)
print("-" * len(hdr))
for name in NOTEBOOKS:
    r = rows[name]
    def f(x):
        return f"{x:9.1f}MB" if x is not None else "      n/a"
    print(f"{name:12s} {f(r['json.loads'])} {f(r['nbf.reads'])} {f(r['rust.reads'])} {f(r['nbf.writes'])} {f(r['rust.writes'])} {f(r['nbf.validate'])} {f(r['rust.validate'])}")

print()
print("Each cell = peak process RSS (MB) of a fresh python -c interpreter doing")
print("exactly: import site/module -> read corpus file -> ONE call. This is the")
print("whole process's memory (interpreter+stdlib import baseline included), so")
print("read these as comparisons WITHIN a notebook row/column, not absolute bytes")
print("used by the algorithm alone -- interpreter+import baseline is ~8-11MB.")
