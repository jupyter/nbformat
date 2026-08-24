# nbformat test taxonomy and format/implementation split

Scope: `/home/user/nbformat/tests/**` (195 tests) + `/home/user/nbformat/nbformat/corpus/tests/` (1 test) = 196
tests collected, matching the stated baseline (192 passed + 3 skipped + 1 corpus = 196).
Every row below was produced by reading the actual test source, not inferred from names.

Categories: **A** format conformance · **B** Python API surface · **C** Python implementation detail · **D** mixed (needs splitting)

## 0. TL;DR counts

Counted at **collected pytest-ID granularity** (so `test_nb4[jsonschema-test4.ipynb]` and
`test_nb4[fastjsonschema-test4.5.ipynb]` are 2 separate counts, matching `pytest --collect-only`) and
cross-checked by summing every per-file subtotal in section 1 down to the last row:

| Category | Count | % |
|---|---|---|
| D — mixed, needs splitting | 70 | 36% |
| B — Python API surface | 58 | 30% |
| A — format conformance | 37 | 19% |
| C — Python implementation detail | 31 | 16% |
| **Total** | **196** | |

**D is the largest bucket, not a small residual** — worth stating up front since it's the least intuitive
result. Two things drive it: (1) `tests/test_validator.py`'s `VALIDATORS` parametrization mechanically
turns every "does this notebook validate" test (A) into 2 collected IDs, one of which is really "do the
two backends agree" (C) — 31 of test_validator.py's 54 IDs land in D for exactly this reason (§1.6); (2)
the `v3`/`v4` `formattest.NBFormatTest` mixin (§0 "machinery" below) contributes a genuinely-A roundtrip
check wrapped in Python-object construction/equality, counted D everywhere it's inherited (15 IDs across
v3/v4). Collapse just those two mechanical sources (refactor plan steps 3 and 6) — 26 backend-duplicated IDs in
`test_validator.py` plus 15 `formattest`-mixin IDs, 41 of the 70 D-classified IDs — and D falls by roughly
that much, with most of the difference flowing to A. The remaining ~29 D cases (§1's other D rows: the
base64/`type(x) is str` splits, `test_sign.py`'s `mark_cells`/`check_cells` group, the cell-id
repair/policy tests, `test_strip_invalid_metadata`, etc.) need the case-by-case split described per-row in
section 1, not a mechanical collapse.

Machinery files that are not tests themselves but shape the classification:
- `tests/base.py` — `TestsBase.fopen`/`_get_files_path`: pure file-loading helper, not a test.
- `tests/v3/formattest.py`, `tests/v4/formattest.py` — **identical** `NBFormatTest` mixin (byte-identical
  files, `diff` shows no difference) contributing 5 tests each to every class that inherits it
  (`test_writes`, `test_reads`, `test_roundtrip`, `test_write_file`, `test_read_file`). This mixin is
  itself a D case (see 2.3).
- `tests/v1/nbexamples.py`, `tests/v2/nbexamples.py`, `tests/v3/nbexamples.py`, `tests/v4/nbexamples.py` —
  Python-constructed fixture notebooks (`nb0`), not tests. These are exactly the fixtures section 3
  proposes converting to data files.

---

## 1. Full classification table

### 1.1 `tests/v1/` (legacy, no JSON schema exists for v1)

| File | Test | Cat | Justification |
|---|---|---|---|
| test_json.py | test_roundtrip | A | write(nb0)+read roundtrip equality — genuine format property (write∘read = id), even though nb0 is Python-built and there is no schema to check against. |
| test_nbbase.py::TestCell | test_empty_code_cell, test_code_cell, test_empty_text_cell, test_text_cell | B | Asserts shape/attributes of `new_code_cell`/`new_text_cell` builder output — this library's Python constructor API, not a spec (no v1 schema exists to conform to). |
| test_nbbase.py::TestNotebook | test_empty_notebook, test_notebooke | B | Same — `new_notebook()` builder shape. |

### 1.2 `tests/v2/` (legacy, no JSON schema exists for v2)

| File | Test | Cat | Justification |
|---|---|---|---|
| test_json.py::TestJSON | test_roundtrip, test_roundtrip_nosplit, test_roundtrip_split | A | JSON write/read roundtrip identity, with/without the line-splitting convention — a real on-disk-format property (git-friendly multiline storage), not schema-checked but genuinely part of "what the v2 JSON must look like". |
| test_nbbase.py::TestCell | test_empty_code_cell, test_code_cell, test_pyerr, test_empty_html_cell, test_html_cell, test_empty_markdown_cell, test_markdown_cell | B | Builder-function shape assertions (`new_code_cell`, `new_output`, `new_text_cell`), no schema backs these. |
| test_nbbase.py::TestWorksheet | test_empty_worksheet, test_worksheet | B | Same, `new_worksheet`. |
| test_nbbase.py::TestNotebook | test_empty_notebook, test_notebook | B | Same, `new_notebook`, asserts `nb.nbformat == 2` as a literal — closest thing to a spec fact but expressed via the builder, not a fixture file. |
| test_nbbase.py::TestMetadata | test_empty_metadata, test_metadata | B | `new_metadata`/`new_author` builder shape. |
| test_nbpy.py::TestPy | test_write | A | Compares `nbpy.writes(nb0)` byte-for-byte against a literal `.py` text fixture (`nb0_py`) — this is conformance to the legacy "notebook-as-Python-script" export format (`# <codecell>` etc.), a real (if now vestigial) textual format that any implementation targeting `.py` export would need to reproduce exactly. |

### 1.3 `tests/v3/` (JSON schema exists: `nbformat.v3.schema.json`)

