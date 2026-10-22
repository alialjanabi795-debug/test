Images: 1000, classes: 5, chance accuracy: 20.00%. Random Forest (min_samples_leaf tuned by inner 3-fold CV), stratified 5-fold CV (mean ± sd over outer folds).

| Observed features | Padding K | Bandwidth overhead | Accuracy | Macro-F1 |
|---|---:|---:|---:|---:|
| JPEG q=85 — total size | none | 0.0% | 30.3 ± 3.7% | 29.7 ± 4.0% |
| JPEG q=85 — total size | 2 | 152.6% | 29.7 ± 2.0% | 17.0 ± 1.2% |
| JPEG q=85 — total size | 4 | 73.4% | 33.7 ± 1.6% | 29.0 ± 1.2% |
| JPEG q=85 — total size | 8 | 34.8% | 33.4 ± 1.9% | 28.0 ± 3.2% |
| PNG lossless — total size | none | 0.0% | 29.9 ± 2.4% | 29.4 ± 2.1% |
| PNG lossless — total size | 2 | 280.5% | 29.6 ± 1.7% | 16.9 ± 1.0% |
| PNG lossless — total size | 4 | 136.0% | 33.2 ± 1.5% | 28.0 ± 2.5% |
| PNG lossless — total size | 8 | 64.8% | 31.5 ± 2.8% | 29.6 ± 2.7% |
| Progressive JPEG — total size | none | 0.0% | 32.5 ± 2.3% | 31.6 ± 2.4% |
| Progressive JPEG — total size | 2 | 158.9% | 29.6 ± 1.6% | 16.9 ± 1.0% |
| Progressive JPEG — total size | 4 | 76.3% | 33.5 ± 1.5% | 28.9 ± 1.3% |
| Progressive JPEG — total size | 8 | 36.1% | 32.7 ± 1.7% | 28.0 ± 2.8% |
| JPEG XL lossless — total size | none | 0.0% | 31.1 ± 3.0% | 29.3 ± 3.1% |
| JPEG XL lossless — total size | 2 | 323.5% | 29.8 ± 1.8% | 17.0 ± 1.0% |
| JPEG XL lossless — total size | 4 | 157.5% | 33.5 ± 1.8% | 29.7 ± 1.6% |
| JPEG XL lossless — total size | 8 | 75.8% | 32.4 ± 2.4% | 29.2 ± 1.7% |
| Progressive JPEG — per-scan sizes (7 features) | none | 0.0% | 40.5 ± 2.4% | 39.8 ± 2.4% |
| Progressive JPEG — per-scan sizes (7 features) | 2 | 162.2% | 34.5 ± 2.5% | 26.3 ± 2.1% |
| Progressive JPEG — per-scan sizes (7 features) | 4 | 78.2% | 38.4 ± 3.7% | 37.3 ± 3.3% |
| Progressive JPEG — per-scan sizes (7 features) | 8 | 36.8% | 43.9 ± 2.4% | 43.2 ± 2.3% |
| Control: image width & height (not on the wire) | none | 0.0% | 36.2 ± 1.5% | 29.6 ± 1.8% |
