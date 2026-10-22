import os, sys, pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from size_attack import attack
d = pd.read_csv(sys.argv[1])  # usage: check_dimensions.py SIZES_CSV [LABEL ...]
if len(sys.argv) > 2:
    d = d[d.label.isin(sys.argv[2:])].reset_index(drop=True)
y = np.asarray(d.label.astype(str).tolist())
px = (d.width * d.height).values
print("dims range: w", d.width.min(), d.width.max(), " h", d.height.min(), d.height.max(), " distinct (w,h):", len(d.groupby(['width','height'])))
for f in ["jpeg_q85", "jxl"]:
    a = attack((d[f] / px).values[:, None], y, 0, 200); print(f, "bytes/pixel only   acc=%.3f F1=%.3f" % (a[0], a[2]))
    a = attack(d[[f, "width", "height"]].values, y, 0, 200); print(f, "size + W,H         acc=%.3f F1=%.3f" % (a[0], a[2]))
for f in ["jpeg_q85", "png", "pjpeg", "jxl"]:
    print(f, "K=1 (pad all to max) overhead %.0f%%" % (100 * (d[f].max() * len(d) / d[f].sum() - 1)))
