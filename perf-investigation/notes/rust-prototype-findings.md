# Would a Rust/pyo3 rewrite of nbformat's hot path help? — prototype findings

**Scope:** a throwaway pyo3 crate (`<scratch>/rust-proto`, `nbf_rust`) implementing three variants of
nbformat's v4/v4.5 hot path (`reads`, `writes`, `validate`), benchmarked against the real
`nbformat` 5.11.1 on the same corpus, and checked for byte/structural correctness against it.
Not proposed for merge as-is — see effort estimate at the end.

## Bottom line

- **`writes()` (V2, serialize straight from the live object graph, no `deepcopy`): the only
  unambiguous win.** 4–7x faster than `nbformat.writes`, and this is not exotic Rust magic — it's
  mostly *not doing the two redundant full-tree walks Python's implementation does*
  (`copy.deepcopy` + a second tree that gets built during `json.dumps`). A pure-Python fix
  along the same lines (serialize from the original tree, apply `split_lines`/`strip_transient`
  logic during serialization instead of via full-tree rewrites first) would recover a large
  fraction of this win **without any Rust at all** — worth trying before reaching for pyo3.
- **`validate()` (V3, Rust `jsonschema` crate on raw bytes, never touching Python objects): also a
  clear win**, 3–7.5x, and the *fused* bytes→validated-NotebookNode pipeline beats
  `nbformat.reads` by 3.8–6x. Some of this margin is not "Rust is fast," it's "we didn't import
  `jsonschema`/`fastjsonschema`/`traitlets`" — see the memory section.
- **`reads()` (V1, drop-in NotebookNode-returning replacement): marginal to negative.** Once you
  are required to hand back a tree of real `NotebookNode`/`dict`/`list`/`str` Python objects,
  you are paying CPython's object-allocation cost no matter what language walked the JSON — and
  that cost dominates. V1 beats `nbformat.reads` by 3–7x (because Python's `from_dict` walks the
  tree *twice more*, once for `from_dict` and once for `rejoin_lines`+`strip_transient`, all in
  pure-Python bytecode), but it is **at or below the `json.loads` floor** on 4 of 5 corpus files
  (0.72x–1.39x of `json.loads`, i.e. sometimes *slower*). **If Python objects must come out the
  other end, Rust cannot give you a `reads()` that meaningfully beats `json.loads` — the ceiling
  is the floor.** This is the single most important number for scoping any future work: don't
  fund a rewrite hoping for a fast drop-in `reads()`.
- **Recommendation:** the win is real and worth funding *only* for `writes()` and `validate()`
  specifically, and only if the maintainers are prepared to accept the build/distribution burden
  below (rough estimate: 3–5 weeks for a production-quality version of just those two, plus
  ongoing multi-platform wheel maintenance). A `reads()` rewrite is not worth doing in Rust; if
  `reads()` speed matters, look at `from_dict`/`rejoin_lines` being pure-Python-bytecode-heavy
  first (see "where Python's reads() actually loses time" below) — that's a Python-only fix.

## Environment

Python 3.11.15, nbformat 5.11.1 (editable install), pyo3 0.22.6 (default ABI, not abi3),
serde_json 1.0 (`preserve_order`, `float_roundtrip`), `jsonschema` (Rust crate) 0.18.3 compiled
for Draft4 against `nbformat/v4/nbformat.v4.5.schema.json` embedded at compile time via
`include_str!`. Built with `maturin develop --release`. Crate: `<scratch>/rust-proto/src/lib.rs`
(~530 lines). Corpus: `<scratch>/corpus/{tiny,small,medium,large,image_heavy}.ipynb`.

## Measured numbers

### Stage 1 — `reads()`

