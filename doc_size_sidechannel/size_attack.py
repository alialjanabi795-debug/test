"""Compressed-size side channel: does the byte size of a document image reveal its type?

Pipeline (one command, rerunnable on any folder of labelled images):
  1. Re-encode every image and record byte sizes:
       jpeg_q85   baseline JPEG, quality 85
       png        PNG lossless (Pillow default zlib level 6)
       pjpeg      progressive JPEG, quality 85 (libjpeg default scan script)
       jxl        JPEG XL lossless (only if imagecodecs has libjxl)
     plus the byte length of every progressive-JPEG scan.
  2. Attack: Random Forest, stratified 5-fold CV, predicting the label from
       (i)  one total size per format, and
       (ii) the vector of progressive-scan sizes.
  3. Defense: pad each observed size up to the next of K bucket edges
     (K = 2, 4, 8 by default) and rerun the attack; report bandwidth overhead.
  4. Write sizes.csv, results.csv, results.md, per_class_f1.csv and
     attack_vs_overhead.png.

Input, either:
  --labels labels.csv   CSV with columns path,label (paths relative to the CSV)
  --images DIR          one sub-folder per class: DIR/<label>/<image>

Usage:
  python size_attack.py --labels data/rvlcdip/labels.csv --out results/
  python size_attack.py --images /srv/docs --out results/ --k 2 4 8 16
  python size_attack.py --labels mix/labels.csv --gray --max-side 1000 --out results/
"""
import argparse, csv, io, os, sys
from functools import partial
from multiprocessing import Pool

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

try:
    import imagecodecs
    HAVE_JXL = bool(imagecodecs.JPEGXL.available)
except Exception:
    HAVE_JXL = False

IMG_EXT = {".tif", ".tiff", ".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
FORMATS = [("jpeg_q85", "JPEG q=85"), ("png", "PNG lossless"),
           ("pjpeg", "Progressive JPEG"), ("jxl", "JPEG XL lossless")]


# ---------------------------------------------------------------- inputs

def load_items(args):
    if args.labels:
        root = os.path.dirname(os.path.abspath(args.labels))
        with open(args.labels, newline="") as f:
            return [(os.path.join(root, r["path"]), r["label"]) for r in csv.DictReader(f)]
    items = []
    for label in sorted(os.listdir(args.images)):
        d = os.path.join(args.images, label)
        if os.path.isdir(d):
            for fn in sorted(os.listdir(d)):
                if os.path.splitext(fn)[1].lower() in IMG_EXT:
                    items.append((os.path.join(d, fn), label))
    return items


# ---------------------------------------------------------------- encoding

def jpeg_scan_sizes(data):
    """Split a JPEG byte stream at its SOS markers.

    Returns [header, scan_1, ..., scan_n]: header is everything before the
    first SOS; scan_i runs from SOS_i to SOS_{i+1} (so it also carries the
    small Huffman-table segment emitted for the next scan); the last scan
    includes EOI. The pieces sum to len(data).
    """
    cuts, i, n = [], 2, len(data)
    while i < n - 1:
        if data[i] != 0xFF:
            raise ValueError("bad JPEG marker")
        m = data[i + 1]
        if m == 0xD9:  # EOI
            break
        if m == 0xFF:  # fill byte
            i += 1
            continue
        seglen = int.from_bytes(data[i + 2:i + 4], "big")
        if m != 0xDA:
            i += 2 + seglen
            continue
        cuts.append(i)
        i += 2 + seglen
        while i < n - 1:  # entropy-coded data ends at a non-stuffed, non-RST marker
            if data[i] == 0xFF and data[i + 1] != 0x00 and not 0xD0 <= data[i + 1] <= 0xD7:
                break
            i += 1
    bounds = [0] + cuts + [n]
    return [bounds[j + 1] - bounds[j] for j in range(len(bounds) - 1)]


def encode_one(item, gray=False, max_side=None):
    path, label = item
    try:
        img = Image.open(path)
        img.load()
    except Exception as e:
        return None, f"{path}: {e}"
    if img.mode not in ("L", "RGB"):
        img = img.convert("RGB" if img.mode in ("RGBA", "P", "CMYK", "YCbCr", "LA") else "L")
    if gray and img.mode != "L":
        img = img.convert("L")
    if max_side and max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.LANCZOS)
    rec = {"path": path, "label": label, "width": img.width, "height": img.height,
           "mode": img.mode}

    buf = io.BytesIO(); img.save(buf, "JPEG", quality=85)
    rec["jpeg_q85"] = buf.tell()
    buf = io.BytesIO(); img.save(buf, "PNG")
    rec["png"] = buf.tell()
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=85, progressive=True)
    rec["pjpeg"] = buf.tell()
    rec["scans"] = jpeg_scan_sizes(buf.getvalue())
    if HAVE_JXL:
        rec["jxl"] = len(imagecodecs.jpegxl_encode(np.asarray(img), lossless=True, effort=7))
    return rec, None


