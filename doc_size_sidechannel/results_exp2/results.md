Images: 1600, classes: 8, chance accuracy: 12.50%. Random Forest (min_samples_leaf tuned by inner 3-fold CV), stratified 5-fold CV (mean ± sd over outer folds).

| Observed features | Padding K | Bandwidth overhead | Accuracy | Macro-F1 |
|---|---:|---:|---:|---:|
| JPEG q=85 — total size | none | 0.0% | 43.4 ± 2.2% | 37.6 ± 1.5% |
| JPEG q=85 — total size | 2 | 119.4% | 23.5 ± 0.8% | 9.4 ± 0.3% |
| JPEG q=85 — total size | 4 | 57.5% | 34.2 ± 2.1% | 22.8 ± 1.4% |
| JPEG q=85 — total size | 8 | 29.0% | 36.1 ± 3.7% | 30.7 ± 2.6% |
| PNG lossless — total size | none | 0.0% | 51.7 ± 2.3% | 50.8 ± 2.1% |
| PNG lossless — total size | 2 | 71.0% | 24.4 ± 0.3% | 9.8 ± 0.1% |
| PNG lossless — total size | 4 | 37.4% | 39.2 ± 1.7% | 26.2 ± 1.2% |
| PNG lossless — total size | 8 | 20.8% | 47.7 ± 2.5% | 46.9 ± 1.9% |
| Progressive JPEG — total size | none | 0.0% | 43.4 ± 3.1% | 38.8 ± 2.8% |
| Progressive JPEG — total size | 2 | 118.8% | 24.1 ± 0.3% | 9.7 ± 0.1% |
| Progressive JPEG — total size | 4 | 56.9% | 35.2 ± 1.6% | 23.5 ± 1.0% |
| Progressive JPEG — total size | 8 | 28.8% | 36.7 ± 3.7% | 32.3 ± 2.9% |
| JPEG XL lossless — total size | none | 0.0% | 52.4 ± 0.7% | 51.5 ± 0.6% |
| JPEG XL lossless — total size | 2 | 93.4% | 24.4 ± 0.3% | 9.8 ± 0.1% |
| JPEG XL lossless — total size | 4 | 45.7% | 39.6 ± 1.7% | 26.4 ± 1.2% |
| JPEG XL lossless — total size | 8 | 23.6% | 47.4 ± 3.6% | 47.0 ± 3.4% |
| Progressive JPEG — per-scan sizes (7 features) | none | 0.0% | 64.6 ± 1.2% | 64.3 ± 1.2% |
| Progressive JPEG — per-scan sizes (7 features) | 2 | 119.1% | 34.9 ± 1.9% | 27.3 ± 1.9% |
| Progressive JPEG — per-scan sizes (7 features) | 4 | 57.2% | 61.2 ± 2.4% | 59.6 ± 2.4% |
| Progressive JPEG — per-scan sizes (7 features) | 8 | 28.2% | 62.4 ± 1.8% | 61.5 ± 2.3% |
| Control: image width & height (not on the wire) | none | 0.0% | 60.6 ± 1.3% | 56.5 ± 1.7% |
