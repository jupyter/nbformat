# Would a Rust + pyo3 rewrite of nbformat's hot path help?

Exploratory investigation. **Nothing here is proposed for merge** except the one
`_struct.py` change described below, which is on this branch as a separate commit.

## Question

Would rewriting nbformat's most common use case — `read()` / `validate()` /
`write()` of a v4 notebook — in Rust with pyo3 bindings meaningfully improve
speed and memory?

## Answer

**Mostly no, and the parts where it would help are cheaper to fix in Python.**

The measured Python overhead is real (`reads` is 5.5× raw `json.loads`, `writes`
is 4.8× raw `json.dumps`), but almost all of it turns out to be *redundant work*
rather than *Python being slow*. A working Rust prototype confirms this: where
Rust wins, it wins by not doing the redundant work — which Python can also stop
doing.

The one place Rust has a genuine, non-replicable advantage is **schema
validation on raw bytes** (5.5×, and near-zero Python memory because it never
builds an object graph). That is also the smallest, most self-contained piece —
and it does not require rewriting nbformat to obtain.

## Measured results

Baseline, this machine, CPython 3.11, synthetic corpus (`bench/gen_corpus.py`):

| notebook | MB | `json.loads` | `nbf.reads` | `validate` | `nbf.writes` | `json.dumps` |
|---|---|---|---|---|---|---|
| small | 0.13 | 0.30ms | 1.83ms | 1.13ms | 3.96ms | 0.91ms |
| medium | 0.81 | 2.00ms | 11.05ms | 7.11ms | 26.97ms | 6.46ms |
| large | 3.68 | 10.27ms | 58.04ms | 35.65ms | 137.25ms | 28.38ms |
| image_heavy | 3.00 | 3.36ms | 8.33ms | 3.75ms | 30.32ms | 18.91ms |

Rust prototype (`rust-proto/`, three variants) vs Python, and vs the
`json.loads`/`json.dumps` floor — the floor matters because any drop-in
replacement must still hand back Python objects:

| notebook | reads vs nbf | **reads vs floor** | writes vs nbf | **writes vs floor** | validate vs nbf |
|---|---|---|---|---|---|
| small | 6.95× | **1.13×** | 4.52× | 1.03× | 7.13× |
| medium | 5.33× | **0.94×** | 4.64× | 1.03× | 5.72× |
| large | 4.22× | **0.75×** | 5.13× | 0.99× | 5.48× |
| image_heavy | 3.85× | **1.48×** | 3.81× | 2.44× | 2.92× |

### Reading these numbers

- **`reads` in Rust is at or *below* the `json.loads` floor** (0.75×–1.48×).
  Once you must return real `NotebookNode`/`dict`/`str` objects, CPython's
  object-allocation cost dominates and it does not matter what language walked
  the JSON. `json.loads` already pays exactly that cost and nothing else. **A
  Rust `reads()` cannot win. This is a hard ceiling, not a tuning problem.**
- **`writes` in Rust lands exactly on the `json.dumps` floor** (0.99×–1.03×) —
  meaning the entire 4.5–5× win is from eliminating the `deepcopy` + full tree
  rebuild that `nbformat.writes()` currently does, *not* from Rust. Pure Python
  can eliminate the same redundant passes.
- **`validate` is the one real Rust win**: 5.5× and near-zero Python memory,
  because it validates the raw text without materializing an object graph.
  Python cannot do this — it must build objects to validate them.

`image_heavy` behaves differently throughout because base64 image payloads are
long single strings: `split_lines` work dominates and the tree is shallow.

## The competing pure-Python plan

The profiling arm (`notes/python-profile-findings.md`) found **~45% of the
overhead is removable without Rust**:

| change | win | risk |
|---|---|---|
| Drop the redundant per-instance `_allownew` set (see below) | ~20% memory | none — zero behaviour change |
| Single-pass write transform (replace `deepcopy` → `split_lines` → `strip_transient` with one non-mutating walk) | 1.30× on that stage, byte-identical output verified | medium (larger diff) |
| `orjson` for the serialize path | `dumps` stage 17.4× alone; `writes()` 2.6–4.7× combined | **changes the on-disk format** — orjson's indent is fixed at 2 spaces, nbformat uses 1 |

Combining only the two safe changes: round trip 203ms → 172ms (1.18×, no
behaviour change). With orjson: → 111ms (1.83×) but at the cost of a disclosed
on-disk format change, which for a format library is a serious thing to spend.

**After those, the remaining ~55% is JSON-Schema validation via
`fastjsonschema`** — already the fastest option in the Python ecosystem, with
irreducible `oneOf` backtracking cost (measured: 8,560 exception objects built
and discarded per read). That residue is exactly the piece Rust addresses, and
it is worth roughly a further 1.5–2× on an already-optimized baseline — not a
fresh 5×.

## Findings that matter regardless of the Rust decision

These came out of holding a second implementation against the first, and are
arguably worth more than the performance result:

