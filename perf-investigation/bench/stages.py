"""Stage-by-stage cost breakdown for nbformat reads()/writes()."""
import copy, gc, json, os, sys, time

CORPUS = sys.argv[1] if len(sys.argv) > 1 else "corpus"
sys.path.insert(0, os.path.dirname(__file__))

import nbformat
from nbformat.notebooknode import from_dict
from nbformat.v4.rwbase import rejoin_lines, split_lines, strip_transient
from nbformat.validator import validate, _normalize
from nbformat.reader import get_version, parse_json

def timeit(fn, n=None, min_time=0.3):
    fn()
    reps, t0 = 0, time.perf_counter()
    while True:
        fn(); reps += 1
        el = time.perf_counter() - t0
        if (n and reps >= n) or (not n and el > min_time and reps >= 5):
            return el / reps

def report(name):
    path = os.path.join(CORPUS, name + ".ipynb")
    src = open(path, encoding="utf-8").read()
    print(f"\n==== {name} ({len(src)/1e6:.2f} MB) ====")

    # ---- READ stages ----
    t_loads = timeit(lambda: json.loads(src))
    nb_dict = json.loads(src)

    t_fromdict = timeit(lambda: from_dict(nb_dict))
    nb_wrapped = from_dict(nb_dict)

    # rejoin_lines / strip_transient mutate in place -> need fresh copies each call
    def mk_wrapped():
        return from_dict(nb_dict)

    t_rejoin = timeit(lambda: rejoin_lines(mk_wrapped()))
    # isolate rejoin only (subtract from_dict cost via a wrapper that reuses one fresh copy per rep is hard w/ in place;
    # instead time fromdict+rejoin combined then subtract known fromdict time)
    t_fromdict_rejoin = timeit(lambda: rejoin_lines(from_dict(nb_dict)))
    t_rejoin_only = max(t_fromdict_rejoin - t_fromdict, 0)

    nb_for_strip = rejoin_lines(from_dict(nb_dict))
    def mk_rejoin():
        return rejoin_lines(from_dict(nb_dict))
    t_full_to_strip = timeit(lambda: strip_transient(mk_rejoin()))
    t_strip_only = max(t_full_to_strip - t_fromdict_rejoin, 0)

    # full to_notebook (from_dict+rejoin+strip)
    from nbformat.v4.nbjson import to_notebook
    t_to_notebook = timeit(lambda: to_notebook(nb_dict))
    nb = to_notebook(copy.deepcopy(nb_dict))

    # validate alone (as called inside reads(), i.e. public validate())
    def mk_fresh_nb():
        return to_notebook(nb_dict)
    t_validate_only = timeit(lambda: validate(mk_fresh_nb()))
    t_tonb_plus_validate = timeit(lambda: validate(to_notebook(nb_dict)))
    # subtract to_notebook cost measured above to isolate validate
    t_validate_isolated = max(t_tonb_plus_validate - t_to_notebook, 0)

    # full reads()
    t_reads = timeit(lambda: nbformat.reads(src, as_version=4))

    print(f"  json.loads          {t_loads*1e3:8.3f} ms")
    print(f"  from_dict           {t_fromdict*1e3:8.3f} ms")
    print(f"  rejoin_lines        {t_rejoin_only*1e3:8.3f} ms  (isolated, from_dict+rejoin={t_fromdict_rejoin*1e3:.3f})")
    print(f"  strip_transient(rd) {t_strip_only*1e3:8.3f} ms  (isolated)")
    print(f"  to_notebook (total) {t_to_notebook*1e3:8.3f} ms  (from_dict+rejoin+strip, should ~= sum above)")
    print(f"  validate (isolated) {t_validate_isolated*1e3:8.3f} ms  (fresh-nb+validate minus to_notebook)")
    print(f"  ---")
    print(f"  SUM (loads+to_nb+validate) = {(t_loads+t_to_notebook+t_validate_isolated)*1e3:8.3f} ms")
    print(f"  nbformat.reads() actual    = {t_reads*1e3:8.3f} ms")

    # ---- WRITE stages ----
    nb_full = nbformat.reads(src, as_version=4)

    t_deepcopy = timeit(lambda: copy.deepcopy(nb_full))
    nb_copy = copy.deepcopy(nb_full)

    def mk_copy():
        return copy.deepcopy(nb_full)

    t_dc_split = timeit(lambda: split_lines(mk_copy()))
    t_split_only = max(t_dc_split - t_deepcopy, 0)

    def mk_split():
        return split_lines(copy.deepcopy(nb_full))
    t_dc_split_strip = timeit(lambda: strip_transient(mk_split()))
    t_strip_w_only = max(t_dc_split_strip - t_dc_split, 0)

    nb_ready = strip_transient(split_lines(copy.deepcopy(nb_full)))
    t_dumps = timeit(lambda: json.dumps(nb_ready, cls=__import__("nbformat.v4.nbjson", fromlist=["BytesEncoder"]).BytesEncoder,
                                          indent=1, sort_keys=True, separators=(",", ": "), ensure_ascii=False))

    t_validate_w = timeit(lambda: validate(nb_full))

    t_writes = timeit(lambda: nbformat.writes(nb_full))

    print(f"\n  -- write stages --")
    print(f"  validate (in writes) {t_validate_w*1e3:8.3f} ms")
    print(f"  copy.deepcopy         {t_deepcopy*1e3:8.3f} ms")
    print(f"  split_lines            {t_split_only*1e3:8.3f} ms  (isolated)")
    print(f"  strip_transient(wr)     {t_strip_w_only*1e3:8.3f} ms  (isolated)")
    print(f"  json.dumps              {t_dumps*1e3:8.3f} ms")
    print(f"  ---")
    print(f"  SUM (validate+dc+split+strip+dumps) = {(t_validate_w+t_deepcopy+t_split_only+t_strip_w_only+t_dumps)*1e3:8.3f} ms")
    print(f"  nbformat.writes() actual             = {t_writes*1e3:8.3f} ms")

for name in (sys.argv[2:] or ["large", "image_heavy", "medium"]):
    report(name)
