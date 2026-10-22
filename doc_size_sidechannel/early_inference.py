"""Early inference: how much of a JPEG must arrive before a classifier knows the document type?

For each image:
  * encode as progressive JPEG (q=85) and decode the prefix ending after scan k,
    for k = 1..N (the last one is the full file);
  * encode as baseline/sequential JPEG (q=85), truncate it at the *same byte
    counts* and decode, plus the full sequential file.
Every decoded image is classified by a pretrained document classifier
(default: microsoft/dit-base-finetuned-rvlcdip). We report accuracy against
the share of the file received, and the share needed to reach 90% of each
format's full-file accuracy.

A truncated sequential JPEG decodes with the missing blocks filled with flat
grey (128). Those blocks are repainted white, i.e. as a blank page, which
favours the sequential baseline.

Usage:
  python early_inference.py --labels data/rvlcdip/labels.csv --per-class 50 --out results_exp3/
Labels must match the model's class names, ignoring case and '_' vs ' '.
"""
import argparse, csv, io, itertools, os, random

import numpy as np
from PIL import Image, ImageFile

from size_attack import jpeg_scan_sizes, load_items

ImageFile.LOAD_TRUNCATED_IMAGES = True
EOI = b"\xff\xd9"


def norm(s):
    return s.lower().replace("_", " ").strip()


