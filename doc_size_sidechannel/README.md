# Document-type leakage from compressed image size

Feasibility check: can a network observer, who sees only the byte size of an
image transfer through TLS, tell what *kind* of document the image shows?

**Short answer: yes, but the signal from total size alone is modest.**
On 16 RVL-CDIP classes (chance 6.25%), a single total-size number gives
**15–17% accuracy** (about 2.5× chance). If the observer can see where each
progressive-JPEG scan ends, accuracy rises to **32%** (5× chance).
Bucket padding is expensive and only partly effective. With K=8 buckets the
per-scan attack still reaches 25.5% at 34% bandwidth overhead. For total
size, K=8 lowers macro-F1 (12.8% → 8.8%) but not accuracy.

![attack accuracy vs bandwidth overhead](results/attack_vs_overhead.png)

## Results (RVL-CDIP, 300 images × 16 classes = 4,800)

Random Forest (200 trees; `min_samples_leaf` ∈ {1, 5, 20, 50} picked by an
inner 3-fold CV), stratified 5-fold CV, mean ± sd over the outer folds.
Chance = 6.25%.

| Observed features | Padding K | Bandwidth overhead | Accuracy | Macro-F1 |
|---|---:|---:|---:|---:|
| JPEG q=85 — total size | none | 0.0% | 15.2 ± 0.4% | 12.8 ± 0.4% |
| JPEG q=85 — total size | 8 | 31.5% | 15.8 ± 0.5% | 8.8 ± 0.9% |
| JPEG q=85 — total size | 4 | 67.0% | 14.7 ± 0.5% | 5.9 ± 0.2% |
| JPEG q=85 — total size | 2 | 139.9% | 11.2 ± 0.2% | 2.5 ± 0.1% |
| PNG lossless — total size | none | 0.0% | 15.4 ± 1.4% | 13.6 ± 1.2% |
| PNG lossless — total size | 8 | 60.6% | 15.3 ± 0.4% | 8.7 ± 0.4% |
| PNG lossless — total size | 4 | 128.3% | 14.2 ± 0.6% | 5.7 ± 0.3% |
| PNG lossless — total size | 2 | 267.7% | 11.4 ± 0.2% | 2.5 ± 0.0% |
| Progressive JPEG — total size | none | 0.0% | 15.6 ± 1.3% | 13.3 ± 1.0% |
| Progressive JPEG — total size | 8 | 32.0% | 15.4 ± 0.4% | 8.4 ± 0.6% |
| Progressive JPEG — total size | 4 | 68.1% | 14.6 ± 0.5% | 5.8 ± 0.2% |
| Progressive JPEG — total size | 2 | 142.4% | 11.2 ± 0.2% | 2.5 ± 0.0% |
| JPEG XL lossless — total size | none | 0.0% | 16.7 ± 1.6% | 14.2 ± 1.6% |
| JPEG XL lossless — total size | 8 | 65.7% | 15.7 ± 0.4% | 8.8 ± 0.3% |
| JPEG XL lossless — total size | 4 | 138.9% | 14.9 ± 0.6% | 6.0 ± 0.2% |
| JPEG XL lossless — total size | 2 | 289.5% | 11.3 ± 0.2% | 2.5 ± 0.0% |
| **Progressive JPEG — per-scan sizes (7 features)** | none | 0.0% | **31.9 ± 1.1%** | **30.7 ± 1.0%** |
| Progressive JPEG — per-scan sizes | 8 | 34.0% | 25.5 ± 1.3% | 23.9 ± 1.2% |
| Progressive JPEG — per-scan sizes | 4 | 72.1% | 22.5 ± 1.5% | 19.9 ± 1.2% |
| Progressive JPEG — per-scan sizes | 2 | 150.5% | 13.4 ± 0.4% | 6.3 ± 0.4% |
| Control: image width & height (not on the wire) | none | — | 14.2 ± 0.8% | 9.8 ± 1.0% |

Machine-readable: `results/results.csv`. Per-image sizes: `results/sizes.csv`.

### What the numbers say

* **All four encoders leak about the same amount** through total size: 15–17%.
  Lossless JPEG XL is slightly ahead, and is also the most expensive to pad.
* **Progressive scan boundaries double the leak.** The 7 numbers are the
  header plus 6 scans. They split the image's energy into DC, low-frequency
  AC and high-frequency AC. That separates text-dense pages from photo and
  graphics pages much better than one total does.
