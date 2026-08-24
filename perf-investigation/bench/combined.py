import time, copy, json, sys, os
import orjson
import nbformat
from nbformat._struct import Struct
from nbformat.v4.rwbase import _non_text_split_mimes

CORPUS = "corpus"

def timeit(fn, n=15):
    fn()
    t0=time.perf_counter()
    for _ in range(n): fn()
    return (time.perf_counter()-t0)/n

def fast_init(self, *args, **kw):
    dict.__init__(self, *args, **kw)

def _plain_copy(v):
    if isinstance(v, dict):
        return {k: _plain_copy(vv) for k, vv in v.items()}
    if isinstance(v, list):
        return [_plain_copy(vv) for vv in v]
    return v

def _plain_mimebundle_split(data):
    r = {}
    for k, v in data.items():
        if isinstance(v, str) and (k.startswith("text/") or k in _non_text_split_mimes):
            r[k] = v.splitlines(True)
        else:
            r[k] = _plain_copy(v)
    return r

def _plain_output(o):
    out = {}
    otype = o.get("output_type", "")
    for k, v in o.items():
        if k == "data" and otype in {"execute_result", "display_data"}:
            out[k] = _plain_mimebundle_split(v)
        elif k == "text" and otype == "stream" and isinstance(v, str):
            out[k] = v.splitlines(True)
        else:
            out[k] = _plain_copy(v)
    return out

def _plain_cell(cell):
    out = {}
    for k, v in cell.items():
        if k == "source" and isinstance(v, str):
            out[k] = v.splitlines(True)
        elif k == "metadata":
            out[k] = {mk: mv for mk, mv in v.items() if mk != "trusted"}
        elif k == "attachments":
            out[k] = {ak: _plain_mimebundle_split(av) for ak, av in v.items()}
        elif k == "outputs":
            out[k] = [_plain_output(o) for o in v]
        else:
            out[k] = _plain_copy(v)
    return out

def build_plain_for_write(nb):
    out = {}
    for k, v in nb.items():
        if k == "metadata":
            out[k] = {mk: mv for mk, mv in v.items() if mk not in ("orig_nbformat", "orig_nbformat_minor", "signature")}
        elif k == "cells":
            out[k] = [_plain_cell(c) for c in v]
        else:
            out[k] = _plain_copy(v)
    return out

def optimized_writes(nb):
    nbformat.validate(nb)  # keep semantics: still validates
    plain = build_plain_for_write(nb)
    return orjson.dumps(plain, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS).decode("utf-8")

for name in ["large", "image_heavy", "medium"]:
    path = os.path.join(CORPUS, name + ".ipynb")
    src = open(path, encoding="utf-8").read()
    print(f"\n==== {name} ====")

    # baseline (unpatched)
    from nbformat._struct import Struct as S0
    def orig_init(self, *args, **kw):
        object.__setattr__(self, "_allownew", True)
        dict.__init__(self, *args, **kw)
    Struct.__init__ = orig_init
    t_reads_base = timeit(lambda: nbformat.reads(src, as_version=4))
    nb_base = nbformat.reads(src, as_version=4)
    t_writes_base = timeit(lambda: nbformat.writes(nb_base))

    # patched _allownew only
    Struct.__init__ = fast_init
    t_reads_allownew = timeit(lambda: nbformat.reads(src, as_version=4))
    nb_p = nbformat.reads(src, as_version=4)
    t_writes_allownew = timeit(lambda: nbformat.writes(nb_p))

    # + single-pass + orjson for writes
    t_writes_opt = timeit(lambda: optimized_writes(nb_p))
    s_base = nbformat.writes(nb_base)
    s_opt = optimized_writes(nb_p)

    print(f"  reads:  baseline={t_reads_base*1e3:7.2f}ms   +allownew-fix={t_reads_allownew*1e3:7.2f}ms  ({t_reads_base/t_reads_allownew:.2f}x)")
    print(f"  writes: baseline={t_writes_base*1e3:7.2f}ms   +allownew-fix={t_writes_allownew*1e3:7.2f}ms  ({t_writes_base/t_writes_allownew:.2f}x)   +singlepass+orjson={t_writes_opt*1e3:7.2f}ms  ({t_writes_base/t_writes_opt:.2f}x total)")