def decode_prefix(data, n, white_fill):
    if n >= len(data):
        return Image.open(io.BytesIO(data)).convert("RGB")
    img = Image.open(io.BytesIO(data[:n] + EOI))
    img.load()
    if not white_fill:
        return img.convert("RGB")
    a = np.array(img)
    bs = 8 if a.ndim == 2 else 16  # MCU: 8 px grey, 16 px colour with 4:2:0
    h, w = a.shape[:2]
    rows, cols = -(-h // bs), -(-w // bs)
    missing = np.array([[np.all(a[r*bs:(r+1)*bs, c*bs:(c+1)*bs] == 128) for c in range(cols)]
                        for r in range(rows)]).ravel()
    decoded = np.flatnonzero(~missing)
    first_missing = decoded[-1] + 1 if len(decoded) else 0  # undecoded blocks are a raster suffix
    for b in range(first_missing, rows * cols):
        r, c = divmod(b, cols)
        a[r*bs:(r+1)*bs, c*bs:(c+1)*bs] = 255
    return Image.fromarray(a).convert("RGB")


def views(path):
    """Yield (format, checkpoint, bytes_received, file_size, image) for one source image."""
    img = Image.open(path)
    img = img.convert("L" if img.mode in ("1", "L", "I;16", "I", "LA") else "RGB")
    b = io.BytesIO(); img.save(b, "JPEG", quality=85, progressive=True); prog = b.getvalue()
    b = io.BytesIO(); img.save(b, "JPEG", quality=85); seq = b.getvalue()
    cuts = list(itertools.accumulate(jpeg_scan_sizes(prog)))[1:]  # end of scan 1..N
    for k, c in enumerate(cuts, 1):
        yield "progressive", f"scan {k}", c, len(prog), decode_prefix(prog, c, False)
        yield "sequential", f"scan {k}", min(c, len(seq)), len(seq), decode_prefix(seq, c, True)
    yield "sequential", "full", len(seq), len(seq), decode_prefix(seq, len(seq), True)


def bytes_to_reach(points, target):
    """(first checkpoint with acc >= target, linear interpolation from the previous one).

    A progressive image only changes at scan ends, so the checkpoint value is
    exact for it; for sequential the interpolation is a finer estimate.
    """
    prev = None
    for x, y in points:
        if y >= target:
            if prev is None or y == prev[1]:
                return x, x
            return x, prev[0] + (target - prev[1]) * (x - prev[0]) / (y - prev[1])
        prev = (x, y)
    return float("nan"), float("nan")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--labels")
    src.add_argument("--images")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="microsoft/dit-base-finetuned-rvlcdip")
    ap.add_argument("--per-class", type=int, default=50)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    import torch
    from transformers import AutoImageProcessor, AutoModelForImageClassification
    proc = AutoImageProcessor.from_pretrained(args.model)
    model = AutoModelForImageClassification.from_pretrained(args.model).eval()
    name_to_id = {norm(v): int(k) for k, v in model.config.id2label.items()}

    items = load_items(args)
    unknown = {lab for _, lab in items if norm(lab) not in name_to_id}
    if unknown:
        raise SystemExit(f"labels not known to the model: {sorted(unknown)}")
    rng = random.Random(args.seed)
    by_class = {}
    for p, lab in items:
        by_class.setdefault(lab, []).append(p)
    items = [(p, lab) for lab in sorted(by_class)
             for p in rng.sample(by_class[lab], min(args.per_class, len(by_class[lab])))]
    print(f"{len(items)} images, {len(by_class)} classes, model {args.model}", flush=True)

    rows, pending = [], []

    def flush():
        with torch.inference_mode():
            x = proc([v[-1] for v in pending], return_tensors="pt")
            pred = model(**x).logits.argmax(-1).tolist()
        for (path, lab, fmt, ck, n, size, _), p in zip(pending, pred):
            rows.append({"path": path, "label": lab, "format": fmt, "checkpoint": ck,
                         "bytes": n, "file_size": size, "pct_bytes": 100 * n / size,
                         "pred": model.config.id2label[p], "correct": int(p == name_to_id[norm(lab)])})
        pending.clear()

    for i, (path, lab) in enumerate(items, 1):
        for v in views(path):
            pending.append((path, lab) + v)
            if len(pending) >= args.batch:
                flush()
        if i % 25 == 0:
            print(f"  {i}/{len(items)} images", flush=True)
    if pending:
        flush()

    with open(os.path.join(args.out, "predictions.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    # Aggregate per (format, checkpoint). sklearn is imported only now: loading its
    # OpenMP runtime next to torch's slowed CPU inference several-fold.
    from sklearn.metrics import f1_score
    summary = []
    for fmt in ("progressive", "sequential"):
        cks = list(dict.fromkeys(r["checkpoint"] for r in rows if r["format"] == fmt))
        for ck in cks:
            sel = [r for r in rows if r["format"] == fmt and r["checkpoint"] == ck]
            summary.append({
                "format": fmt, "checkpoint": ck,
                "pct_bytes": np.mean([r["pct_bytes"] for r in sel]),
                "kb": np.mean([r["bytes"] for r in sel]) / 1024,
                "accuracy": np.mean([r["correct"] for r in sel]),
                "macro_f1": f1_score([norm(r["label"]) for r in sel], [norm(r["pred"]) for r in sel],
                                     average="macro"),
            })
    with open(os.path.join(args.out, "summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)

    n_cls = len(by_class)
    reach = {}
    for fmt in ("progressive", "sequential"):
        pts = sorted((s["pct_bytes"], s["accuracy"]) for s in summary if s["format"] == fmt)
        final = pts[-1][1]
        reach[fmt] = (final, bytes_to_reach(pts, 0.9 * final))

    prog = {s["checkpoint"]: s for s in summary if s["format"] == "progressive"}
    seq = {s["checkpoint"]: s for s in summary if s["format"] == "sequential"}
    lines = [f"Images: {len(items)} ({n_cls} classes, chance {100/n_cls:.2f}%). Model: `{args.model}`. "
             "Both formats JPEG q=85; sequential is truncated at the progressive scan's byte count.", "",
             "| Bytes received | Progressive: % of file | Progressive acc / macro-F1 "
             "| Sequential: % of file | Sequential acc / macro-F1 |",
             "|---|---:|---:|---:|---:|"]
    for ck in prog:
        p, s = prog[ck], seq[ck]
        lines.append(f"| end of {ck} ({p['kb']:.1f} KB) | {p['pct_bytes']:.1f}% | "
                     f"{100*p['accuracy']:.1f}% / {100*p['macro_f1']:.1f}% | {s['pct_bytes']:.1f}% | "
                     f"{100*s['accuracy']:.1f}% / {100*s['macro_f1']:.1f}% |")
    s = seq["full"]
    lines.append(f"| full sequential file ({s['kb']:.1f} KB) | — | — | 100.0% | "
                 f"{100*s['accuracy']:.1f}% / {100*s['macro_f1']:.1f}% |")
    lines += ["", "| Format | Full-file accuracy | % of bytes to reach 90% of it: first checkpoint "
              "(interpolated) |", "|---|---:|---:|"]
    for fmt, (final, (pct, interp)) in reach.items():
        lines.append(f"| {fmt} | {100*final:.1f}% | {pct:.1f}% ({interp:.1f}%) |")
    md = "\n".join(lines) + "\n"
    with open(os.path.join(args.out, "results.md"), "w") as f:
        f.write(md)
    print("\n" + md)

    plot(summary, reach, n_cls, args.out)


def plot(summary, reach, n_cls, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = {"progressive": "#2a78d6", "sequential": "#eb6834"}
    ink, ink2, grid, bg = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    fig.patch.set_facecolor(bg); ax.set_facecolor(bg)
    for fmt, marker in (("progressive", "o"), ("sequential", "s")):
        pts = sorted((s["pct_bytes"], 100 * s["accuracy"]) for s in summary if s["format"] == fmt)
        x, y = zip(*pts)
        final, (pct, _) = reach[fmt]
        ax.plot(x, y, color=colors[fmt], lw=2, marker=marker, ms=7, mec=bg, mew=1.5, zorder=3,
                label=f"{fmt.capitalize()} JPEG — 90% of final at {pct:.0f}% of bytes")
        ax.axvline(pct, color=colors[fmt], lw=1, ls=":", zorder=2)
    ax.axhline(100 / n_cls, color=ink2, lw=1, ls="--", zorder=1)
    ax.text(100, 100 / n_cls + 1.5, f"chance {100/n_cls:.2f}%", ha="right", va="bottom",
            fontsize=8, color=ink2)
    ax.set_xlim(0, 102); ax.set_ylim(0, 100)
    ax.set_xlabel("Bytes received (% of that format's full file)")
    ax.set_ylabel("Classifier accuracy on the partial image (%)")
    ax.set_title("Document type from a partially received JPEG", color=ink, loc="left", fontsize=11)
    ax.grid(True, color=grid, lw=0.8, zorder=0)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(colors=ink2)
    ax.legend(frameon=False, fontsize=8, loc="lower right", labelcolor=ink)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "accuracy_vs_bytes.png"), facecolor=bg)


if __name__ == "__main__":
    main()