| File | Test | Cat | Justification |
|---|---|---|---|
| formattest.py (via test_json.py, test_nbpy.py) | test_writes, test_reads, test_roundtrip, test_write_file, test_read_file | D | Mixin exercises `mod.writes/reads/write/read` on a Python-built `nb0`. The *roundtrip/read/write-preserves-content* assertion is A; but the fixture is generated by Python-only `nbexamples.py` calling `new_*` builders, and `assertNBEquals`→`assertEqual` compares `NotebookNode`/dict objects (Python equality semantics) rather than parsed JSON structural equality — so the harness itself is Python-flavored even though what it's checking is format-level. Split: promote `nb0`'s JSON serialization to a `.ipynb` fixture file, then this becomes a pure A "round-trip this document through the JSON reader/writer" check. |
| test_json.py::TestJSON | test_roundtrip_nosplit, test_roundtrip_split | A | Same roundtrip property with explicit `split_lines=True/False` — real on-disk convention. |
| test_json.py::TestJSON | test_strip_transient | D | Format policy: `metadata.orig_nbformat`/`orig_nbformat_minor`/`cell.metadata.trusted` are "transient", i.e. **must not** be persisted to `.ipynb` on write (A — this is a real interop rule, `strip_transient` in `nbformat/v3/rwbase.py:143`). But the test drives it through `nbjson.writes`/`from_dict`, Python objects — split into: (a) data fixture "notebook with transient keys set → written JSON must not contain them" (A), (b) nothing else needed, this one is cleanly convertible. |
| test_json.py::TestJSON | test_to_json | D | Complementary: `to_notebook`/`from_dict` on parsed JSON keeps transient keys — A-level assertion ("reading does not strip transient keys, only writing does") entangled with calling Python's `from_dict`/`nbjson.to_notebook` API (B). |
| test_json.py::TestJSON | test_read_png, test_read_jpeg | D | A-part: base64 PNG/JPEG blob data must survive JSON roundtrip as unicode text. B-part: `self.assertEqual(type(pngdata), str)` asserts a **Python type**, which is meaningless in another language — the conformance-relevant fact is "the value round-trips as valid base64 text", not "is Python `str`". |
| test_misc.py::MiscTests | test_parse_filename | C | Tests `nbformat.v3.parse_filename`, a filename/extension-sniffing helper (`test.ipynb`→format `json`, `test.py`→format `py`) used by the deprecated `nbformat.current` CLI-era API. Pure path-string utility, irrelevant to the notebook format itself. |
| test_nbbase.py::TestCell | test_empty_code_cell, test_code_cell, test_pyerr, test_empty_html_cell, test_html_cell, test_empty_markdown_cell, test_markdown_cell, test_empty_raw_cell, test_raw_cell, test_empty_heading_cell, test_heading_cell | B | Builder shape assertions (`new_code_cell`, `new_output`, `new_text_cell`, `new_heading_cell`). Note nothing here calls `validate()`, so even though a v3 schema exists these tests don't check against it — purely Python constructor shape. |
| test_nbbase.py::TestWorksheet | test_empty_worksheet, test_worksheet | B | `new_worksheet` shape. |
| test_nbbase.py::TestNotebook | test_empty_notebook, test_notebook, test_notebook_name | B | `new_notebook` shape; `nb.nbformat == nbformat` is the closest A-flavored fact but it's asserting the builder default, not validating a document. |
| test_nbbase.py::TestMetadata | test_empty_metadata, test_metadata | B | `new_metadata`/`new_author` shape. |
| test_nbbase.py::TestOutputs | test_binary_png, test_b64b6tes_png, test_binary_jpeg, test_b64b6tes_jpeg | D | A-part: passing raw `bytes` (not base64-encoded text) as `output_png`/`output_jpeg` is a format smell worth flagging — real notebooks must store base64 *text*. C-part: the mechanism asserted is `pytest.warns(UserWarning, match=...)`, a Python `warnings` call inside the `new_output` builder — no schema enforces this, it's this library's defensive constructor behavior. |
| test_nbpy.py::TestPy | test_writes, test_reads, test_roundtrip, test_write_file, test_read_file (via formattest mixin) | A | `nb0_py` is a literal `.py`-format text fixture (`nbexamples.py:125-169`) compared with a `%`-formatted nbformat/nbformat_minor header — this is again conformance to the legacy "notebook-as-python-script" textual format, generated independent of `NotebookNode` internals for the comparison itself (`assertSubset` walks plain dict/list/str). |

### 1.4 `tests/v4/` (JSON schema exists, versioned 4.0–4.5)

| File | Test | Cat | Justification |
|---|---|---|---|
| formattest.py (via test_json.py) | test_writes, test_reads, test_roundtrip, test_write_file, test_read_file | D | Same as 1.3's formattest entry — genuinely A in intent, entangled with Python object construction and equality. |
| test_json.py::TestJSON | test_roundtrip_nosplit, test_roundtrip_split | A | Multiline-blob split/rejoin roundtrip — documented on-disk convention (`nbformat/v4/rwbase.py:69-92`). |
| test_json.py::TestJSON | test_splitlines | A | Verifies exactly *which* mimebundle keys get split into line-arrays (`text/*`, non-JSON) vs left alone (`application/…+json`, `application/json`) — this is a precise, language-agnostic on-disk-format rule (`_is_json_mime`, `nbformat/v4/rwbase.py:8-12`), asserted here against literal JSON (`json.loads(s)`), making it a clean A. |
| test_json.py::TestJSON | test_read_png, test_read_jpeg | D | Same split as v3's equivalent: base64 survives roundtrip (A) entangled with `type(pngdata) == str` (B, Python-type assertion). |
| test_json.py::TestJSON | test_latest_schema_matches | A | Pins `nbformat==4, nbformat_minor==5` as *the* current version — a fact about the format's current released version, language-agnostic. |
| test_json.py::TestJSON | test_base_version_matches_latest | A | Asserts `nbformat.v4.schema.json` (the "current" alias) is byte-identical to `nbformat.v4.5.schema.json` — pure JSON-file consistency check, no Python semantics involved at all. Trivially portable — could run as a `diff`/`jq`-based CI check in any language. |
| test_json.py::TestJSON | test_latest_matches_nbformat | A | Schema's `description` field string must mention the current version number — JSON-file/version-string consistency, language-agnostic. |
| test_nbbase.py | test_empty_notebook, test_empty_markdown_cell, test_markdown_cell, test_empty_raw_cell, test_raw_cell, test_empty_code_cell, test_empty_display_data, test_empty_stream, test_empty_execute_result, test_display_data, test_execute_result, test_error, test_code_cell_with_outputs, test_stream | B | All 14 are shape assertions on `new_*` builder output (`nbformat/v4/nbbase.py`). Unlike v3, these *do* implicitly exercise the schema (`new_code_cell` etc. call `validate()` internally, `nbformat/v4/nbbase.py:129,143,157,170`) — so a failure here could be either a builder bug or a schema regression. Still classified B because the assertions themselves check Python attribute values (`cell.cell_type`, `output.data[key]`), not schema conformance directly. |
| test_convert.py | test_upgrade_notebook, test_downgrade_notebook | A | v3↔v4 whole-notebook conversion is `validate()`-checked both before and after — this is exactly the "v3→v4 conversion produces a valid document" conformance fact, independent of the Python objects used to build the v3 fixture. |
| test_convert.py | test_upgrade_heading | D | A-part: heading-cell → markdown-cell-with-`#`-prefix mapping rule, including the "join multi-line heading source with spaces" rule — real, precise field-mapping spec. C-part: `mock.patch("nbformat.v4.convert.random_cell_id", ...)` and `mock.patch("nbformat.v4.nbbase.random_cell_id", ...)` — mocking a specific Python function by dotted path to make cell-id generation deterministic is pure implementation plumbing; a data-fixture version would just hardcode expected ids or ignore them. |
| test_convert.py | test_downgrade_heading | A | markdown→heading downgrade field-mapping rules (`#`, `#\t`, multiple `#`, single- vs multi-line) — precise, language-agnostic spec facts, no mocking needed here. |
| test_convert.py | test_upgrade_v4_to_4_dot_5 | A | Reads a real fixture file (`tests/test4.ipynb`, `nbformat_minor==0`) and checks `convert.upgrade` produces a validated 4.5 doc with cell ids added — a genuine input-file → expected-output-shape conformance case, already using a file fixture. |
| test_convert.py | test_upgrade_without_nbminor_version | A | `no_min_version.ipynb` → `convert.upgrade` must raise `ValidationError` — format policy ("v4 notebooks lacking `nbformat_minor` cannot be upgraded blindly"), file-fixture-driven already. |
| test_validate.py | test_valid_code_cell | A | `new_code_cell()` output validates as `code_cell` — but really is exercising the schema, wrapped in a builder call. |
| test_validate.py | test_invalid_code_cell, test_invalid_markdown_cell, test_invalid_raw_cell | D | A-part: "source must be a string", "metadata is required", "source is required", "cell_type is required" are real schema-conformance facts about `code_cell`/`markdown_cell`/`raw_cell`. C-part: the invalid instances are produced by mutating a builder-constructed dict (`del cell["metadata"]`) rather than loading a minimal invalid JSON fixture — trivial to convert to data files (12 tiny fixture cells: 3 cell types × 4 mutations). |
| test_validate.py | test_sample_notebook | A | Loads `tests/test4.ipynb` and validates it — already file-fixture-driven, straightforwardly portable. |

