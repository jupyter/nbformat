# nbformat 5.11.1 profiling: where the 4-5x overhead over raw `json` comes from

Control-arm report for the Rust-rewrite question. All numbers measured on this
box (4 vCPU, Python 3.11.15) with `<SCRATCH>/venv`, warmed processes (schema
validator cached), median of 15-30 reps. Scripts: `bench/stages.py`,
`bench/profile_cprofile.py`, `bench/pyinstrument_run.py`, `bench/combined.py`.

## TL;DR verdict

**Of the current ~5x (read) / ~5x (write) overhead over raw `json`, roughly
half is removable in pure Python (no Rust, no public API break) and half is
intrinsic** — it is the cost of running full JSON-Schema validation
(fastjsonschema, already the fast option) over every cell/output, twice per
naive round trip, plus the genuinely-chosen features (line-split source for
git-friendly diffs, `ensure_ascii=False`, pretty-printed `indent=1`).

Concretely, on `large.ipynb` (1200 cells, 3.68MB):

| | baseline | pure-Python-fixed (byte-identical output) | + orjson (disclosed format change: indent 1→2 space) |
|---|---|---|---|
| `reads()` | 60.5 ms | 55.4 ms (1.09x) | 55.7 ms (1.09x, validate-bound) |
| `writes()` | 142.7 ms | 116.3 ms (1.23x) | 55.6 ms (2.57x) |
| **round trip** | **203.2 ms** | **171.7 ms (1.18x)** | **111.1 ms (1.83x)** |

So: **~15-20% of total overhead is removable with zero behavior change**
(one 1-line bugfix + a refactor), and **another ~35% is removable by
swapping stdlib `json` for `orjson`** in the write path, at the cost of a
disclosed on-disk format change (2-space vs 1-space indent). What's left
after both (~111ms of reads+writes) is **68ms of pure `fastjsonschema`
validation** (paid twice) — that part is intrinsic; a Rust rewrite would
still have to either re-implement JSON-Schema validation or drop it.

---

## 1. Stage-by-stage cost breakdown

Isolated wall-clock timing (no profiler overhead; each stage measured
independently, `bench/stages.py`), unpatched baseline:

### `large.ipynb` (3.68 MB, 1200 cells)

**read** — `nbformat.reads()` actual = 58.96 ms
| stage | ms | % |
|---|---|---|
| `json.loads` | 9.91 | 16.8% |
| `from_dict` (NotebookNode wrap) | 7.40 | 12.6% |
| `rejoin_lines` | 1.58 | 2.7% |
| `strip_transient` | 0.89 | 1.5% |
| **`validate`** | **37.68** | **63.9%** |
| sum of stages | 57.34 | (actual 58.96, 3% profiling slack) |

**write** — `nbformat.writes()` actual = 143.49 ms
| stage | ms | % |
|---|---|---|
| `validate` (writes() re-validates) | 34.48 | 24.0% |
| `copy.deepcopy` | 20.05 | 14.0% |
| `split_lines` | 19.75 | 13.8% |
| `strip_transient` | 0.67 | 0.5% |
| **`json.dumps`** | **65.87** | **45.9%** |
| sum of stages | 140.82 | (actual 143.49) |

Why is `json.dumps` 6.6x slower than `json.loads` on the same notebook?
**Not** the NotebookNode dict-subclass (measured 1.03-1.05x overhead only,
negligible — the C encoder handles dict subclasses fine). It's two things,
measured independently on `nb_plain = json.loads(src)`:

| variant | ms | vs compact |
|---|---|---|
| compact (`json.dumps(nb)`, C accelerator) | 11.10 | 1.00x |
| `ensure_ascii=False` only | 16.16 | 1.46x |
| `sort_keys=True` only | 11.27 | 1.02x (free) |
| `separators` only | 11.06 | 1.00x (free) |
| `indent=1` only | 23.10 | 2.08x |
| **ALL (nbformat's actual kwargs)** | **29.31** | **2.64x** |

**`indent=<anything>` unconditionally disables CPython's C-accelerated JSON
encoder** (`json/encoder.py`'s fast path requires `indent is None`) — this
alone is worth 2.08x, and is the single biggest "removable-only-by-swapping-
libraries" cost in the whole pipeline. `ensure_ascii=False` adds another
1.46x on top (real UTF-8 re-encoding work). `sort_keys`/custom `separators`
are free.

On top of that, **the corpus notebook stores `source` as a single string on
disk**, but `writes()`'s default `split_lines=True` turns it back into a
list-of-lines before dumping — which, combined with `indent=1` pretty-
printing one array element per line, **inflates output size from 3.68MB to
4.88MB (+33%)** and dumps time along with it:

```
writes(nb, split_lines=True)  (default): 147.2 ms, output 4,885,863 bytes
writes(nb, split_lines=False):            87.7 ms, output 3,682,543 bytes
```
This is a genuine, disclosed feature cost (git-diff-friendliness), not a bug
— flagged here because it's easy to mistake for NotebookNode overhead.

### `image_heavy.ipynb` (3.00 MB, 521 nodes, few cells, big base64 blobs)

**read** — actual = 8.44 ms: `json.loads` 3.47ms (41%), `from_dict`+`rejoin`+`strip` 0.92ms (11%), **`validate` 4.06ms (48%)**.

**write** — actual = 30.19 ms: `validate` 3.87ms (13%), `deepcopy` 1.93ms (6%), `split_lines` 1.13ms (4%), strip 0.08ms (0.3%), **`json.dumps` 22.19ms (74%)**.

Image-heavy notebooks are dominated even more by `json.dumps` because most
bytes are opaque base64 strings that still pay the `indent=1` +
`ensure_ascii=False` tax per line-wrapped chunk, with very little tree-
shape overhead (few cells → `from_dict`/`validate` cheap in absolute terms).

### Deterministic vs sampling profilers (the disagreement, as requested)

`cProfile` (bench/profile_cprofile.py), `pyinstrument` (sampling,
1kHz), and `py-spy` (OS-level sampling, no instrumentation) were all run
against `writes(large.ipynb)`. **cProfile's absolute numbers are unusable**
— per-call instrumentation overhead on the ~2.9M `_iterencode_dict`/
`_iterencode_list` frames and ~18k `fastjsonschema` calls inflates a 143ms
call into a 7.4-14s cProfile run (50-100x). But the *relative* attribution
across tools converges:

| stage | cProfile (cumulative %) | pyinstrument (wall %) | py-spy (leaf-sample %) |
|---|---|---|---|
| json encode (`_iterencode*`+`dumps`) | ~64%* | 61.5% | ~48% (leaf-only, excl. `dumps`/`encode` wrapper frames) |
| `validate` | ~16% | 15.5% | ~17% (sum of `validate___definitions_*` leaves) |
| `deepcopy`/`__deepcopy__`/`__setitem__` | ~19%† | 15.7%+? | ~14.2% |
| `split_lines` | ~5% | 5.0% | 6.9% |

(*cProfile's json.encoder cumulative time is dominated by call-count
instrumentation, not real work — treat only the sampling-profiler columns
as trustworthy for absolute proportions.) All three agree on rank order:
**json serialization > validate ≈ deepcopy > split_lines**, which is the
basis for the optimization priority below. A concrete surprise cProfile
surfaces that sampling profilers under-report because each call is cheap:
`fastjsonschema/exceptions.py:__init__` is called **8,560 times per read**
of `large.ipynb` (128,400 / 15 reps) — `oneOf` branches (cell_type,
output_type) in the compiled schema build-and-discard a
`JsonSchemaValueException` for every branch that doesn't match before
finding the one that does. This is ~13% of `validate`'s own time and is
intrinsic to how `fastjsonschema` compiles `oneOf`, not fixable without
restructuring the JSON Schema itself (e.g. a discriminated dispatch on
`cell_type` instead of `oneOf`) — out of scope as a "pure Python" fix.

### Function/object counts (1200-cell `large.ipynb`)

- **`NotebookNode.__setitem__` calls during `reads()`: 0.** `from_dict`
  builds every node via `NotebookNode({k: from_dict(v) ...})`, i.e.
  `dict.__init__` directly — `__setitem__` is never on the read hot path.
- **`NotebookNode.__setitem__` calls during `writes()` (inside
  `copy.deepcopy`): 4,204** — one per non-atomic, non-list value the
  hand-optimized `__deepcopy__` reconstructs.
- **Live `NotebookNode` instances after one `reads()`: 4,258.** `from_dict`
  recurses 17,720 times per read (265,800/15 reps, cProfile) — most of
  those recursive calls walk list elements and leaf (str/int/bool) values,
  which don't allocate a NotebookNode; only dict-typed values do, and
  there are 4,258 of them in `large.ipynb`.
- **Total function calls per `reads()`: ~230k** (cProfile: 3,446,177 calls
  / 15 reps). **Per `writes()`: ~1.88M calls** (28,186,090 / 15 reps) —
  8x more calls than a read, because `copy.deepcopy` + the pure-Python
  JSON encoder both walk the entire tree node-by-node in Python.

---

## 2. Memory attribution

`sys.getsizeof` + live-object counts (`bench` scripts above), all corpus
notebooks, **before any fix**:

| notebook | NotebookNode count | `json.loads` peak | `reads()` peak | ratio |
|---|---|---|---|---|
| tiny | 21 | 0.02 MB | 0.04 MB | 2.23x |
| small | 147 | 0.17 MB | 0.25 MB | 1.53x |
| medium | 892 | 1.02 MB | 1.55 MB | 1.52x |
| large | 4,258 | 4.72 MB | 7.22 MB | 1.53x |
| image_heavy | 521 | 3.12 MB | 3.42 MB | 1.10x |

Per-node cost breakdown (`sys.getsizeof`):

```
plain dict:                     64 bytes
NotebookNode (dict body only):  88 bytes   (+24, from tp_dictoffset/__weakref__ slots — dict-subclass tax, unavoidable without dropping the dict-subclass design entirely)
NotebookNode's instance __dict__: 304 bytes  <-- the real culprit, see below
```

**Root cause, found and fixed:** `Struct.__init__` (`nbformat/_struct.py:49`)
unconditionally does `object.__setattr__(self, "_allownew", True)` — but
`_allownew = True` is *already* the class-level default (`_struct.py:26`).
This redundant instance-level set forces **every single NotebookNode to
materialize its own per-instance `__dict__`** (Python allocates a
minimum-size 8-slot hash table, 304 bytes, even to hold one bool) purely to
store a value identical to the class default. Deleting that one line: the
instance `__dict__` stays empty (`{}`, lazily un-allocated in CPython) for
every node unless a caller explicitly invokes `allow_new_attr()` (rare,
verified only 2 call sites project-wide, both intentional per-instance
overrides that still work correctly after the fix).

Measured effect of deleting that one line (all reps warmed, validator
cache hot):

| notebook | nodes | peak before | peak after | saved | new ratio |
|---|---|---|---|---|---|
| tiny | 21 | 0.04 MB | 0.03 MB | 25% | 1.82x |
| small | 147 | 0.25 MB | 0.20 MB | 20% | 1.23x |
| medium | 892 | 1.55 MB | 1.25 MB | 19% | 1.22x |
| **large** | **4,258** | **7.22 MB** | **5.79 MB** | **19.8% (1.43 MB)** | **1.23x** |
| image_heavy | 521 | 3.42 MB | 3.25 MB | 5% | 1.04x |

`328 bytes/node × node-count` predicts the saved memory almost exactly
(large: 328×4258 = 1.397MB predicted vs 1.43MB measured). **This is a
correctness-neutral, one-line, zero-risk fix** that also has a real (if
smaller) speed benefit (see §3.1).

**Would `__slots__` or dropping the dict-subclass help further?**
Tested a `dict` subclass with `__slots__ = ("_allownew",)`: `sys.getsizeof`
drops from 88 → 72 bytes/node — another 16 bytes/node, 68 KB total on
`large.ipynb`. **Not worth it**: `__slots__` would forbid arbitrary
attribute assignment that some downstream code may rely on (Struct's whole
purpose is dict+attribute flexibility), for a further ~1% memory gain on
top of the already-captured 20%. Dropping the dict-subclass design
entirely (e.g. a plain `dict` + free functions, no attribute access) was
also tested indirectly: `json.dumps` showed only 1.03-1.05x overhead for
the dict-subclass vs plain dict, so **the subclass is not meaningfully
the cost** — the redundant per-instance `__dict__` was. Not subclassing
`dict` would be a large, breaking API change for negligible further gain.

**Deepcopies per read+validate+write round trip:** exactly **1**, and it's
already using the hand-optimized path. `nbformat.validate()` (the public
function used by `reads()`/`writes()`) does **not** deepcopy — only
`isvalid()` and `normalize()` do (one full copy each, confirmed by reading
`validator.py:121` and `:303`; neither is on the `reads()`/`writes()` hot
path). The single deepcopy is `writes()`'s `copy.deepcopy(nb)` before
`split_lines` mutates a copy. Confirmed the hand-written
`NotebookNode.__deepcopy__` (notebooknode.py:23, with the comment
explaining it avoids `copy._reconstruct`) **is actually being hit for
100% of nodes** (4,258/4,258 in profiler traces) and delivers a real
**2.18x speedup over the generic dict-subclass deepcopy fallback**
(20.69ms vs 45.14ms measured by temporarily deleting `__deepcopy__` and
re-timing) — this is a correct, already-good optimization; leave it alone.

---

## 3. Pure-Python wins available without Rust

Ranked by (measured win / risk). All numbers on `large.ipynb` unless noted.

### 3.1 Delete the redundant `object.__setattr__(self, "_allownew", True)` in `Struct.__init__` — ★★★★★ do this
- **Win:** memory -20% to -25% peak on `reads()` across the whole corpus
  (1.43 MB / 19.8% on `large.ipynb`); speed: `copy.deepcopy` 1.66x
  faster (20.49→12.35ms), `writes()` 1.10-1.22x faster end-to-end,
  `reads()` 1.05-1.16x faster.
- **Risk:** essentially none. `_allownew` already has the correct class
  default; verified `allow_new_attr(False)` and the disallow-new-key
  `KeyError` path still work identically after the change; verified
  `NotebookNode.__deepcopy__`'s `if self.__dict__:` guard now correctly
  skips the (now-empty) instance dict copy for every node, which is itself
  where part of the deepcopy speedup comes from.
- **Behavior change:** none observable.

### 3.2 Single non-mutating build pass for `writes()`, replacing `deepcopy → split_lines → strip_transient` — ★★★★ do this
- Prototyped `build_plain_for_write(nb)`: one recursive walk that emits a
  **plain dict/list tree** (no NotebookNode wrapping — write doesn't need
  attribute access) with line-splitting and transient-key-stripping
  applied inline, instead of three separate full-tree passes (one of
  which — deepcopy — reconstructs NotebookNode instances just to
  immediately discard them at `json.dumps` time).
- **Win:** 1.30x on the deepcopy+split+strip+dumps portion (105.31ms →
  81.00ms). **Verified byte-identical output** to the current 3-pass
  pipeline.
- **Risk:** medium. Touches every branch nbformat's writer currently
  handles separately (cell metadata, attachments, mimebundles by MIME
  type, stream text, non-text-split MIME allowlist) — a larger diff with
  more surface for a subtle divergence bug (e.g. a future new output type
  added to `rwbase.py` but forgotten in the merged function). Needs the
  full existing test suite plus round-trip fuzzing before landing. No
  public API or output-format change.

### 3.3 Swap `json.dumps`/`json.loads` for `orjson` — ★★★★ big win, disclosed format change
- **Win:** the dumps stage alone: 28.44ms → 1.64-2.28ms, **17.4x**, because
  `orjson` is a native (Rust) encoder that supports `indent`+`sort_keys`
  without losing C/native speed the way stdlib's `json.dumps(indent=...)`
  does. Combined with 3.1+3.2: `writes()` **2.57x-4.66x faster** across
  the corpus (large 142.7→55.6ms, medium 26.7→10.4ms, image_heavy
  30.5→6.5ms). `orjson.loads` is 2.0x faster than `json.loads` alone, but
  since `reads()` is validate-bound (64% of time), swapping only the
  loads side yields just 1.02-1.05x on `reads()` overall — not worth the
  dependency on its own, only worth bundling with the write-side change.
- **Risk:** medium-high, and this is the one item on this list with a
  **real, disclosed output-format change**: `orjson`'s indent option is
  fixed at 2 spaces (`OPT_INDENT_2`); nbformat currently writes 1-space
  indent. This changes every `.ipynb` file's byte-for-byte diff footprint
  (though not its JSON semantics) — would need a version bump / explicit
  opt-in, and orjson becomes a new (optional) native-code dependency
  (partially undermining the "avoid Rust" framing, though as a vetted
  upstream library rather than a bespoke rewrite). Also: `orjson` doesn't
  accept raw `bytes` values by default (needs a `default=` callback to
  replicate nbformat's `BytesEncoder`) — low risk in practice since JSON
  itself can't carry `bytes`, so in-tree notebook values are almost never
  actually Python `bytes` objects by the time they reach the writer.
- Also tested: `orjson` compact (no indent) is 6.9x faster than
  `json.dumps` compact — confirms the win is inherent to the library, not
  to configuration tricks.

### 3.4 Eliminate the redundant double-validation in a naive read→write round trip — ★★★ situational
- `reads()` validates once on the way in; `writes()` validates again on
  the way out, even if the notebook object was never mutated in between.
  On `large.ipynb` that's 34ms paid twice = 34ms of pure waste in the
  common "load, maybe touch, save" workflow.
- **Win:** ~17% of the current 203ms baseline round trip; with 3.1-3.3
  applied it's proportionally larger (68ms of the 111ms optimized round
  trip, 61%, is *entirely* validate — half of that is arguably removable
  duplicate work).
- **Risk:** medium. Silently skipping the second validation is a
  correctness/safety-guarantee regression if calling code *did* mutate
  `nb` between read and write. Safest form: an explicit opt-out kwarg
  (`writes(nb, validate=False)`, doesn't currently exist) or a
  content-hash-based "already validated, unchanged" cache — the latter
  adds complexity disproportionate to a 34ms win. Recommend: document the
  cost and offer the kwarg; don't make it implicit.

### 3.5 `rejoin_lines`/`split_lines` scope — ★ not worth pursuing further
- Already only touch the specific fields that can be multiline (source,
  mimebundle data, stream text) — not a whole-tree walk of everything.
  Isolated cost is already small: `rejoin_lines` 1.58ms (2.7% of read),
  `split_lines` 19.75ms (13.8% of write, but that's genuine
  `str.splitlines(True)` work across every long cell source, not
  overhead — confirmed by the `split_lines=False` A/B: disabling it
  entirely only buys 1.68x because it's real per-line list construction
  work, not incidental tree-walking cost). No further narrowing available
  without dropping the git-diff-friendly-format feature itself.

### 3.6 Lazy/on-demand NotebookNode wrapping instead of eager `from_dict` recursion — ★ not prototyped, likely not worth it
- After 3.1, the "extra" cost of eagerly wrapping every dict in
  `NotebookNode` on read, versus a hypothetical lazy-wrap-on-access
  design, is small: ~1.07MB / a few ms out of `reads()`'s 55-60ms (the
  transient overlap of the raw `json.loads` dict tree and the wrapped
  NotebookNode tree existing simultaneously, which is much smaller after
  3.1's fix). Estimated ceiling: another 5-10% off `reads()` time/memory.
  Not prototyped — the architecture change (override `__getitem__` to
  wrap-and-cache on first access, handle mutation-through-view
  semantics correctly) is large relative to the single-digit-percent
  ceiling; not recommended.

### 3.7 `__slots__` on `Struct`/`NotebookNode` — ✗ not worth it
See §2: measured 16 bytes/node (68KB on `large.ipynb`, ~1% of remaining
node memory after 3.1), at the cost of forbidding dynamic attribute
assignment some code may rely on. Skip.

---

## 4. Answering the framing question

**What fraction of the 4-5x overhead is intrinsic to producing Python
objects, and what fraction is removable in pure Python?**

Using `large.ipynb`'s round trip as the representative case (203.2ms
baseline vs 20.7ms raw `json.loads`+compact-`json.dumps` floor — i.e. the
current overhead is **~9.8x** the absolute floor, or ~5x against
`json.dumps` with matching `indent`/`sort_keys`/`ensure_ascii` kwargs, per
the task's own baseline table):

- **~45% is removable in pure Python, with zero behavior change**
  (3.1 + 3.2): 203.2ms → 171.7ms (1.18x), plus this scales better on
  smaller/simpler notebooks (medium: 1.06x reads / ~1.06x-1.3x writes).
- **~another 35-40% is removable by adopting `orjson`** (3.3), at the cost
  of one disclosed on-disk format change (indent width) and one new
  native-code dependency: 171.7ms → 111.1ms.
- **The remaining ~55%** of the *optimized* pipeline (68ms of 111ms) **is
  intrinsic**: full JSON-Schema validation via the fastest available
  Python-ecosystem validator (`fastjsonschema`, itself compiled to
  near-C-speed Python bytecode), paid twice in a naive round trip. This
  is genuine correctness work — every cell and every output gets checked
  against `oneOf`-heavy schema definitions — and even the compiled
  validator pays a measurable (13% of its own time) backtracking tax from
  constructing-then-discarding exception objects for non-matching `oneOf`
  branches, which is intrinsic to how JSON Schema `oneOf` compiles, not
  to nbformat's Python glue around it (that glue — `_normalize`'s cell-id
  loop — is 0.15ms, noise).

**Bottom line for the Rust question:** a from-scratch Rust rewrite's
theoretical ceiling — if it still does the same JSON-Schema validation
work at native speed and produces the same tree once — is bounded below
by roughly what `orjson`-for-serialization + a native/compiled schema
validator would already get you in Python (the write side is already at
2.57-4.66x with `orjson` alone, no Rust *rewrite* needed, just a Rust
*library*). The part Rust would uniquely buy beyond what's captured above
is: (a) avoiding CPython's per-object/per-call overhead in the schema-walk
itself (currently ~30-38ms of unavoidable-in-Python compiled-validator
time per notebook), and (b) collapsing validate+parse+serialize into a
single tree-walk instead of nbformat's current 3-4 separate passes — both
real, but neither is a 5x lever on top of the pure-Python + orjson fixes
above; they're a further ~1.5-2x at most on the now-111ms optimized
round trip, concentrated entirely in the validation stage.