def encode_all(items, workers, gray=False, max_side=None):
    recs, errs = [], []
    with Pool(workers) as pool:
        fn = partial(encode_one, gray=gray, max_side=max_side)
        for k, (rec, err) in enumerate(pool.imap(fn, items, chunksize=8), 1):
            (recs.append(rec) if rec else errs.append(err))
            if k % 250 == 0:
                print(f"  encoded {k}/{len(items)}", flush=True)
    for e in errs[:10]:
        print("  skipped:", e, file=sys.stderr)
    if errs:
        print(f"  skipped {len(errs)} unreadable images", file=sys.stderr)
    return recs


def write_sizes(recs, fmts, n_scan, path):
    cols = ["path", "label", "width", "height", "mode"] + fmts + \
           ["pjpeg_header"] + [f"pjpeg_scan{j}" for j in range(1, n_scan)]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in recs:
            scans = r["scans"] + [0] * (n_scan - len(r["scans"]))
            w.writerow([r["path"], r["label"], r["width"], r["height"], r["mode"]] +
                       [r[k] for k in fmts] + scans)


def read_sizes(path, fmts):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    scan_cols = [c for c in rows[0] if c.startswith("pjpeg_")]
    recs = []
    for r in rows:
        rec = {k: int(r[k]) for k in fmts + ["width", "height"]}
        rec["label"] = r["label"]
        rec["scans"] = [int(r[c]) for c in scan_cols]
        recs.append(rec)
    return recs


# ---------------------------------------------------------------- attack / defense

def bucket_edges(x, k, scheme):
    """K upper edges covering x; the last edge is max(x) so nothing is truncated."""
    x = np.asarray(x, dtype=float)
    if scheme == "quantile":
        edges = np.quantile(x, np.arange(1, k + 1) / k)
    else:  # log-spaced between min and max
        edges = np.geomspace(max(x.min(), 1), x.max(), k + 1)[1:]
    edges[-1] = x.max()
    return np.unique(np.ceil(edges))


def pad(x, edges):
    """Pad every value up to the smallest edge >= it."""
    return edges[np.searchsorted(edges, x, side="left")]


def pad_matrix(X, k, scheme):
    return np.column_stack([pad(X[:, j], bucket_edges(X[:, j], k, scheme))
                            for j in range(X.shape[1])])


def attack(X, y, seed, trees):
    """Random Forest, stratified 5-fold CV. min_samples_leaf is picked by an
    inner 3-fold CV on each training fold: with only 1-2 noisy continuous
    features an unregularised forest overfits badly and understates the leak."""
    from sklearn.base import clone
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, f1_score
    from sklearn.model_selection import GridSearchCV, StratifiedKFold
    rf = RandomForestClassifier(n_estimators=trees, random_state=seed)
    clf = GridSearchCV(rf, {"min_samples_leaf": [1, 5, 20, 50]}, scoring="accuracy",
                       cv=StratifiedKFold(n_splits=3, shuffle=True, random_state=seed), n_jobs=-1)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    acc, f1, pred = [], [], np.empty_like(y)
    for tr, te in cv.split(X, y):
        pred[te] = clone(clf).fit(X[tr], y[tr]).predict(X[te])
        acc.append(accuracy_score(y[te], pred[te]))
        f1.append(f1_score(y[te], pred[te], average="macro"))
    return np.mean(acc), np.std(acc), np.mean(f1), np.std(f1), pred


