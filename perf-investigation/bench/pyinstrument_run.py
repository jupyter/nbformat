import sys
from pyinstrument import Profiler
import nbformat

src = open("corpus/large.ipynb", encoding="utf-8").read()
nb = nbformat.reads(src, as_version=4)  # warm

p = Profiler(interval=0.0001, async_mode="disabled")
p.start()
for _ in range(30):
    nbformat.reads(src, as_version=4)
p.stop()
print("=== READ (large x30) ===")
print(p.output_text(unicode=True, color=False, show_all=True))

p2 = Profiler(interval=0.0001, async_mode="disabled")
p2.start()
for _ in range(30):
    nbformat.writes(nb)
p2.stop()
print("\n=== WRITE (large x30) ===")
print(p2.output_text(unicode=True, color=False, show_all=True))