### 1.5 `tests/` top level

| File | Test | Cat | Justification |
|---|---|---|---|
| test_api.py | test_canonical_version | C | Asserts `nbformat.__version__` is PEP 440-canonical via `packaging.version.parse` — a Python packaging-ecosystem convention, meaningless for a Rust/JS artifact (crates.io/npm have their own versioning rules). |
| test_api.py::TestAPI | test_read | A | v2 file auto-upgraded to `current_nbformat` on read — cross-version read policy, file-fixture-driven (`test2.ipynb`). |
| test_api.py::TestAPI | test_write_downgrade_2 | A | v3→v2 downgrade-on-write, checked via `json.loads` of the output string — genuinely format-level, and notably already avoids `NotebookNode` on the output side. |
| test_api.py::TestAPI | test_read_write_path, test_read_write_pathlib_object | C | Tests that `read()`/`write()` accept `str` paths and `pathlib.Path` objects, not just file-like objects — this is Python stdlib file-handling API surface (path-like protocol), not a notebook-format fact at all. |
| test_api.py::TestAPI | test_capture_validation_error | B | Tests the `capture_validation_error: dict` out-parameter convention on `read`/`write` — a Python API ergonomics feature (mutate a caller-supplied dict as an error channel) with no format-level meaning. |
| test_convert.py (top) | test_downgrade_3_2, test_upgrade_2_3, test_upgrade_downgrade_4_3_4 | A | `convert()` step-wise version conversion, file-fixture-driven (`test3.ipynb`, `test2.ipynb`, `test4.ipynb`), checked via `get_version`/`validate`/`isvalid`. |
| test_convert.py (top) | test_upgrade_3_4__missing_metadata | A | v3→v4 conversion of a metadata-less document must raise `ValidationError` matching `"could not be converted.+metadata"` — format policy + error-message *content family* (regex is loose enough to be a legitimate conformance-style assertion, not implementation-specific wording). |
| test_convert.py (top) | test_open_current | A | Reads v2, converts to `current_nbformat`, and separately confirms the *original* major version was still obtainable before conversion — format/version-history fact. |
| test_nbformat.py | test_read_invalid_iowrapper, test_read_invalid_filepath, test_read_invalid_pathlikeobj | D | A-part: `{}` is not a valid notebook and `read()` must raise `ValidationError` mentioning `"cells"` — real format fact (empty doc invalid, missing required top-level key). C-part: the three tests differ only in *how the input is supplied to Python's `read()`* (an open file object vs a `str` path vs a `pathlib`-ish path) — pure Python I/O-API surface, three redundant wrappers around one format fact. |
| test_nbformat.py | test_read_invalid_str, test_read_invalid_type | C | `read()` on a nonexistent path raises `OSError`; `read(123)` raises `OSError` (not `TypeError`!) — this documents *this Python function's* argument-handling/error-type quirks, not a notebook-format property. |
| test_reader.py::TestReader | test_read | A | v2/v3 documents each keep their own version through `reader.read()` (no implicit conversion) — real format/versioning contract, file-fixture-driven. |
| test_reader.py::TestReader | test_read_fails_on_missing_worksheets, test_read_fails_on_missing_worksheet_cells | A | v3 documents missing `worksheets`/`cells` raise `ValidationError` mentioning the missing key — schema-required-field conformance, already file-fixture-driven (`test3_no_worksheets.ipynb`, `test3_worksheet_with_no_cells.ipynb`). |

### 1.6 `tests/test_validator.py` (30 distinct test functions, 54 collected IDs via `VALIDATORS`/fixture parametrization)

`VALIDATORS = ["fastjsonschema", "jsonschema"]` (`nbformat/json_compat.py:98-102`) is a **pure Python
implementation axis** — which third-party schema-compiler library is used. Every test parametrized over
`validator_name` is, by construction, a D case: the notebook-level fact being checked is A, but running it
twice to prove two Python libraries agree is C. This sub-section lists each distinct test function once;
the "×N variants" note captures the parametrization.