1. **`validate()` mutates its argument in place.** Verified directly: reading
   `tests/v4_5_no_cell_id.ipynb` and calling `validate()` silently injects
   generated cell `id`s (`[<ABSENT>]` → `['e7400a8a']`). A side-effect-free
   implementation *correctly* disagrees with nbformat here. This is a
   documented-ish repair behaviour, but a validator that mutates is a surprising
   API contract and it is the single biggest obstacle to swapping in any
   alternative implementation.
2. **Lone UTF-16 surrogates break any naive pyo3 bridge.** Python round-trips
   `"bad \ud800 surrogate"` in output text without complaint; passing that
   string across a pyo3 `&str` boundary raises `UnicodeEncodeError` *before Rust
   runs*. Corrupted terminal output saved into a notebook is a real-world source
   of these. Verified directly.
3. **`serde_json` silently downcasts integers beyond ±2⁶³ to lossy `f64`.**
   Needs the `arbitrary_precision` feature; untested here.
4. **`NaN`/`Infinity` asymmetry.** Python's `json.loads` accepts them (non-
   conformant but permitted); `serde_json` rejects them on read. nbformat can
   currently read notebooks a strict Rust reader would refuse.
5. **The most important format rules are not in the schema.** Cell-`id`
   uniqueness lives in `validator.py` control flow, not in the `.schema.json`
   files, because JSON Schema cannot express cross-field uniqueness. Any second
   implementation must reimplement it from prose.

## Distribution cost

nbformat is currently pure Python with **zero compiled dependencies**, supports
Python 3.10–3.14 on Linux/macOS/Windows, and sits at the bottom of the Jupyter
stack (nbconvert, nbclient, jupyter-server, papermill). Going compiled means:

- ~15–25 wheels per release instead of 1, plus musl/Alpine variants
- free-threaded CPython and PyPy are untested and second-class in pyo3
- a source-build fallback now requires a Rust toolchain at install time
- **Pyodide / JupyterLite** — nbformat runs in the browser today; a compiled
  extension needs an emscripten build target
- two implementations to keep in sync, permanently

Effort estimate for production-quality Rust `writes()` + `validate()` on common
platforms only: **3–5 weeks**, with open-ended ongoing platform-matrix cost.

## Recommendation

1. **Do not pursue a Rust `reads()`.** It cannot beat `json.loads`. Settled.
2. **Take the free memory win now** (below) — it is on this branch.
3. **Consider the single-pass write transform** in pure Python. It captures most
   of what Rust's `writes()` offered, with no packaging consequences.
4. **Treat the test split as the valuable standalone work.** See
   `notes/test-taxonomy.md`. It is worth doing on its own merits and is a
   prerequisite for *ever* validating a second implementation.
5. **If Rust is ever revisited, scope it to validation only**, as an optional
   accelerator (`pip install nbformat[fast]`) that nbformat falls back from —
   never as a hard dependency. That preserves the pure-Python install.

## The one change proposed for merge

`Struct.__init__` did `object.__setattr__(self, "_allownew", True)` even though
`_allownew = True` is already the class default. That forced **every**
`NotebookNode` to materialize a 304-byte instance `__dict__` — larger than the
208-byte node itself — to hold one redundant bool.

Removing it, measured on this corpus:

| notebook | peak mem before | after | vs `json.loads` |
|---|---|---|---|
| large | 7.22MB | 5.79MB (−19.8%) | 1.53× → 1.23× |
| medium | 1.50MB | 1.25MB | 1.52× → 1.22× |

Semantics verified preserved: `allow_new_attr(False)` still works, new keys are
still refused afterwards, and `deepcopy` still carries `_allownew=False` across.
Full suite green (193 passed). The profiling arm also reported a speed bonus
from this change; in my own runs that was within noise, so I claim only the
memory result.

## Layout

```
notes/rust-prototype-findings.md   Rust prototype: full tables, correctness gates, JSON-semantics divergences
notes/python-profile-findings.md   Control arm: per-stage attribution, memory root-cause, pure-Python wins
notes/test-taxonomy.md             196 tests classified format-conformance vs Python-specific; refactor plan
rust-proto/                        pyo3 crate: reads / writes / validate_json / read_validate
bench/                             corpus generator, benchmarks, correctness gates, profilers
```

### Reproducing

The bench scripts contain **hardcoded absolute scratch paths** from the session
that produced them and need their `CORPUS`/path constants adjusted before reuse.
Build the crate with `maturin develop` inside a venv that has nbformat
installed, then:

```
python bench/gen_corpus.py <corpus-dir>   # generate the corpus
python bench/bench.py <corpus-dir>        # Python baseline
python bench/bench_rust.py                # Python vs Rust, all three variants
python bench/correctness.py               # byte-identical / structural gates
```

Correctness gate result as run: `writes` **19/19 byte-identical**; `reads` 17/19
and `validate` 18/19, with every divergence traced to finding #1 or #2 above
rather than to a prototype bug.
