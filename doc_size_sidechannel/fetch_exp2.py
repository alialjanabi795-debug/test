"""Build the Exp 2 "realistic document mix": identity documents + RVL-CDIP pages.

Classes (200 images each, seed 0):
  id_card          MIDV-2020 templates: alb_id, esp_id, est_id, fin_id, svk_id (40 each)
  passport         MIDV-2020 templates: aze, grc, lva, srb passports + rus internal (40 each)
  driving_licence  felipebandeira/driverlicense1k (Hugging Face, MIT), first train shard
  letter, form, invoice, scientific_report, email   from an RVL-CDIP sample made by
                   fetch_rvlcdip.py (--rvlcdip points at its output)

MIDV-2020's own hosts (smartengines FTP, l3i-share) were unreachable, so the
1,000 genuine MIDV-2020 templates come from the SIDTD release
(http://datasets.cvc.uab.es/SIDTD/templates.zip, 1.27 GB; forged "fakes" skipped).

Original bytes are written untouched; harmonise later with
size_attack.py --gray --max-side 1000.

Usage:
  python fetch_exp2.py --rvlcdip data/rvlcdip --out data/exp2
"""
import argparse, csv, os, random, urllib.request, zipfile

import pyarrow.parquet as pq

SIDTD_URL = "http://datasets.cvc.uab.es/SIDTD/templates.zip"
DL_URL = ("https://huggingface.co/datasets/felipebandeira/driverlicense1k/resolve/main/"
          "data/train-00000-of-00003-62e4f2419b4a65d1.parquet")
ID_TYPES = ["alb_id", "esp_id", "est_id", "fin_id", "svk_id"]
PASSPORT_TYPES = ["aze_passport", "grc_passport", "lva_passport", "srb_passport",
                  "rus_internalpassport"]
RVL_CLASSES = ["letter", "form", "invoice", "scientific_report", "email"]


def fetch(url, path):
    if not os.path.exists(path):
        print("downloading", url, flush=True)
        urllib.request.urlretrieve(url, path + ".part")
        os.rename(path + ".part", path)
    return path


def write(out, label, name, data, rows):
    rel = os.path.join("images", label, name)
    os.makedirs(os.path.join(out, "images", label), exist_ok=True)
    with open(os.path.join(out, rel), "wb") as f:
        f.write(data)
    rows.append((rel, label))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rvlcdip", required=True, help="output dir of fetch_rvlcdip.py")
    ap.add_argument("--out", required=True)
    ap.add_argument("--per-class", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    n = args.per_class
    dl_dir = os.path.join(args.out, "downloads")
    os.makedirs(dl_dir, exist_ok=True)
    rows = []

    # MIDV-2020 templates (via SIDTD): n/5 per country type.
    z = zipfile.ZipFile(fetch(SIDTD_URL, os.path.join(dl_dir, "sidtd_templates.zip")))
    reals = sorted(m for m in z.namelist()
                   if m.startswith("templates/Images/reals/") and m.endswith(".jpg"))
    for label, types in (("id_card", ID_TYPES), ("passport", PASSPORT_TYPES)):
        for t in types:
            pool = [m for m in reals if os.path.basename(m).rsplit("_", 1)[0] == t]
            for m in rng.sample(pool, n // len(types)):
                write(args.out, label, os.path.basename(m), z.read(m), rows)

    # Driving licences.
    t = pq.read_table(fetch(DL_URL, os.path.join(dl_dir, "driverlicense1k_train0.parquet")),
                      columns=["image"])
    col = t.column("image")
    for i in sorted(rng.sample(range(t.num_rows), n)):
        rec = col[i].as_py()
        write(args.out, "driving_licence", f"dl_{i:04d}.png", rec["bytes"], rows)

    # RVL-CDIP classes from the existing sample.
    with open(os.path.join(args.rvlcdip, "labels.csv"), newline="") as f:
        rvl = list(csv.DictReader(f))
    for label in RVL_CLASSES:
        pool = sorted(r["path"] for r in rvl if r["label"] == label)
        for p in rng.sample(pool, n):
            with open(os.path.join(args.rvlcdip, p), "rb") as f:
                write(args.out, label, os.path.basename(p), f.read(), rows)

    with open(os.path.join(args.out, "labels.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["path", "label"])
        w.writerows(sorted(rows))
    print(f"wrote {len(rows)} images to {args.out} (downloads cached in {dl_dir})")


if __name__ == "__main__":
    main()