| Test function | ×variants | Cat | Justification |
|---|---|---|---|
| test_should_warn | ×2 validators | D | A: a 4.5 cell without `id` is still "valid enough" to proceed (soft policy). C/B: asserted via `pytest.warns(MissingIDFieldWarning)`, a specific Python warning class, and the backend-agreement parametrization. |
| test_should_not_mutate | ×2 (skipped: "Does not work in all architectures") | B | Non-mutation-of-input is an implementation contract for `validate()`, not a fact about notebook *documents*. Currently dead (skipped) — flagged as a maintenance smell independent of this taxonomy. |
| test_is_valid_should_not_mutate | ×2 invalidators×2 validators = 4 | B | Same non-mutation contract, for `isvalid()`. Not format-level; any implementation could choose a mutating-then-restoring strategy and still be "format-conformant". |
| test_nb2, test_nb3 | ×2 validators each | D | A: `test2.ipynb`/`test3.ipynb`, once read+auto-upgraded, validate as current — real conformance fact, file-fixture-driven already. C: the ×2 is proving backend agreement. |
| test_nb4 | ×2 nbfile×2 validators = 4 | D | Same pattern for `test4.ipynb`/`test4.5.ipynb`. |
| test_nb4_document_info, test_nb4custom, test_nb4jupyter_metadata, test_nb4jupyter_metadata_timings | ×2 validators each | D | Each is "this specific fixture file (`test4docinfo.ipynb` etc.) is a valid v4 notebook" — clean A once decoupled from the backend loop. |
| test_invalid | ×2 validators | D | A: `invalid.ipynb` fails validation (source missing, bad cell/output type). C: backend-agreement loop. |
| test_validate_empty | ×2 validators | A | `{}` is invalid — minimal, portable conformance fact. |
| test_future | ×2 validators | D | A: a notebook declaring itself newer (`test4plus.ipynb`) fails when validated *against an older* explicit version but passes when validated against its own — real forward-compatibility policy. C: backend loop. |
| test_validation_error | ×2 validators | C | Asserts the exact **jsonschema-library error-message shape** via regex (`"validating .required. in markdown_cell"`, `"On instance\[u?['\"].*cells['\"]\]\[0\]"`) — this is 100% `jsonschema`-package wording (note `validator.py:504` always re-runs through `jsonschema` for "better" messages regardless of which backend was selected), meaningless for any other implementation. |
| test_iter_validation_error | ×2 validators | D | A: `invalid.ipynb` has exactly 3 errors, mapped to refs `{"markdown_cell","heading_cell","bad stream"}` — genuine, valuable "which of N seeded defects does the validator find" conformance data. C/B: `.ref` is an attribute of this library's `NotebookValidationError`/`better_validation_error` machinery (`validator.py:223-261`), not something JSON Schema itself produces. |
| test_iter_validation_empty | ×2 validators | D | A: `{}` yields at least one error via the streaming API too. B: `type(errors[0]) is ValidationError` pins the exact Python exception type (imported from `jsonschema`, not from `nbformat`). |
| test_validation_no_version | ×2 validators | A | A document with no recognizable version key is invalid — real fact, though the fixture is an inline dict rather than a file. |
| test_invalid_validator_raises_value_error, test_invalid_validator_raises_value_error_after_read | not parametrized | C | Setting `NBFORMAT_VALIDATOR=foobar` raises `ValueError` — entirely about this library's env-var-driven backend-selection mechanism (`json_compat.py:118-123`). No other implementation has this concept. |
| test_fallback_validator_with_iter_errors_using_ref | not parametrized | C | Confirms `new_code_cell()`/`new_markdown_cell()`/`new_raw_cell()` don't spuriously warn when `NBFORMAT_VALIDATOR=fastjsonschema` — validator-backend + Python `recwarn` fixture, pure implementation detail. |
| test_non_unique_cell_ids | not parametrized | D | A: duplicate cell `id`s across a notebook make it invalid — a real cross-field uniqueness rule that JSON Schema *cannot* express and that `_normalize` enforces in code (`validator.py:360-380`); this is exactly the kind of rule a reusable conformance fixture needs to capture explicitly since "run it against the schema" alone won't catch it. B: `repair_duplicate_cell_ids=False` kwarg and calling the private `nbformat.validator._validate` are this-library internals. |
| test_repair_non_unique_cell_ids | not parametrized | D | A: same uniqueness rule, "auto-repairable" variant. B: the repair-and-`DuplicateCellId`-warn *policy* is this library's choice (a Rust core could equally choose to hard-error instead of silently regenerating an id) — worth keeping as an explicit, named library behavior rather than baking it into the conformance suite as mandatory. |
| test_no_cell_ids, test_repair_no_cell_ids | not parametrized | D | Same pattern as above, for the "cell has no `id` at all" case (`v4_5_no_cell_id.ipynb`). |
| test_invalid_cell_id | not parametrized | A | `invalid_cell_id.ipynb` fails validation — presumably an id violating the `^[a-zA-Z0-9-_]+$` pattern (`nbformat.v4.5.schema.json:98-103`); pure schema conformance, file-fixture-driven already. |
| test_notebook_invalid_without_min_version | not parametrized | A | `no_min_version.ipynb` fails validation — file-fixture-driven format fact. |
| test_notebook_v3_valid_without_min_version | not parametrized | A | `test3_no_min_version.ipynb` validates — v3 notebooks are not required to carry a minor version; file-fixture-driven. |
| test_notebook_invalid_without_main_version | not parametrized | — | **Dead test**: body is a bare `pass`. Asserts nothing. Flagged for deletion/completion regardless of the taxonomy — not usefully classifiable. |
| test_strip_invalid_metadata | not parametrized | D | A: `v4_5_invalid_metadata.ipynb` is invalid; after `normalize(strip_invalid_metadata=True)` it becomes valid — an excellent input-file→expected-output-file conformance fixture pair (`conformance/normalize/...`). C: the *mechanism* (`_strip_invalida_metadata` walking a `jsonschema`-specific `error_tree`, `validator.py:515-586`) only exists for the `jsonschema` backend and is a clear example of implementation reaching into a third-party library's internals — not portable, and arguably a maintenance risk independent of this task. |
| test_get_validator_caches_per_relax_add_props, test_relax_add_props_does_not_leak_into_strict_validation | ×2 validators each | C | Tests the identity/caching behavior of the private `validators` dict cache and `get_validator()` — pure implementation performance/correctness detail (avoiding recompiling schemas), no notebook-format content involved. |

### 1.7 `tests/test_sign.py` (21 tests: trust/signing subsystem)

Signing is a **companion Python tool**, not part of the `.ipynb` format: the schema places no constraint
on `metadata.signature` (a free-form string, stripped as "transient" before writing, see 1.3's
`test_strip_transient`), and the actual trust database lives *outside* the notebook file (a local SQLite
file under the Jupyter data dir, `nbformat/sign.py:17-34`). Every test in this file is classified **C**
unless noted, because the entire mechanism — HMAC digest algorithm choice, SQLite storage/culling, the
`traitlets`-`Config` integration, and the `python -m nbformat.sign` CLI — is Python/Jupyter-ecosystem
tooling with no cross-language notebook-format meaning.

