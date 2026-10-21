"""Download a class-balanced subset of RVL-CDIP from Hugging Face.

Source: chainyo/rvl-cdip (full-resolution RVL-CDIP TIFFs in parquet, max side
1000 px). Only the 40k-image *test* split is used; its 15 shards are sorted by
label, so each shard is downloaded in full, sampled, then deleted.

Output layout (the same layout size_attack.py accepts for your own data):
    OUT/images/<class_name>/<idx>.tif   original bytes, untouched
    OUT/labels.csv                      path,label  (path relative to OUT)

Usage:
    python fetch_rvlcdip.py --out data/rvlcdip --per-class 300 --seed 0
"""
import argparse, csv, os, random, tempfile, urllib.request
from collections import defaultdict

import pyarrow.parquet as pq

REPO = "chainyo/rvl-cdip"
N_SHARDS = 15
CLASSES = ["advertisement", "budget", "email", "file_folder", "form", "handwritten",
           "invoice", "letter", "memo", "news_article", "presentation", "questionnaire",
           "resume", "scientific_publication", "scientific_report", "specification"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--per-class", type=int, default=300)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    rng = random.Random(args.seed)

    # Pass over all shards: a class can straddle two shards, so first collect
    # (shard, row) candidates per class, then sample, then extract.
    shard_rows = {}
    by_class = defaultdict(list)
    tmpdir = tempfile.mkdtemp(dir=args.out, prefix="shards_")
    for s in range(N_SHARDS):
        name = f"test-{s:05d}-of-{N_SHARDS:05d}.parquet"
        url = f"https://huggingface.co/datasets/{REPO}/resolve/main/data/{name}"
        local = os.path.join(tmpdir, name)
        print(f"[{s+1}/{N_SHARDS}] downloading {name}", flush=True)
        urllib.request.urlretrieve(url, local)
        labels = pq.read_table(local, columns=["label"]).column("label").to_pylist()
        shard_rows[s] = local
        for r, lab in enumerate(labels):
            by_class[lab].append((s, r))

    chosen = defaultdict(list)  # shard -> [(row, label)]
    for lab in sorted(by_class):
        picks = rng.sample(by_class[lab], min(args.per_class, len(by_class[lab])))
        for s, r in picks:
            chosen[s].append((r, lab))

    rows_out = []
    for s, local in shard_rows.items():
        if chosen[s]:
            col = pq.read_table(local, columns=["image"]).column("image")
            for r, lab in sorted(chosen[s]):
                rec = col[r].as_py()
                cdir = os.path.join(args.out, "images", CLASSES[lab])
                os.makedirs(cdir, exist_ok=True)
                rel = os.path.join("images", CLASSES[lab], f"s{s:02d}_{r:05d}.tif")
                with open(os.path.join(args.out, rel), "wb") as f:
                    f.write(rec["bytes"])
                rows_out.append((rel, CLASSES[lab]))
        os.remove(local)
    os.rmdir(tmpdir)

    with open(os.path.join(args.out, "labels.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["path", "label"])
        w.writerows(sorted(rows_out))
    print(f"wrote {len(rows_out)} images to {args.out}")


if __name__ == "__main__":
    main()