def run_experiments(recs, fmts, ks, scheme, seed, trees):
    y = np.array([r["label"] for r in recs])
    n_scan = max(len(r["scans"]) for r in recs)
    scans = np.array([r["scans"] + [0] * (n_scan - len(r["scans"])) for r in recs], float)

    names = dict(FORMATS)
    feature_sets = [(names[f] + " — total size", f, np.array([[r[f]] for r in recs], float))
                    for f in fmts]
    feature_sets.append((f"Progressive JPEG — per-scan sizes ({n_scan} features)",
                         "pjpeg_scans", scans))

    rows, preds = [], {}
    for name, key, X in feature_sets:
        base = X.sum()
        for k in [None] + list(ks):
            Xk = X if k is None else pad_matrix(X, k, scheme)
            acc, acc_sd, f1, f1_sd, pred = attack(Xk, y, seed, trees)
            if k is None:
                preds[name] = pred
            rows.append({"features": name, "key": key, "K": "none" if k is None else k,
                         "overhead_pct": 100 * (Xk.sum() / base - 1),
                         "accuracy": acc, "accuracy_sd": acc_sd,
                         "macro_f1": f1, "macro_f1_sd": f1_sd})
            print(f"  {name:55s} K={rows[-1]['K']!s:>4}  acc={acc:.3f}  "
                  f"F1={f1:.3f}  overhead={rows[-1]['overhead_pct']:.1f}%", flush=True)

    # Control: dimensions only. Not visible through TLS, but tells us how much
    # of the size signal is just "this class is scanned at a different size".
    Xwh = np.array([[r["width"], r["height"]] for r in recs], float)
    acc, acc_sd, f1, f1_sd, _ = attack(Xwh, y, seed, trees)
    rows.append({"features": "Control: image width & height (not on the wire)", "key": "wh",
                 "K": "none", "overhead_pct": 0.0, "accuracy": acc, "accuracy_sd": acc_sd,
                 "macro_f1": f1, "macro_f1_sd": f1_sd})
    print(f"  control W,H  acc={acc:.3f}  F1={f1:.3f}")
    return rows, y, preds


