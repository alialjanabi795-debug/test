Images: 1600, classes: 8, chance accuracy: 12.50%. Random Forest (min_samples_leaf tuned by inner 3-fold CV), stratified 5-fold CV (mean ± sd over outer folds).

| Observed features | Padding K | Bandwidth overhead | Accuracy | Macro-F1 |
|---|---:|---:|---:|---:|
| JPEG q=85 — total size | none | 0.0% | 50.0 ± 2.5% | 47.9 ± 2.3% |
| JPEG q=85 — total size | 2 | 200.9% | 24.1 ± 0.3% | 9.7 ± 0.1% |
| JPEG q=85 — total size | 4 | 82.6% | 38.6 ± 1.4% | 25.8 ± 1.0% |
| JPEG q=85 — total size | 8 | 28.5% | 40.9 ± 2.7% | 38.4 ± 1.9% |
| PNG lossless — total size | none | 0.0% | 50.8 ± 2.3% | 50.3 ± 2.2% |
| PNG lossless — total size | 2 | 219.3% | 24.4 ± 0.3% | 9.8 ± 0.1% |
| PNG lossless — total size | 4 | 92.8% | 36.4 ± 2.6% | 24.3 ± 1.9% |
| PNG lossless — total size | 8 | 31.3% | 39.9 ± 1.8% | 34.9 ± 1.6% |
| Progressive JPEG — total size | none | 0.0% | 50.2 ± 1.9% | 48.4 ± 2.0% |
| Progressive JPEG — total size | 2 | 202.4% | 24.1 ± 0.3% | 9.7 ± 0.1% |
| Progressive JPEG — total size | 4 | 83.4% | 38.4 ± 1.5% | 25.6 ± 1.1% |
| Progressive JPEG — total size | 8 | 29.0% | 41.3 ± 2.5% | 38.7 ± 1.6% |
| JPEG XL lossless — total size | none | 0.0% | 54.2 ± 1.6% | 53.7 ± 1.4% |
| JPEG XL lossless — total size | 2 | 252.4% | 24.4 ± 0.3% | 9.8 ± 0.1% |
| JPEG XL lossless — total size | 4 | 109.6% | 38.6 ± 2.4% | 25.8 ± 1.6% |
| JPEG XL lossless — total size | 8 | 41.0% | 42.1 ± 2.0% | 36.6 ± 1.7% |
| Progressive JPEG — per-scan sizes (11 features) | none | 0.0% | 63.3 ± 2.4% | 62.9 ± 2.3% |
| Progressive JPEG — per-scan sizes (11 features) | 2 | 216.4% | 37.1 ± 1.2% | 32.3 ± 1.2% |
| Progressive JPEG — per-scan sizes (11 features) | 4 | 103.1% | 58.6 ± 1.3% | 57.3 ± 1.4% |
| Progressive JPEG — per-scan sizes (11 features) | 8 | 37.7% | 61.9 ± 2.0% | 61.0 ± 2.2% |
| Control: image width & height (not on the wire) | none | 0.0% | 60.5 ± 1.2% | 56.5 ± 1.6% |
