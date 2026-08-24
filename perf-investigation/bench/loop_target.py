import time, sys
import nbformat
src = open("corpus/large.ipynb", encoding="utf-8").read()
nb = nbformat.reads(src, as_version=4)
t_end = time.time() + 12
while time.time() < t_end:
    nbformat.writes(nb)