| Test | Cat | Justification |
|---|---|---|
| test_invalid_db_file | C | SQLite file-corruption recovery (`.bak` backup) — SQLite implementation detail. |
| test_not_using_context_manager_warns (skipped) | C | Python context-manager usage-pattern deprecation warning. |
| test_using_context_manager_does_not_warn | C | Same. |
| test_algorithms | C | Iterates `hashlib.algorithms_guaranteed` minus `shake_*` — Python `hashlib` API surface. |
| test_sign_same, test_change_secret | C | HMAC digest determinism/secret-sensitivity — generic crypto property, but exercised entirely through this library's `NotebookNotary.compute_signature`, an implementation detail (the format doesn't mandate HMAC-anything). |
| test_sign, test_unsign | B/C | Public `NotebookNotary.sign`/`check_signature`/`unsign` API surface (B) backed by SQLite (C). Classified C overall since the trust *concept* isn't format-normative. |
| test_cull_db | C | SQLite LRU-culling policy (`cache_size`, 75%-retention math) — pure storage-engine implementation detail. |
| test_check_signature | C | Algorithm-mismatch detection logic within the signature-store record format — internal to this tool. |
| test_mark_cells_untrusted, test_mark_cells_trusted, test_check_cells, test_trust_no_output | D | A sliver: the *convention* that `cell.metadata.trusted` only appears on `code` cells is a real, if soft, notebook-metadata convention (`nbformat/sign.py`'s `mark_cells`). C: the actual trust bookkeeping (signature DB lookup) is pure tooling. |
| test_mark_cells_untrusted_v3, test_mark_cells_trusted_v3, test_check_cells_v3 | D | Same, plus explicitly exercising the v3 `worksheets[0].cells` shape — v3-structure-awareness is B/A-ish but wrapped entirely in the trust tool. |
| test_sign_stdin | C | Spawns `python -m nbformat.sign` as a subprocess and greps its stdout log text (`"Signing notebook: <stdin>"`) — about as Python-implementation-specific as a test can get (subprocess + CLI log wording). |
| test_config_store | C | `traitlets.config.Config` dependency-injection pattern (`NotebookNotary.store_factory`) — Python config-framework API. |
| SignatureStoreTests::test_basics | C | `MemorySignatureStore` CRUD — in-memory Python dict-backed store, pure implementation. |
| SQLiteSignatureStoreTests::test_basics (inherited) | C | Same test body against the SQLite-backed store. |

### 1.8 `nbformat/corpus/tests/test_words.py`

| Test | Cat | Justification |
|---|---|---|
| test_generate_corpus_id | C | Tests `uuid.uuid4().hex[:8]` output length/uniqueness — an internal ID-generation helper. The *format* only requires cell ids to match `^[a-zA-Z0-9-_]+$`, length 1–64, and be unique within a document (`nbformat.v4.5.schema.json:98-103`, enforced in `validator.py`); the specific "8 lowercase-hex characters via uuid4" scheme is this library's implementation choice, not a format requirement — any implementation is free to generate ids differently. |

---

## 2. Notes on borderline calls

1. **Every `VALIDATORS`-parametrized test is D by construction.** The 16 test functions parametrized only
   over `validator_name` (32 collected IDs) all reduce to "does a real notebook validate correctly" (A)
   run twice to prove Python's two JSON-Schema backends agree (C). Splitting them is mechanical: the A half
   becomes one fixture-driven case per notebook file; the "two backends agree" half becomes a *single*,
   explicitly-labelled `test_validator_backends_agree` (or similar) that stays in the Python suite forever,
   parametrized over the *existing* conformance fixtures rather than duplicating assertions inline.
2. **Cell-id uniqueness (`test_non_unique_cell_ids`, `test_no_cell_ids`, and their repair variants) is the
   most important A-fact hiding inside implementation-flavored tests.** JSON Schema cannot express
   "unique across siblings", so a Rust/JS conformance suite would silently miss this rule if it only ran
   the `.schema.json` files through a generic validator — these need to become explicit fixture+expected-verdict
   pairs, independent of Python's specific repair/warn behavior.
3. **`strip_transient`, `split_lines`/`rejoin_lines`, and the mime-bundle split rule (`_is_json_mime`) are
   real on-disk-format conventions that happen to live in "implementation" files (`rwbase.py`) and are
   tested incidentally.** They deserve first-class A fixtures (before/after JSON pairs) rather than being
   implied by roundtrip tests.
4. **Python-*type* assertions (`type(x) is str`) inside otherwise-A tests** (`test_read_png`/`test_read_jpeg`
   in both v3 and v4) are the cleanest, most mechanical D→split example: replace with "value parses as
   base64" (any language) instead of "value is a Python `str`".
5. **`sign.py` is classified almost entirely C**, which is a judgment call worth stating explicitly: one
   could argue the Jupyter *trust model* (unsigned/untrusted notebooks don't auto-run outputs) is a
   cross-implementation *concept*. But nbformat's `sign.py` doesn't encode that concept in the file format —
   it encodes one specific Python tool's local trust database. A Rust core would have no reason to replicate
   `NotebookNotary`; it would just need to preserve/strip the `metadata.signature` and `cell.metadata.trusted`
   keys correctly (which *is* tested, as part of `strip_transient`, and *is* classified A there).
6. **v1/v2 have no JSON schema at all.** Every "format conformance" test for v1/v2 is therefore
   necessarily either a roundtrip test or a literal-text comparison (`nbpy` `.py` export) — there is no
   schema-validation angle to separate out. This limits how much v1/v2 testing can move into a
   schema-driven conformance suite; it can still move as roundtrip/golden-file fixtures, just without a
   validator to run them through.

---

## 3. Conformance-fixture inventory and proposed layout

### 3.1 What already exists as data files

`tests/*.ipynb` (18 files) are **already** language-agnostic fixtures, currently scattered flat in
`tests/` and consumed only via `TestsBase.fopen`/hardcoded relative paths:

```
tests/invalid.ipynb                       tests/test3_no_metadata.ipynb
tests/invalid_cell_id.ipynb               tests/test3_no_min_version.ipynb
tests/invalid_unique_cell_id.ipynb        tests/test3_no_worksheets.ipynb
tests/many_tracebacks.ipynb (unused!)     tests/test3_worksheet_with_no_cells.ipynb
tests/no_min_version.ipynb                tests/test4.5.ipynb
tests/test2.ipynb                         tests/test4.ipynb
tests/test3.ipynb                         tests/test4custom.ipynb
                                           tests/test4docinfo.ipynb
                                           tests/test4jupyter_metadata.ipynb
                                           tests/test4jupyter_metadata_timings.ipynb
                                           tests/test4plus.ipynb
                                           tests/v4_5_invalid_metadata.ipynb
                                           tests/v4_5_no_cell_id.ipynb
```
(`tests/many_tracebacks.ipynb` was not referenced by any test file grepped — worth confirming with the
maintainer before moving/pruning it; possibly dead fixture, or used only by a downstream consumer.)
There is **no** `nbformat/v*/tests/` or `nbformat/tests/` directory inside the package — all fixture data
lives under the top-level `tests/`.

### 3.2 Python-constructed fixtures that could become JSON data files

- `tests/v3/nbexamples.py:nb0`, `tests/v4/nbexamples.py:nb0` — built via `new_*` builders, then serialized
  with `mod.writes(nb0)` inside the tests that use them. **Straightforward to convert**: run
  `nbjson.writes(nb0)` once, save the output as `conformance/v{3,4}/valid/kitchen_sink.ipynb`, and rewrite
  the dependent tests to `read()` that file instead of importing `nb0`. This removes the Python-object
  detour entirely for the A-classified parts of `test_json.py`/`formattest.py`.
- `tests/v1/nbexamples.py:nb0`, `tests/v2/nbexamples.py:nb0` — same idea, though since there's no schema
  for v1/v2 these become "golden roundtrip fixtures" rather than "schema-valid fixtures". Still worth
  moving for the roundtrip and `nbpy` golden-text tests.
- The four `test_invalid_*_cell` mutations in `test_validate.py` (`del cell["metadata"]`, etc.) — trivial
  to hand-author as 12 minimal invalid-cell JSON snippets (3 cell types × 4 defects) rather than mutating
  builder output at test time.
- `test_upgrade_heading`/`test_downgrade_heading` cases in `v4/test_convert.py` — the cell-level
  before/after pairs (heading→markdown, markdown→heading) are small enough to become
  `conformance/convert/v3-to-v4/heading_cell/{input,expected}.json` fixture pairs; this also removes the
  need for `mock.patch` on `random_cell_id` (an expected-output fixture can simply omit/normalize the `id`
  field, or the comparison can ignore it) — see step-plan item 4.

### 3.3 What genuinely cannot become plain data fixtures

- **Backend-agreement tests** (`VALIDATORS` parametrization) — inherently about *this Python library's*
  choice of two JSON-Schema engines; there is nothing to "convert to data", they stay as Python tests
  forever (ideally consuming the same conformance fixtures rather than inline dicts).
- **Non-mutation-of-input contracts** (`test_should_not_mutate`, `test_is_valid_should_not_mutate`) — an
  API-contract property (does calling `validate()` leave the argument unchanged?), not a property of a
  notebook document; can't be expressed as "here is a file, here is the expected verdict".
- **Everything in `test_sign.py`** — no file-based fixture makes sense; the subject under test is a local
  trust database and a CLI subprocess, not a document.
- **Env-var/type/path-object handling** (`NBFORMAT_VALIDATOR`, `pathlib.Path` vs `str` vs file-object
  inputs to `read()`/`write()`) — these are about *how Python callers invoke the library*, not about
  documents.
- **`test_canonical_version`, cache-identity tests, `test_read_invalid_type`** — no notebook content
  involved at all.

### 3.4 Proposed `conformance/` layout

```
conformance/
  README.md                      # what this tree is, how to consume it from any language
  v3/
    valid/
      kitchen_sink.ipynb          # from tests/v3/nbexamples.py:nb0
      no_min_version.ipynb        # <- tests/test3_no_min_version.ipynb (moved)
    invalid/
      missing_worksheets.ipynb    # <- tests/test3_no_worksheets.ipynb
        expected.json             # {"error_contains": "worksheets", "schema_ref": null}
      worksheet_with_no_cells.ipynb
        expected.json
      missing_metadata.ipynb      # <- tests/test3_no_metadata.ipynb
        expected.json             # {"error_contains": "could not be converted...metadata", "context": "convert-to-v4"}
  v4/
    valid/
      kitchen_sink.ipynb          # from tests/v4/nbexamples.py:nb0
      test4.5.ipynb               # <- tests/test4.5.ipynb (moved)
      document_info.ipynb         # <- tests/test4docinfo.ipynb
      custom_mimetype.ipynb       # <- tests/test4custom.ipynb
      jupyter_metadata.ipynb      # <- tests/test4jupyter_metadata.ipynb
      jupyter_metadata_timings.ipynb
      future_minor.ipynb          # <- tests/test4plus.ipynb
        expected.json             # {"valid_as": [4, null], "invalid_as": [4, 3]}  <- version-pinned verdicts
    invalid/
      empty_document.json         # {} -- not even an .ipynb, just the smallest possible bad input
        expected.json             # {"error_contains": "cells"}
      general_defects.ipynb       # <- tests/invalid.ipynb
        expected.json             # {"error_count": 3, "refs": ["markdown_cell", "heading_cell", "bad stream"]}
      duplicate_cell_id.ipynb     # <- tests/invalid_unique_cell_id.ipynb
        expected.json             # {"error_contains": "Non-unique cell id"}
      missing_cell_id.ipynb       # <- tests/v4_5_no_cell_id.ipynb
        expected.json
      malformed_cell_id.ipynb     # <- tests/invalid_cell_id.ipynb
        expected.json
      no_min_version.ipynb        # <- tests/no_min_version.ipynb
        expected.json
      cells/
        code_cell_source_wrong_type.json     # cell-level ref-validated fragments
        code_cell_missing_metadata.json
        code_cell_missing_source.json
        code_cell_missing_cell_type.json
        markdown_cell_*.json  (x4)
        raw_cell_*.json        (x4)
    normalize/
      invalid_metadata/
        input.ipynb              # <- tests/v4_5_invalid_metadata.ipynb
        expected_output.ipynb    # result of normalize(strip_invalid_metadata=True)
        expected.json            # {"changes": N}
  convert/
    v2-to-v3/
      input.ipynb                # <- tests/test2.ipynb
      expected_version.json      # {"major": 3}
    v3-to-v4/
      input.ipynb                # <- tests/test3.ipynb
      expected.ipynb
      heading_cell/
        input.json               # single-cell fragment: v3 heading, level 1
        expected.json            # v4 markdown cell, source "# foo"
      heading_cell_multiline/
        input.json
        expected.json
    v4-to-v3/
      input.ipynb
      expected.ipynb
    v4-minor-upgrade/
      4.0-to-4.5/
        input.ipynb               # <- tests/test4.ipynb (nbformat_minor: 0)
        expected_minor.json       # {"nbformat_minor": 5, "cells_gain_id": true}
      missing-minor/
        input.ipynb                # <- tests/no_min_version.ipynb
        expected.json              # {"raises": "ValidationError"}
  roundtrip/
    v3/kitchen_sink.ipynb          # write(read(x)) == x, and split/nosplit variants
    v4/kitchen_sink.ipynb
    v4/mime_split_rules.ipynb      # exercises _is_json_mime / _split_mimebundle precisely
```

Each `expected.json` is a **small, hand-readable verdict file**, not a serialized Python exception — e.g.
`{"valid": false, "error_contains": "...", "error_count": 3}` rather than pickling a `ValidationError`.
This is the piece that has to be *designed*, not mechanically extracted — today's expected-error assertions
are regexes against Python/jsonschema-flavored strings (see 1.6, `test_validation_error`) and would need to
be rewritten as language-neutral verdicts (error *count*, error *ref*/*location*, not exact wording) for
the fixture format to be honestly reusable by a non-Python validator.

---

## 4. Source-module map

| Module | Category | Why |
|---|---|---|
| `nbformat/v3/nbformat.v3.schema.json`, `nbformat/v4/nbformat.v4*.schema.json` | **A** | Already 100% language-agnostic. The literal reusable artifact — zero rewrite needed for a conformance suite or a Rust core. |
| `nbformat/v1/convert.py`, `v2/convert.py`, `v3/convert.py`, `v4/convert.py` | **A** (core logic) + thin **B** wrapper | The actual field-mapping spec between format versions (e.g. `pyout`→`execute_result`, `stream`→`output.name`, heading-cell→markdown mapping, `nbformat/v4/convert.py:102-296`). This *is* the versioning spec of the format and is the best single source for `conformance/convert/` fixtures. The `_warn_if_invalid` helper (uses `traitlets.log.get_logger()`) is the B/C sliver. |
| `nbformat/v1/rwbase.py`, `v2/rwbase.py`, `v3/rwbase.py`, `nbformat/v4/rwbase.py` | **A** (functions) + **B** (classes) | `split_lines`/`rejoin_lines`/`base64_encode`/`base64_decode`/`strip_transient`/`_is_json_mime` encode real, documented on-disk conventions (git-friendly multiline storage, "transient" metadata keys) that any implementation targeting byte-compatible `.ipynb` files must replicate. The `NotebookReader`/`NotebookWriter` base classes (`read`/`write`/`reads`/`writes` template methods) are Python OOP scaffolding (B). |
| `nbformat/v1/nbjson.py`, `v2/nbjson.py`, `v3/nbjson.py`, `nbformat/v4/nbjson.py` | **A** (algorithm) + **B** (class shape) | "Parse this JSON text via `json.loads`, call `rejoin_lines`, return"; "call `split_lines`+`strip_transient`, `json.dumps`" — the *algorithm* is A, the `JSONReader(NotebookReader)`/`JSONWriter(NotebookWriter)` class wrapping is B glue for Python's `read(fp)` vs `reads(s)` ergonomics. |
| `nbformat/reader.py` | **A** core + **B** glue | `get_version()` (dict lookup with defaults) is pure A. `reads()`/`read()` dispatch by major version via the `versions` dict (a Python module registry — B) but the *policy* "look at `nbformat`/`nbformat_minor` keys, dispatch by major version, missing-key → error" is A. `NotJSONError` is a Python exception type (B). |
| `nbformat/validator.py` | **A** policy, **B/C** mechanism | `_normalize`'s cell-id-uniqueness/id-presence policy (`:341-380`) and the whole "what does it mean for a notebook to be valid at version (M, m)" orchestration is A — this is where format rules that JSON Schema can't express (uniqueness) live in *code* rather than in the schema files, making this the single most important module to mine for A-fixtures. `get_validator`/`_get_schema_json` (schema file resolution + backend caching) and `NotebookValidationError`/`better_validation_error` (jsonschema-flavored message formatting) are B/C — Python-package-specific. |
| `nbformat/json_compat.py` | **C** | 100% Python implementation detail: the `jsonschema`/`fastjsonschema` backend adapter classes and the `NBFORMAT_VALIDATOR` env var. This is *the* natural "swap the core validator" seam (see §5) — in a Rust world this file disappears entirely, replaced by a native JSON-Schema implementation (or a hand-written validator using the rules mined out of `validator.py`'s `_normalize`). |
| `nbformat/converter.py` | **A** policy + **B** glue | `convert()`'s step-wise "walk the `versions` dict one major version at a time" policy is A; the `versions` dict itself and `ValueError`/`ValidationError` exception types are B. |
| `nbformat/notebooknode.py`, `nbformat/_struct.py` | **B** | `NotebookNode`/`Struct`: dict-with-attribute-access, custom `__deepcopy__`, `_allownew` protection. Pure Python ergonomics layer for a nicer `nb.cells[0].source` API; a Rust core has no equivalent concept (it would return native structs, and pyo3 bindings would need their own wrapper, which is binding-layer work, not "format" work). |
| `nbformat/corpus/words.py` | **C** (with an A-adjacent constraint) | `generate_corpus_id` (`uuid4().hex[:8]`) is this library's specific choice for satisfying the schema's `cell_id` pattern (`^[a-zA-Z0-9-_]+$`, 1–64 chars) — the *pattern* is A (schema-encoded), the *generator* is not mandated and is C. |
| `nbformat/sentinel.py` | **C** | `Sentinel`/`NO_CONVERT` — a Python "distinguishable None" idiom for the `version=` default-vs-explicit-None-vs-NO_CONVERT tri-state in `writes()`/`read()`. Pure API-ergonomics plumbing. |
| `nbformat/warnings.py` | **B** | `MissingIDFieldWarning`/`DuplicateCellId` — Python `warnings`-module subclasses. The *policy* they signal (soft-deprecation period before a rule becomes a hard error) is worth documenting as format-evolution metadata, but the delivery mechanism is Python-specific. |
| `nbformat/sign.py` | **C** | Trust/signing tool: HMAC signatures in an external SQLite database, `traitlets`-based `NotebookNotary`/CLI. Not format-normative (see §2.5); would not need to exist in a Rust core beyond correctly preserving/stripping the `metadata.signature`/`cell.metadata.trusted` keys, which is `rwbase.strip_transient`'s job (A), not `sign.py`'s. |
| `nbformat/__init__.py` | **B** (Python public API) wrapping **A** (policy) | `read`/`reads`/`write`/`writes` — the *policy* "always validate after read, log+optionally capture the error rather than raising" is arguably A-ish (a reasonable contract any binding should offer), but it's expressed entirely as Python function signatures/kwargs (`capture_validation_error: dict`, `NO_CONVERT` sentinel) — this file **is** the Python API surface, by definition B. |
| `nbformat/current.py` | **C**, untested | Deprecated pre-3.0 shim aliasing `nbformat.v3`. No dedicated test file exists (`test_current.py` absent) — dead weight, not exercised by the suite at all. |
| `nbformat/_imports.py` | **C** | `import_item`: dotted-string → object import helper (vendored from `ipython_genutils`). Trivial Python reflection. |
| `nbformat/_version.py` | **C** | `__version__`/`version_info` — packaging metadata. |

### Existing package-internal tests

`nbformat/corpus/tests/test_words.py` is the **only** test living inside the `nbformat` package itself
(as opposed to the top-level `tests/`); everything else, including validator/reader/converter/sign tests,
lives in `tests/`. There is no `nbformat/v*/tests/` directory — versioned-module tests are entirely
external, in `tests/v*/`.

---

## 5. The seam

**The narrowest interface across which a non-Python core could be swapped in is:**

```
notebook JSON text  →  [ CORE: parse version, normalize, validate, convert ]  →  notebook JSON text
                          reads as: bytes/str in, (bool valid, [errors], bytes/str out) out
```

Concretely, the seam sits **between `nbformat/json_compat.py` + `nbformat/notebooknode.py` on the Python
side, and `nbformat/validator.py`'s policy logic + the `.schema.json` files + `v*/convert.py` + `v*/rwbase.py`
on the core side.** A Rust core would own:

- schema loading/compilation and validation (replacing `json_compat.py` + the `get_validator`/`_get_schema_json`
  half of `validator.py`),
- the cell-id uniqueness/presence policy currently living in `_normalize` (`validator.py:319-386`),
- version detection (`reader.get_version`),
- the split/rejoin/base64/strip-transient on-disk conventions (`rwbase.py`),
- the inter-version field-mapping (`v*/convert.py`),

and would need to expose, at minimum, four operations to Python via pyo3: `parse(bytes) -> dict`,
`validate(dict, version) -> ValidationResult`, `convert(dict, to_version) -> dict`,
`serialize(dict) -> bytes`. Everything on the Python side of that line —
`NotebookNode`/`Struct` attribute-access sugar, the `read`/`write`/`reads`/`writes` public function
signatures and their `capture_validation_error`/`NO_CONVERT` conventions, `sign.py`'s trust tooling,
`corpus/words.py`'s id-generation choice, and all of `notebooknode.py`/`_struct.py`/`sentinel.py` — stays
Python-only glue and binding ergonomics, regardless of what implements the core. This is exactly the
Python-API-surface/implementation-detail (B/C) boundary the test taxonomy above independently arrives at:
**modules classified A above are the seam's core-side inventory; modules classified B are what the pyo3
binding layer has to reproduce; modules classified C either disappear (`json_compat.py`) or stay pure
Python tooling untouched by the seam (`sign.py`, `corpus/words.py`, `sentinel.py`).**

Two wrinkles worth flagging explicitly:
- **Error reporting is currently jsonschema-shaped** (`NotebookValidationError.__str__`, the `.ref` attribute,
  `better_validation_error`'s oneOf-drilldown). A Rust core needs its own error-reporting design — the
  existing behavior is *useful* (structured refs, truncated tracebacks) but not portable as-is; it's the
  biggest genuine design task hiding in "just call the schema validator instead", not a mechanical port.
- **`_strip_invalida_metadata` walks jsonschema's `ErrorTree`** (`validator.py:539-586`), a `jsonschema`-package
  data structure — `normalize(strip_invalid_metadata=True)` cannot be ported to a different validator engine
  without redesigning how "which metadata keys caused the failure" is discovered.

---

## 6. Incremental refactor plan

Every step keeps `pytest tests nbformat/corpus/tests` green (192 passed, 3 skipped) at that step's end
unless explicitly noted as the point where a count intentionally changes (e.g. deleting a truly dead test).
None of these steps require touching pyo3/Rust — they stand alone, per the maintainer's framing.

| # | Step | Risk | Public API change? |
|---|---|---|---|
| 1 | **Move the 18 existing `.ipynb` fixtures under `tests/` into `tests/conformance/<version>/{valid,invalid}/...` per §3.4, updating `TestsBase.fopen`/hardcoded paths to the new locations. No fixture content changes, no test logic changes — pure file move + path-string edits.** | Very low — purely mechanical, caught immediately by the existing suite if a path is wrong. | No. |
| 2 | **Add `expected.json` verdict files next to each moved `invalid/` fixture** (error count, `ref`s, contains-substring — data only, not code), without yet changing any test to *read* them. This is prep: writing down, as data, what today's inline Python assertions already encode (e.g. `test_iter_validation_error`'s `{"markdown_cell","heading_cell","bad stream"}`). | Low — additive, no existing test touched. | No. |
| 3 | **Serialize `tests/v3/nbexamples.py:nb0` and `tests/v4/nbexamples.py:nb0` to `conformance/v{3,4}/valid/kitchen_sink.ipynb` once (a one-off script, not part of the test run), then repoint the *A-classified* tests that currently build `nb0` in Python (`test_roundtrip`, `test_roundtrip_nosplit/split`, `test_read_png/jpeg`, the `formattest` mixin's `test_writes/reads/roundtrip`) to `read()` the file instead of importing `nb0`.** Keep `nbexamples.py` around (still used by `test_convert.py`, `test_nbbase.py`, `test_nbpy.py`, and as the generator of the fixture itself) — do not delete it in this step. | Low-medium — mechanical, but touches real test bodies rather than just data location; run the full suite after each file. | No. |
| 4 | **Split each identified D test into an A half and a B/C half**, per §1's per-test notes — mechanically apply the `test_read_png`/`test_read_jpeg` "assert base64-parses, drop the `type(x) is str` line into a separately-named Python-only test" pattern first (lowest-risk D case), then `test_strip_transient`/`test_to_json` (already close to pure-A), then the `test_validate.py::test_invalid_*_cell` builder-mutation→fixture conversion (§3.2), then the `test_upgrade_heading`/`downgrade_heading` cell-level fixture pairs (removes the `mock.patch` dependency entirely). Each sub-step is independently mergeable; do the easiest 5–6 first, re-assess. | Medium — this is where test *behavior* intent has to be preserved exactly; requires care that the split doesn't silently drop coverage (e.g. the base64-validity check must survive, not just the type check). | No. |
| 5 | **Physically reorganize the test tree**: create `tests/conformance/` (format-only: schema validation, convert field-mapping, roundtrip/split/rejoin, cell-id rules) vs `tests/api/` (Python surface: builders' shape, `NotebookNode`, `read`/`write` kwargs, path-object handling, sign.py, validator-backend/env-var mechanics). Move already-split A-only test functions into `conformance/`; leave B/C/D-residue in `api/`. This is the step where directory structure finally reflects the taxonomy — do it only after steps 1–4 have shrunk the D bucket, so the move itself is close to mechanical (file relocation + import fixups) rather than requiring new splitting judgment calls mid-move. | Medium — large diff (mostly `git mv` + import path edits), but low logic risk if steps 1–4 are done first; test discovery/CI config (`pyproject.toml`/`pytest.ini` test paths, coverage config) needs updating in the same PR. | No (unless CI/coverage tooling hardcodes `tests/` path assumptions — check `pyproject.toml`'s `[tool.pytest.ini_options]` / coverage `source`/`omit` before merging). |
| 6 | **Collapse the `VALIDATORS`-parametrization redundancy**: for each of the 16 test functions that are purely "validate this fixture, twice, once per backend" (§1.6, D rows with "×2 validators" and no other axis), keep exactly one backend-agnostic conformance test per fixture (now trivially expressible as "for each `.ipynb` in `conformance/v4/valid/`, `validate()` succeeds" — a single parametrized-over-*fixtures* test, not over *backends*) and add **one** new explicit `test_validator_backends_agree(fixture)` in `tests/api/` that loops the *same* fixture set across both backends. Net effect: fewer total test IDs, same coverage, and backend-agreement becomes an explicitly-named property instead of an implicit side-effect of parametrization. | Medium-high — this changes the *shape* of test IDs (CI history, `-k` filters, flaky-test tracking that references old test names all break), and it's easy to accidentally weaken coverage by conflating "backend produces *a* valid/invalid verdict" fixtures with "backend produces the exact *right* error message" fixtures (only the latter, `test_validation_error`, is legitimately jsonschema-only and must stay put, not get folded in). | No public API change, but real risk to CI tooling that references specific test node IDs. |
| 7 | **(Most invasive, do last, and only if the Rust question is still live) Extract `validator.py`'s `_normalize` policy (cell-id presence/uniqueness) and the schema-loading logic into a small internal module with an explicit, minimal function-call interface** (`normalize_ids(nbdict, version) -> (changes, nbdict)`, `load_schema(version, minor) -> dict`) **that has zero dependency on `jsonschema`/`fastjsonschema` types** — today `NotebookValidationError` wraps a `jsonschema.exceptions.ValidationError` and callers pattern-match on it (`from jsonschema import ValidationError` in `tests/test_validator.py:13`), so this step also means designing nbformat's *own* validation-result type (not a jsonschema-shaped one) that `json_compat.py`'s backends adapt into. This is the actual seam-hardening step from §5, and it is the only step here that changes public API (`ValidationError` currently *is* `jsonschema.exceptions.ValidationError` re-exported, `nbformat/json_compat.py:16`) — anything catching `except jsonschema.ValidationError` downstream (e.g. `nbclient`, `nbconvert`) would need `except nbformat.ValidationError` instead, which is probably already true for well-behaved consumers but is worth an explicit deprecation cycle. | High. | **Yes** — `nbformat.ValidationError` would stop being literally `jsonschema.exceptions.ValidationError`; needs a deprecation/compat shim and a major-version bump. |

---

## 7. What the split honestly costs (not a sales pitch)

- **Shared fixtures get harder to keep in sync.** Today `nbexamples.py:nb0` is *both* the object every
  `test_nbbase.py` shape-test exercises *and* (via `mod.writes`) the source of every roundtrip test's input.
  Splitting means two artifacts (the Python builder-fixture *and* the serialized `.ipynb`) that can drift —
  if someone adds a field to `new_code_cell()`, the `.ipynb` fixture needs a manual regeneration step that
  today happens automatically at test-run time. This needs either a `make regenerate-fixtures` script
  wired into CI drift-detection, or acceptance that the two go stale relative to each other silently.
- **Two `read`/`write`-path fixtures for the same conceptual document** (Python-object nb0 for B-tests,
  `.ipynb` file for A-tests) means twice the review surface for anyone updating what "a representative
  notebook" looks like, and a real chance the two fixtures quietly diverge in content over years.
- **Test discovery and `-k`/node-ID-based tooling breaks.** Anything referencing test IDs by path
  (flaky-test dashboards, `pytest --lf`, CI annotations linking to `tests/v4/test_validate.py::test_...`)
  goes stale the moment files move (step 5) or IDs get restructured (step 6). This is real toil, not just
  risk — every historical CI run's failure links become dead links.
- **Coverage measurement gets murkier, not clearer, in the short term.** `validator.py`'s `_normalize` and
  `_strip_invalida_metadata` are exercised by tests that, post-split, live in *both* buckets (an A fixture
  drives the "is it valid" branch, a B/C test drives the "does it warn/cache correctly" branch) — coverage
  tools attributing lines to "the conformance suite" vs "the implementation suite" needs either combined
  coverage runs (defeating some of the point of separating them) or accepting two coverage reports that
  each look incomplete on their own.
- **Contributor familiarity cost.** Every existing nbformat contributor's mental model is "tests mirror
  `nbformat/v*/`" (confirmed true today — `tests/v1..v4` mirror `nbformat/v1..v4` exactly). Introducing a
  `tests/conformance/` vs `tests/api/` split that cuts *across* that existing per-version mirroring is a
  second organizing axis contributors have to learn simultaneously with the first; expect PRs that add
  tests in the "wrong" bucket for a while, and a need for a CONTRIBUTING note (or a pre-commit check) to
  keep the split intact.
- **The conformance suite's value is capped by what's mineable from *code*, not just schema.** §2's point
  2 and §5's seam discussion both land on the same uncomfortable fact: some of the most important format
  rules (cell-id uniqueness, the "future minor version" relaxation policy, transient-key stripping) live in
  Python control flow today, not in the `.schema.json` files. Writing them down as fixture+expected-verdict
  pairs is necessary *and* is genuinely new authoring work (§3.4's last paragraph) — it is not extractable
  by mechanical refactoring alone, unlike most of steps 1–5.
- **Step 7 (seam-hardening) has a real deprecation cost** for any downstream consumer that catches
  `jsonschema.exceptions.ValidationError` directly rather than `nbformat.ValidationError` — see the table
  entry. This is the one step in this plan that isn't "free" even if the Rust rewrite never happens; it's
  worth doing only if a maintainer actually wants a jsonschema-independent error type for its own sake.
