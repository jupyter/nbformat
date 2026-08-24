import cProfile, pstats, io, sys, os
import nbformat

CORPUS = "corpus"

def profile_read(name, n=20):
    path = os.path.join(CORPUS, name + ".ipynb")
    src = open(path, encoding="utf-8").read()
    pr = cProfile.Profile()
    pr.enable()
    for _ in range(n):
        nbformat.reads(src, as_version=4)
    pr.disable()
    return pr

def profile_write(name, n=20):
    path = os.path.join(CORPUS, name + ".ipynb")
    src = open(path, encoding="utf-8").read()
    nb = nbformat.reads(src, as_version=4)
    pr = cProfile.Profile()
    pr.enable()
    for _ in range(n):
        nbformat.writes(nb)
    pr.disable()
    return pr

def show(pr, title, sortby, top=25):
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats(top)
    print(f"\n===== {title} sorted by {sortby} =====")
    print(s.getvalue())

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "large"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    pr_r = profile_read(name, n)
    show(pr_r, f"READ {name} x{n}", "cumulative")
    show(pr_r, f"READ {name} x{n}", "tottime")

    pr_w = profile_write(name, n)
    show(pr_w, f"WRITE {name} x{n}", "cumulative")
    show(pr_w, f"WRITE {name} x{n}", "tottime")
