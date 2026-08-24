"""Generate a synthetic notebook corpus spanning realistic shapes/sizes."""
import base64, json, os, random, sys

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
rng = random.Random(20260824)

PNG = base64.b64encode(bytes(rng.getrandbits(8) for _ in range(64 * 1024))).decode()

def cell_code(i, out_kinds):
    src = "\n".join(f"x{i}_{j} = compute({j}) * {j}  # line {j}" for j in range(rng.randint(3, 40)))
    outs = []
    for kind in out_kinds:
        if kind == "stream":
            outs.append({"output_type": "stream", "name": "stdout",
                         "text": "".join(f"row {k}: value={k*3.14159}\n" for k in range(rng.randint(5, 200)))})
        elif kind == "text":
            outs.append({"output_type": "execute_result", "execution_count": i, "metadata": {},
                         "data": {"text/plain": "<pandas.DataFrame>\n" + "\n".join(f"{k}  {k*2}  {k*3}" for k in range(30))}})
        elif kind == "image":
            outs.append({"output_type": "display_data", "metadata": {},
                         "data": {"image/png": PNG, "text/plain": "<Figure size 640x480>"}})
        elif kind == "error":
            outs.append({"output_type": "error", "ename": "ValueError", "evalue": "bad",
                         "traceback": [f"frame {k}" for k in range(12)]})
    return {"cell_type": "code", "id": f"cell-{i:05d}", "execution_count": i,
            "metadata": {"collapsed": False, "tags": ["t1", "t2"]}, "source": src, "outputs": outs}

def cell_md(i):
    return {"cell_type": "markdown", "id": f"md-{i:05d}", "metadata": {},
            "source": "## Section %d\n\n%s" % (i, "\n".join("Some prose line %d." % k for k in range(rng.randint(2, 20))))}

def notebook(n_cells, img_every=0):
    cells = []
    for i in range(n_cells):
        if i % 4 == 0:
            cells.append(cell_md(i))
        else:
            kinds = ["stream"] if i % 3 else ["text", "stream"]
            if img_every and i % img_every == 0:
                kinds.append("image")
            if i % 17 == 0:
                kinds.append("error")
            cells.append(cell_code(i, kinds))
    return {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.12.0", "mimetype": "text/x-python",
                              "file_extension": ".py", "nbconvert_exporter": "python",
                              "codemirror_mode": {"name": "ipython", "version": 3}, "pygments_lexer": "ipython3"}},
            "nbformat": 4, "nbformat_minor": 5}

SPECS = {"tiny": (5, 0), "small": (40, 0), "medium": (250, 0), "large": (1200, 0), "image_heavy": (120, 3)}
for name, (n, img) in SPECS.items():
    p = os.path.join(OUT, name + ".ipynb")
    with open(p, "w") as f:
        json.dump(notebook(n, img), f, indent=1, sort_keys=True, separators=(",", ": "), ensure_ascii=False)
    print(f"{name:12s} {os.path.getsize(p)/1024:9.1f} KiB  {n} cells")