* **The leak is page content, not page geometry.** Image dimensions are
  class-correlated in RVL-CDIP: the width/height control alone gets 14%.
  But size divided by pixel count (bytes/pixel) gives the same accuracy as
  raw size: 15.5% for JPEG and 16.9% for JPEG XL. Combining size with W,H
  gives 23–24%, so the two signals are complementary.
  Reproduce with `python check_dimensions.py results/sizes.csv`.
* **Padding barely moves *accuracy* for total size, but it does cut macro-F1.**
  With K buckets the best attacker can do is guess the most common class in
  each bucket. That keeps accuracy near the unpadded level but collapses
  per-class recall. Read macro-F1 for the defense rows. At K=2, accuracy is
  11% while macro-F1 is 2.5%: the attacker only ever guesses two classes.
* **Padding is costly.** Buckets are equal-frequency quantiles, with the top
  edge at the largest image, so a heavy tail makes the top bucket expensive.
  Padding *everything* to the maximum (K=1, which is guaranteed chance) costs
  290% (JPEG), 295% (progressive JPEG), 553% (PNG) and 597% (JPEG XL).
* **The per-scan attack needs per-scan padding.** If you pad only the total,
  the scan boundaries still leak everything in the first per-scan row. The
  defense rows above pad *each* scan independently.

## Reproduce

```bash
pip install -r requirements.txt

# 1. 300 random images per class from the RVL-CDIP test split (downloads about
#    4.6 GB of parquet one shard at a time, keeps about 560 MB of TIFFs)
python fetch_rvlcdip.py --out data/rvlcdip --per-class 300 --seed 0

# 2. Encode, attack, defend, and write table + figure (about 6 min encode +
#    4 min CV on 4 cores)
python size_attack.py --labels data/rvlcdip/labels.csv --out results/

# Re-run only the attacks/defenses from cached sizes:
python size_attack.py --sizes results/sizes.csv --out results/
```

### On your own images

Either one sub-folder per class:

```bash
python size_attack.py --images /srv/docs --out my_results/        # /srv/docs/<label>/<file>
```

or a CSV with `path,label` (paths relative to the CSV):

```bash
python size_attack.py --labels /srv/docs/labels.csv --out my_results/ --k 2 4 8 16
```

Options: `--k` bucket counts, `--buckets quantile|log` edge placement,
`--trees`, `--seed`, `--workers`. JPEG XL is skipped automatically if
`imagecodecs` lacks libjxl. Mixed colour/grey inputs work. RGB progressive
JPEGs have 10 scans instead of 6, and missing scans are zero-filled.

## Method details and caveats

* **Data.** [`chainyo/rvl-cdip`](https://huggingface.co/datasets/chainyo/rvl-cdip)
  is a parquet copy of RVL-CDIP: grayscale scans, longest side 1000 px.
  The sample is 300 per class from the 40k test split, drawn with seed 0.
  The original TIFF bytes are decoded and re-encoded, so the source
  compression doesn't matter.
* **Encoders.**
  * JPEG and progressive JPEG: Pillow / libjpeg-turbo, q=85, default
    progressive scan script. Progressive mode uses optimised Huffman tables.
  * PNG: Pillow default (zlib level 6, no `optimize`).
  * JPEG XL: libjxl 0.12 via `imagecodecs`, lossless, effort 7.
* **Scan sizes.** The progressive file is split at each SOS marker.
  `pjpeg_header` is everything before the first scan. Each `pjpeg_scanN`
  runs from its SOS to the next SOS, so it includes the small DHT segment
  for the next scan. The pieces sum exactly to the file size. This assumes
  an observer can split scans in time, for example from a progressive
  renderer's request or flush pattern. That is a stronger threat model than
  total size.
* **Wire vs file size.** TLS records, HTTP headers and compression framing
  add a near-constant or monotone overhead. We use file size as a proxy for
  what a passive observer sees. Real traffic also has multiplexing noise,
  which would lower these numbers.
* **Buckets.** The defender fits the bucket edges on the whole set, not per
  fold; they are a defense parameter, not attacker training. Every size is
  padded *up* to the next edge. Overhead = Σ padded / Σ original − 1.
* **Classifier tuning matters.** An untuned forest (`min_samples_leaf=1`)
  overfits a single continuous feature. It scored only 10–12% on total
  size, which is *below* its own padded scores. The inner CV over
  `min_samples_leaf` fixes this.
* **Scope.** This is one dataset of 1990s tobacco-litigation scans.
  Class-size distributions on another corpus will differ, so rerun on your
  own data before drawing conclusions.