```
notebook         MB  json.loads  nbf.reads  rust.reads  rust/loads  rust/nbf
tiny           0.01    0.026ms    0.231ms    0.033ms      1.26x     0.14x  (rust IS the floor here, dominated by fixed overhead)
small          0.13    0.305ms    1.749ms    0.264ms      0.87x     0.15x
medium         0.81    2.086ms   11.720ms    2.602ms      1.25x     0.22x
large          3.68   10.034ms   55.054ms   13.921ms      1.39x     0.25x
image_heavy    3.00    3.420ms    8.601ms    2.569ms      0.75x     0.30x
```
Read the "rust/loads" column as the headline: it hovers around **1.0x** (0.75x–1.39x). Rust wins
big over `nbformat.reads` (4–7x, "rust/nbf" inverted) purely because `nbformat.reads` does
`json.loads` → pure-Python `from_dict` (builds a *second* full tree, one `NotebookNode(dict-comp)`
call per dict, isinstance checks per value) → pure-Python `rejoin_lines` (walks `nb.cells` again,
attribute access per field) → `strip_transient`. That's 3 extra full-tree passes in Python
bytecode. Rust collapses all three into one pass over `serde_json::Value`, but the *unavoidable*
cost — allocating a `NotebookNode`/`dict`/`str`/`list` Python object for every JSON node — is still
paid, in Rust exactly as in Python, because it goes through the same CPython allocator either way.
`json.loads` pays that same object-allocation cost and nothing else, which is why V1 can't clear it.

### Stage 2 — `writes()`

```
notebook         MB  json.dumps  nbf.writes  rust.writes  rust/dumps  rust/nbf
tiny           0.01    0.111ms    0.460ms    0.067ms      0.60x     0.14x
small          0.13    0.995ms    4.254ms    1.003ms      1.01x     0.24x
medium         0.81    6.566ms   29.395ms    6.378ms      0.97x     0.22x
large          3.68   31.020ms  149.656ms   32.643ms      1.05x     0.22x
image_heavy    3.00   19.377ms   30.691ms    7.860ms      0.41x     0.26x
```
`rust.writes` is **4.2x–6.9x faster than `nbformat.writes`**, and — notably — it lands right at
the `json.dumps` floor (0.41x–1.05x of it), *sometimes beating plain `json.dumps` on already-parsed
dicts*, because it never materializes the deep-copied+re-split intermediate tree that
`json.dumps` in the Python baseline is handed; it streams output directly while walking the live
object graph once. This is the outcome the task predicted, and it holds up: `nbformat.writes` does
`copy.deepcopy(nb)` (full tree, one Python-level dict/list alloc per node) → `split_lines` (another
full walk) → `strip_transient` → `json.dumps` (a third full walk, in C, but over the
already-3x-rebuilt tree). Rust does exactly one walk. Output was byte-identical to
`nbformat.writes()` on every corpus file and every in-scope test-suite notebook (see Correctness).

### Stage 3 — `validate()`, and fused `reads`+`validate`

```
notebook         MB  nbf.validate  rust.validate  speedup
tiny           0.01    0.138ms    0.018ms    7.53x
small          0.13    1.109ms    0.166ms    6.67x
medium         0.81    6.804ms    1.169ms    5.82x
large          3.68   33.579ms    5.912ms    5.68x
image_heavy    3.00    3.893ms    1.306ms    2.98x

fused (bytes -> validated NotebookNode):
tiny           0.01     0.225ms (nbf.reads)     0.037ms (rust)   6.06x
small          0.13     1.764ms                 0.304ms          5.80x
medium         0.81    11.982ms                 2.742ms          4.37x
large          3.68    59.869ms                15.775ms          3.80x
image_heavy    3.00     9.296ms                 2.471ms          3.76x
```
`nbformat.validate()` already uses `fastjsonschema` (compiled validator) when available, so this
isn't "compiled schema beats interpreted schema" — it's Rust's `jsonschema` crate validating a
`serde_json::Value` directly vs. Python calling into a C-compiled-but-still-per-instance-Python-call
validator over a `NotebookNode` tree, plus `nbformat.validate()`'s own overhead (`get_validator`
cache lookup, version dispatch, `_normalize`/id-repair pass — see Correctness below). image_heavy's
smaller 2.98x reflects that most of its bytes are base64 blobs the schema barely inspects (`type:
string`), so validation cost there is dominated by just *touching* every string once — a place
where Rust's advantage over CPython string handling is real but proportionally smaller.

### Memory

Two numbers, and they disagree on purpose — see caveat.

