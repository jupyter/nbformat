"""Correctness gates for the rust prototype vs nbformat."""
import glob, json, os, sys, traceback

import nbf_rust
import nbformat
from nbformat.notebooknode import NotebookNode

CORPUS = "/tmp/claude-0/-home-user-nbformat/4daa7540-3a45-57cd-84ee-987a6735721f/scratchpad/corpus"
TESTS = "/home/user/nbformat/tests"

files = sorted(glob.glob(os.path.join(CORPUS, "*.ipynb"))) + sorted(
    glob.glob(os.path.join(TESTS, "*.ipynb"))
)


def normalize(x):
    """Recursively normalize to plain dict/list for structural comparison."""
    if isinstance(x, dict):
        return {k: normalize(v) for k, v in x.items()}
    if isinstance(x, list):
        return [normalize(v) for v in x]
    return x


def check_isinstance(x):
    if isinstance(x, dict):
        if not isinstance(x, NotebookNode):
            return False
        return all(check_isinstance(v) for v in x.values())
    if isinstance(x, list):
        return all(check_isinstance(v) for v in x)
    return True


n_reads_ok = n_reads_fail = 0
n_writes_ok = n_writes_fail = 0
n_validate_agree = n_validate_disagree = 0
failures = []

skipped_scope = []

for path in files:
    name = os.path.relpath(path)
    try:
        src = open(path, encoding="utf-8").read()
    except Exception as e:
        print(f"SKIP {name}: cannot read ({e})")
        continue

    try:
        raw_probe = json.loads(src)
    except Exception:
        raw_probe = {}
    is_v4 = raw_probe.get("nbformat") == 4
    minor = raw_probe.get("nbformat_minor")

    # V1/V2 are explicitly scoped to v4 notebooks (no `convert()` step is
    # implemented in rust) -- v1/v2/v3 fixtures are noted separately, not
    # counted as failures.
    if not is_v4:
        skipped_scope.append((name, "not v4 (needs convert(), out of scope)"))
        continue

    py_valid = True
    py_err = None
    try:
        nb_py = nbformat.reads(src, as_version=4)
    except Exception as e:
        py_valid = False
        py_err = e
        nb_py = None

    # --- gate 2: reads() structural equality
    try:
        nb_rs = nbf_rust.reads(src)
        rs_reads_ok = True
    except Exception as e:
        rs_reads_ok = False
        nb_rs = None
        rs_reads_err = e

    if nb_py is not None:
        if not rs_reads_ok:
            n_reads_fail += 1
            failures.append((name, "reads", f"rust raised {rs_reads_err!r} but python succeeded"))
        else:
            same = normalize(nb_py) == normalize(nb_rs)
            iso = check_isinstance(nb_rs)
            if same and iso:
                n_reads_ok += 1
            else:
                # nbformat.reads() calls validate(), which has a *side effect*:
                # it repairs missing/duplicate cell `id` fields in place. A
                # notebook that needed repair will therefore differ only in
                # injected/rewritten `id` fields -- detect that specific class
                # rather than lump it in with real structural bugs.
                def strip_ids(x):
                    if isinstance(x, dict):
                        return {k: strip_ids(v) for k, v in x.items() if k != "id"}
                    if isinstance(x, list):
                        return [strip_ids(v) for v in x]
                    return x

                only_ids = strip_ids(normalize(nb_py)) == strip_ids(normalize(nb_rs))
                n_reads_fail += 1
                tag = "reads(id-repair side effect of validate())" if only_ids else "reads"
                failures.append((name, tag, f"structural_eq={same} isinstance_ok={iso}"))
    else:
        pass

    # --- gate 1: writes() byte-identical. Scoped to v4 (rust implements the
    # v4 rwbase split_lines/strip_transient rules only; v1/v2/v3 notebooks
    # have a different on-disk shape (e.g. `worksheets`) and are out of scope
    # -- already filtered out above via the `is_v4` continue.
    nb_for_write = nb_py

    if nb_for_write is not None:
        try:
            w_py = nbformat.writes(nb_for_write)
        except Exception as e:
            w_py = None
            w_py_err = e
        try:
            w_rs = nbf_rust.writes(nb_for_write)
        except Exception as e:
            w_rs = None
            w_rs_err = e

        if w_py is None:
            pass  # python itself can't write this one; not a rust bug
        elif w_rs is None:
            n_writes_fail += 1
            failures.append((name, "writes", f"rust raised {w_rs_err!r}"))
        elif w_py == w_rs:
            n_writes_ok += 1
        else:
            n_writes_fail += 1
            # find first divergence
            for i, (a, b) in enumerate(zip(w_py, w_rs)):
                if a != b:
                    ctx = (
                        f"@byte {i}: py={w_py[max(0,i-30):i+30]!r} "
                        f"rs={w_rs[max(0,i-30):i+30]!r} lens py={len(w_py)} rs={len(w_rs)}"
                    )
                    break
            else:
                ctx = f"length mismatch py={len(w_py)} rs={len(w_rs)}"
            failures.append((name, "writes", ctx))

    # --- gate 3: validate agreement. Rust's V3 validator has ONE schema
    # compiled in (v4.5, the current/newest minor) -- nbformat.validate()
    # instead auto-selects among v4.0..v4.5 schemas by the notebook's
    # declared `nbformat_minor`. To compare like-for-like we force Python to
    # validate against the *same* v4.5 schema rust uses. Separately we also
    # record what happens with Python's own auto-selected (declared-minor)
    # schema, to quantify the real-world divergence from that scope choice.
    import nbformat.validator as nvmod

    raw = json.loads(src)
    if raw.get("nbformat") == 4:
        try:
            py_ok_v45 = True
            try:
                nvmod.validate(raw, version=4, version_minor=5)
            except Exception:
                py_ok_v45 = False
            rs_ok = nbf_rust.is_valid_json(src)
            if py_ok_v45 == rs_ok:
                n_validate_agree += 1
            else:
                n_validate_disagree += 1
                failures.append((name, "validate", f"python(v4.5 schema)={py_ok_v45} rust(v4.5 schema)={rs_ok}"))

            declared_minor = raw.get("nbformat_minor", 0)
            if declared_minor != 5:
                py_ok_declared = True
                try:
                    nvmod.validate(raw, version=4, version_minor=declared_minor)
                except Exception:
                    py_ok_declared = False
                if py_ok_declared != rs_ok:
                    skipped_scope.append(
                        (
                            name,
                            f"validate: declared minor={declared_minor}, python(own schema)={py_ok_declared} "
                            f"vs rust(hardcoded v4.5 schema)={rs_ok} -- schema-selection out of scope for prototype",
                        )
                    )
        except Exception as e:
            failures.append((name, "validate-harness-error", repr(e)))

print(f"reads:    ok={n_reads_ok} fail={n_reads_fail}")
print(f"writes:   ok={n_writes_ok} fail={n_writes_fail}")
print(f"validate: agree={n_validate_agree} disagree={n_validate_disagree}  (both forced to v4.5 schema)")
print()
if failures:
    print("=== FAILURES (real divergences, in scope) ===")
    for name, stage, msg in failures:
        print(f"[{stage}] {name}: {msg}")
else:
    print("No in-scope failures.")
print()
if skipped_scope:
    print("=== OUT OF SCOPE / EXPECTED (not counted as failures) ===")
    for name, msg in skipped_scope:
        print(f"{name}: {msg}")