def write_per_class(y, preds, out):
    """Per-class F1 of each unpadded attack (out-of-fold predictions)."""
    from sklearn.metrics import f1_score
    labels = sorted(set(y))
    names = list(preds)
    table = {n: f1_score(y, preds[n], labels=labels, average=None) for n in names}
    with open(os.path.join(out, "per_class_f1.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["label"] + names)
        for i, lab in enumerate(labels):
            w.writerow([lab] + [f"{table[n][i]:.4f}" for n in names])


# ---------------------------------------------------------------- outputs

def write_results(rows, n_img, n_cls, out):
    with open(os.path.join(out, "results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    chance = 100 / n_cls
    lines = [f"Images: {n_img}, classes: {n_cls}, chance accuracy: {chance:.2f}%. "
             "Random Forest (min_samples_leaf tuned by inner 3-fold CV), stratified 5-fold CV "
             "(mean ± sd over outer folds).", "",
             "| Observed features | Padding K | Bandwidth overhead | Accuracy | Macro-F1 |",
             "|---|---:|---:|---:|---:|"]
    for r in rows:
        lines.append(f"| {r['features']} | {r['K']} | {r['overhead_pct']:.1f}% | "
                     f"{100*r['accuracy']:.1f} ± {100*r['accuracy_sd']:.1f}% | "
                     f"{100*r['macro_f1']:.1f} ± {100*r['macro_f1_sd']:.1f}% |")
    md = "\n".join(lines) + "\n"
    with open(os.path.join(out, "results.md"), "w") as f:
        f.write(md)
    print("\n" + md)


def plot(rows, n_cls, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    series = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
    ink, ink2, grid = "#0b0b0b", "#52514e", "#e4e3df"
    plt.rcParams.update({"font.size": 10, "axes.edgecolor": ink2, "axes.labelcolor": ink,
                         "xtick.color": ink2, "ytick.color": ink2})
    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    fig.patch.set_facecolor("#fcfcfb"); ax.set_facecolor("#fcfcfb")

    keys = [k for k in dict.fromkeys(r["key"] for r in rows) if k != "wh"]
    markers = ["o", "s", "D", "^", "v"]
    for i, key in enumerate(keys):
        pts = sorted((r for r in rows if r["key"] == key), key=lambda r: r["overhead_pct"])
        x = [r["overhead_pct"] for r in pts]
        y = [100 * r["accuracy"] for r in pts]
        ax.plot(x, y, color=series[i % len(series)], lw=2, marker=markers[i % 5], ms=7,
                mec="#fcfcfb", mew=1.5, label=pts[0]["features"], zorder=3)
        if i == len(keys) - 1:  # label K on one series; all share the left-to-right order
            for r, xi, yi in zip(pts, x, y):
                ax.annotate("no padding" if r["K"] == "none" else f"K={r['K']}", (xi, yi),
                            textcoords="offset points", xytext=(6, 6), fontsize=8, color=ink2)
    ax.axhline(100 / n_cls, color=ink2, lw=1, ls="--", zorder=1)
    ax.text(ax.get_xlim()[1], 100 / n_cls + 1, f"chance {100/n_cls:.2f}%", ha="right",
            va="bottom", fontsize=8, color=ink2)
    ax.set_xlabel("Bandwidth overhead from padding (%)")
    ax.set_ylabel("Attack accuracy, 5-fold CV (%)")
    ax.set_title("Document-type inference from compressed size vs. padding cost",
                 color=ink, loc="left", fontsize=11)
    ax.set_ylim(0, None)
    ax.grid(True, color=grid, lw=0.8, zorder=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc="upper right", labelcolor=ink)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "attack_vs_overhead.png"), facecolor=fig.get_facecolor())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--labels", help="CSV with columns path,label")
    src.add_argument("--images", help="folder with one sub-folder per class")
    ap.add_argument("--sizes", help="reuse an existing sizes.csv instead of re-encoding")
    ap.add_argument("--out", required=True)
    ap.add_argument("--k", type=int, nargs="+", default=[2, 4, 8])
    ap.add_argument("--buckets", choices=["quantile", "log"], default="quantile",
                    help="bucket edges: equal-frequency quantiles (default) or log-spaced")
    ap.add_argument("--gray", action="store_true", help="convert every image to greyscale first")
    ap.add_argument("--max-side", type=int, help="downscale so the longest side is at most this")
    ap.add_argument("--trees", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    args = ap.parse_args()
    if not (args.labels or args.images or args.sizes):
        ap.error("give --labels, --images or --sizes")
    os.makedirs(args.out, exist_ok=True)

    if args.sizes:
        with open(args.sizes) as f:
            header = f.readline()
        fmts = [k for k, _ in FORMATS if k in header.strip().split(",")]
        recs = read_sizes(args.sizes, fmts)
    else:
        fmts = [k for k, _ in FORMATS if k != "jxl" or HAVE_JXL]
        if not HAVE_JXL:
            print("libjxl not available (pip install imagecodecs); skipping JPEG XL")
        items = load_items(args)
        print(f"encoding {len(items)} images with {args.workers} workers")
        recs = encode_all(items, args.workers, args.gray, args.max_side)
        write_sizes(recs, fmts, max(len(r["scans"]) for r in recs),
                    os.path.join(args.out, "sizes.csv"))

    n_cls = len({r["label"] for r in recs})
    print(f"running attacks on {len(recs)} images, {n_cls} classes")
    rows, y, preds = run_experiments(recs, fmts, args.k, args.buckets, args.seed, args.trees)
    write_results(rows, len(recs), n_cls, args.out)
    write_per_class(y, preds, args.out)
    plot(rows, n_cls, args.out)
    print(f"wrote {args.out}/results.md, results.csv, attack_vs_overhead.png")


if __name__ == "__main__":
    main()