**tracemalloc peak** (Python-allocator-visible only; **blind to Rust's own heap** — serde_json
trees, the compiled jsonschema validator, Rust `String`/`Vec` buffers never touch `PyMem`/obmalloc):
```
reads:   tiny 0.04/0.03MB · small 0.25/0.24MB · medium 1.55/1.49MB · large 7.22/6.97MB · image_heavy 3.42/3.39MB   (nbf / rust)
writes:  tiny 0.10/0.01MB · small 1.14/0.17MB · medium 7.08/1.08MB · large 32.15/4.89MB · image_heavy 8.62/3.12MB  (nbf / rust)
validate: essentially 0 for both (schema validation doesn't build new Python objects on either side)
```
`rust.writes`'s tracemalloc number *looks* dramatically better (32MB→4.9MB on `large`), but that's
largely real: `nbformat.writes`'s `deepcopy` really does allocate a full duplicate Python object
tree that `rust.writes` never builds — this is a genuine, not illusory, memory win, consistent with
the timing win.

**Fresh-process peak RSS** (one `python -c` process per cell, single call — total memory including
whatever the Rust extension allocates on its own heap; see `<scratch>/bench/rss_subprocess.py`):
```
notebook      json.loads  nbf.reads  rust.reads  nbf.writes  rust.writes  nbf.validate  rust.validate
tiny              10.4MB      32.6MB      23.6MB      32.6MB      34.0MB      32.6MB      13.3MB
small             10.5MB      33.0MB      24.0MB      33.0MB      34.3MB      33.0MB      13.6MB
medium            11.3MB      34.9MB      27.2MB      38.8MB      37.7MB      35.1MB      15.4MB
large             18.0MB      43.0MB      40.5MB      73.6MB      54.1MB      43.1MB      23.4MB
image_heavy       15.4MB      39.0MB      32.8MB      42.6MB      47.9MB      39.0MB      19.4MB
```
Important caveat baked into these numbers: **most of the `nbf.*` vs `rust.*` RSS gap is import
weight, not algorithm memory.** `import nbformat` pulls in `traitlets`, `jsonschema`,
`fastjsonschema`, and the v1/v2/v3/v4 subpackages regardless of which function you call;
`rust.reads` only imports the tiny `nbformat.notebooknode` module (to get the `NotebookNode`
class), and `rust.validate` imports nothing from nbformat at all (schema is compiled into the
`.so`). That is a legitimate operational advantage of a Rust extension (smaller footprint for,
say, a validation-only service that never needs the rest of nbformat) — but it is a different
claim from "Rust validates more memory-efficiently than fastjsonschema," which these numbers
cannot actually isolate. `rust.writes` on `large` (54MB) vs `nbf.writes` (73.6MB) is the one row
where the gap is plausibly mostly algorithmic (both already paid the `import nbformat` cost by
the time `writes()` runs), and it lines up with the tracemalloc deepcopy-avoidance story above.

**Caveat on both metrics, stated plainly (as the task asked):** tracemalloc undercounts Rust
variants (blind to non-Python heap) in the *upward* direction — it makes Rust look *cheaper* than
it is. RSS high-water-mark undercounts in the *comparability* direction — it's dominated by which
libraries got imported, is monotonic for the process lifetime (a later small call can't show a
smaller number than an earlier big one — this bit us in the first draft of `bench_rust.py`'s
in-process RSS sampling, which is why the final harness also does single-call fresh-process
sampling for the RSS table). Neither number alone is trustworthy for "how much RAM does the
algorithm need"; use tracemalloc for the Python-object cost and the fresh-process table only for
whole-process footprint comparisons.

## Where the win comes from, and where it evaporates

- **Comes from:** eliminating redundant full-tree Python-level passes (`writes`'s `deepcopy` +
  rebuild; `reads`'s `from_dict` + `rejoin_lines` + `strip_transient` as three separate walks
  instead of one), and moving string/schema work into Rust where a `char`-level loop is far
  cheaper than the equivalent Python bytecode loop.
- **Evaporates the moment Python objects must exist at the boundary.** V1 makes this concrete:
  building `n` `NotebookNode`/`dict`/`str`/`list` objects costs the same whether the recursive
  walk that decides *what* to build was written in Rust or Python, because each `PyDict_New`/
  `PyUnicode_FromStringAndSize`/etc. call is CPython allocator work, not walk work. The walk was
  never the bottleneck for `reads()` in the first place, relative to `json.loads`'s baseline — the
  bottleneck *nbformat.reads()* actually has (vs. `json.loads`) is the pure-Python multi-pass
  wrapping logic, which V1 does fix, and does very well (3–7x over `nbformat.reads`) — it just
  can't do better than what `json.loads` already spends on object construction, which is most of
  the time.
- **Also evaporates on outputs dominated by data the schema/serializer barely touches**
  (`image_heavy`'s base64 blobs): the win shrinks from ~5-7x on structurally rich notebooks to
  ~3x, because a large fraction of both the Python and Rust implementations' time is simply
  copying/scanning long opaque strings, where the two languages are closer in relative (if not
  absolute) cost.

## Correctness gates

Ran on all 5 corpus notebooks + all 20 notebooks under `/home/user/nbformat/tests/`
(`<scratch>/bench/correctness.py`). Final result after scoping out genuinely out-of-scope cases
(see below): **19/19 in-scope `writes()` byte-identical, 17/19 in-scope `reads()` structurally
identical (2 explained, not bugs — see below), 18/19 in-scope `validate()` agreements (1
explained)**. v1/v2/v3-format notebooks (6 files) were excluded from `reads`/`writes` comparison —
V1/V2 only implement the v4 `rwbase` rules, not `convert()`; extending to older formats is
additional, well-scoped work, not a blocker.

Three **genuine, non-bug findings** surfaced by the gates — these are about `nbformat`'s actual
semantics, and matter for anyone else attempting this rewrite:

1. **`nbformat.reads()`/`validate()` silently mutate the notebook.** `nbformat/validator.py`'s
   `_normalize()` (called from `validate()`, called from `reads()`) injects a fresh `id` into any
   v4.5+ cell missing one, and rewrites duplicate cell ids, *in place*, before running schema
   validation — so `nbformat.reads()` on a notebook missing cell ids returns a notebook **with**
   ids it invents, and `nbformat.validate()` on the same raw dict reports it valid (after silently
   repairing it). A validator/reader that faithfully validates/parses the *bytes as given*, with
   no side effects (both `nbf_rust.reads` and `nbf_rust.validate_json` do this, correctly, by the
   letter of the task) will disagree with `nbformat` here — not because it's wrong, but because
   `nbformat.reads`/`validate` are not actually pure functions of their input. Reproduced on
   `tests/v4_5_no_cell_id.ipynb` and `tests/invalid_unique_cell_id.ipynb`. **Any reimplementation
   claiming drop-in compatibility must replicate this repair-and-mutate behavior explicitly, or
   document the divergence loudly** — it's exactly the kind of surprise that turns into a
   production incident report.
2. **`validate()`'s schema selection is per-`nbformat_minor`, not just per-major-version.**
   `nbformat` picks among `v4.0`..`v4.5` schema files based on the notebook's declared
   `nbformat_minor` (`get_validator`/`_get_schema_json`); this prototype's V3 hardcodes the v4.5
   schema (as scoped by the task). Forcing both sides to validate against v4.5 gives clean
   agreement (18/19, one explained by finding #1); validating a v4.0-declared notebook against
   v4.5 will predictably disagree on schema-only-in-4.5 requirements (e.g. cell `id`). A
   production version needs `N` compiled schemas (one per minor, `v4.0`..`v4.5` today, growing
   over time), not one — not hard, but not zero effort, and it means the compiled-validator cache
   needs the same lifecycle nbformat's `validators` dict already has.
3. **`strip_transient` only strips from the *top-level* `metadata` and each cell's `metadata`,
   nowhere else.** Confirmed by gate 1's byte-for-byte pass — worth stating because it would be
   an easy scope mistake to over-apply the strip rule to nested metadata dicts (e.g. inside
   `outputs`), which real nbformat does not do.

## JSON-semantics divergences (Rust `serde_json`/`jsonschema` vs. Python `json`)

Directly probed with crafted inputs (see transcript); this is one of the most useful outputs of
the exercise, independent of speed:

| Case | Python `json` | Rust `serde_json` (this prototype) | Verdict |
|---|---|---|---|
| **Integers beyond ±2⁶³/2⁶⁴** | Arbitrary precision, exact | **Silently downcast to `f64`, losing precision** (`123456789012345678901234567890` → `1.2345678901234568e+29`, and worse, comes back as the *wrong type* — a Python `float`, not `int`) | **Real bug class.** Fixable with serde_json's `arbitrary_precision` feature (parses big ints as an opaque string-backed `Number`, converted to Python `int` via `PyLong_FromString`), at a small parsing-cost tax. Untested in the current prototype — flag before shipping. |
| **`NaN`/`Infinity`/`-Infinity` literals** | Parsed by default (`json.loads` accepts them; strictly non-conformant JSON but Python's `json` allows it) | **Rejected — hard parse error.** `serde_json::from_str` treats them as invalid JSON, full stop. | Real divergence. A notebook that today round-trips through `nbformat.reads`/`writes` because some tool wrote a literal `NaN` into JSON will **fail to parse at all** in the Rust reader. Writing NaN/Inf (V2, from a live Python float) works fine since it delegates to Python's own `repr()` + json's constant strings — the asymmetry (write ok, read broken) is itself worth flagging. |
| **Lone UTF-16 surrogates in strings** (e.g. an unpaired `\ud800` escape, or content that arrived via `errors="surrogateescape"`) | Represented directly; Python `str` can legally hold isolated surrogate code points | **Cannot cross the pyo3 FFI boundary as `&str` at all.** Passing such a Python `str` into any `#[pyfunction]` taking `&str` (used by every function in this prototype, `reads`/`writes`/`validate_json`) raises `UnicodeEncodeError: 'utf-8' codec can't encode ... surrogates not allowed` **before Rust code runs**, because Rust `String`/`str` are required to be valid UTF-8 and cannot represent surrogate code points. | **This is the sharpest, least-obvious finding.** Any real-world notebook containing mis-decoded bytes in a string field (this happens — corrupted terminal output captured as `text/plain`, improperly decoded subprocess output, etc.) that Python happily reads/writes today would **hard-crash** a naive pyo3 bridge. A production port needs to either (a) accept this as a documented incompatibility, or (b) do byte-level marshaling (`PyUnicode_AsEncodedString(..., "utf-8", "surrogatepass")` on the way in/out) instead of the ergonomic `&str` pyo3 gives by default — real, non-trivial engineering work, not a one-liner. |
| **Duplicate object keys** | Last value wins (`json.loads('{"a":1,"a":2}')` → `{"a": 2}`) | Same — last value wins (confirmed) | No divergence. |
| **`sort_keys` ordering on non-ASCII / astral keys** | Sorts by Unicode code point (Python `str.__lt__`) | Rust `str`/`String` `Ord` sorts by UTF-8 byte sequence, which is code-point-order-preserving for well-formed UTF-8 | No divergence (verified with `☺`/`𝔘`/mixed-case keys) — but this is a property that happens to hold, not a coincidence-proof guarantee if either side ever mishandles surrogate-encoded input (see row above). |
| **Float formatting** (`repr`-shortest-roundtrip, scientific-notation threshold, `-0.0`, subnormals) | `float.__repr__` (shortest round-trip digit string, `1e16`→`'1e+16'`, `1e15`→`'1000000000000000.0'`, etc.) | **This prototype sidesteps the problem entirely for `writes()`**: rather than reimplementing CPython's dtoa-shortest-repr algorithm in Rust (a real undertaking — Rust's own `{}` `Display` for `f64` does *not* match, e.g. it never switches to scientific notation), V2 calls back into Python's own `repr()` on the `PyFloat` object it's holding, so formatting is byte-identical by construction (verified with `0.1, 1e300, 1e-300, -0.0, 1e16, 1e15, NaN, inf, -inf, pi`). **This works for `writes()` because we already hold the live Python float object; it would not work for a Rust-only `reads()` that needs to hand back a value some other Rust code formats** — worth remembering if scope ever grows to "format floats in Rust for real" (e.g. a Rust-side re-serializer that doesn't touch Python at all). No corpus notebook or test-suite fixture contains any float value at all, so this path is verified only by hand-constructed cases, not by the corpus. |

## Build / distribution burden (the part that doesn't show up in a benchmark)

This is the actual cost side of the ledger, and it's substantial relative to the win:

- **Wheels per platform × per Python minor.** nbformat currently ships a pure-Python wheel —
  one artifact covers every OS/arch/Python version. A compiled extension needs a wheel per
  (OS × arch × CPython minor) combination CI builds: at minimum linux (manylinux, glibc) x86_64
  + aarch64, macOS x86_64 + arm64, Windows x86_64 — ×however many CPython minors are supported
  (nbformat's `requires-python = ">=3.10"` today implies 3.10–3.13+ and climbing) — that's easily
  15-25+ wheel builds per release, each needing its own CI runner/toolchain, vs. today's one.
- **musl / Alpine.** A separate manylinux vs. musllinux wheel matrix; Alpine-based Docker images
  (common in data/ML deployments) would otherwise fall back to source build (see below) unless
  musl wheels are also published.
- **Free-threaded (3.13t/3.14t) builds.** pyo3 support for the free-threaded ABI is still
  maturing; this prototype was not tested against a free-threaded interpreter at all. Would need
  its own wheel variant and its own correctness pass (no-GIL changes what "safe to hold a
  `Bound<'py, PyAny>` across X" means in subtle ways).
- **PyPy.** pyo3 has PyPy support but it is a second-class, slower-maturing target with its own
  gotchas (different refcounting/GC behavior visible through the C API compatibility layer); would
  need explicit testing, and some `nbformat` users are PyPy users specifically for speed, making
  a "the fast version doesn't cleanly support PyPy" story an awkward one.
- **Source-build fallback.** Platforms without a prebuilt wheel (e.g. exotic Linux arches,
  some corporate air-gapped mirrors that only permit pure-Python sdists) fall back to `pip`
  building from source, which requires a Rust toolchain at install time — a new hard requirement
  nbformat has never had. This is the kind of thing that breaks CI in downstream projects that
  pin nbformat and build in minimal/locked-down containers, quietly, until someone reports it.
  A pure-Python fallback implementation would need to be maintained in parallel (or accept the
  install-time Rust-toolchain requirement, which is a real adoption-friction cost for a package
  as widely-depended-upon as nbformat).
- **Two implementations to keep in sync, forever.** Every future JSON-schema-quirk fix or
  `rwbase.py` behavior change needs to land in both the Python reference implementation (kept, if
  only as the source-build fallback and for non-CPython platforms) and the Rust one, doubling the
  review/test surface for every future PR touching this code path.

## Effort estimate

- **Just `writes()` (V2) + `validate()` (V3), production quality, common platforms only**
  (manylinux x86_64/aarch64, macOS, Windows; CPython 3.10-3.13, no PyPy/free-threaded/musl):
  **~3-5 weeks** — fix the big-int and surrogate-string edge cases above properly (not sidestep
  them), build out the per-minor schema cache, wire CI wheel builds + a pure-Python fallback path,
  write the compatibility test suite this prototype only sketched.
- **Adding `reads()` "for completeness"** given the finding that it can't beat `json.loads`
  when Python objects must be returned: **not recommended** — if pursued anyway for API symmetry,
  add another 1-2 weeks, but set expectations that it will not look like a win in a benchmark.
- **Full platform matrix (musl, free-threaded, PyPy) + long-term maintenance**: open-ended,
  meaningfully larger than the above — realistically the dominant cost of this project over its
  lifetime, not the initial port.
- **Net:** the speed and memory wins for `writes`/`validate` are real and reproducible, but they
  are not free, and a chunk of the `writes()` win is achievable in pure Python by not
  deep-copying (worth prototyping *that* first, cheaply, before committing to Rust). Fund this
  only if (a) `writes()`/`validate()` are demonstrably a bottleneck for real users at the sizes
  where the win is largest (multi-MB notebooks), and (b) the team is willing to own a compiled
  wheel matrix indefinitely.

## Files

- Crate: `<scratch>/rust-proto/` (`src/lib.rs`, `Cargo.toml`, `pyproject.toml`)
- Benchmark: `<scratch>/bench/bench_rust.py` (timing + tracemalloc), `<scratch>/bench/rss_subprocess.py`
  (fresh-process peak RSS)
- Correctness gates: `<scratch>/bench/correctness.py`
- This file: `<scratch>/notes/rust-prototype-findings.md`
