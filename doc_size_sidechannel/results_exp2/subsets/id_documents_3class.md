Images: 600, classes: 3, chance accuracy: 33.33%. Random Forest (min_samples_leaf tuned by inner 3-fold CV), stratified 5-fold CV (mean ± sd over outer folds).

| Observed features | Padding K | Bandwidth overhead | Accuracy | Macro-F1 |
|---|---:|---:|---:|---:|
| JPEG q=85 — total size | none | 0.0% | 76.5 ± 4.9% | 76.6 ± 4.9% |
| JPEG q=85 — total size | 2 | 21.3% | 53.2 ± 1.5% | 42.6 ± 1.2% |
| JPEG q=85 — total size | 4 | 11.6% | 53.3 ± 3.0% | 50.0 ± 4.6% |
| JPEG q=85 — total size | 8 | 6.1% | 63.0 ± 3.6% | 62.6 ± 3.7% |
| PNG lossless — total size | none | 0.0% | 86.5 ± 2.3% | 86.3 ± 2.5% |
| PNG lossless — total size | 2 | 20.4% | 62.0 ± 1.5% | 49.7 ± 1.2% |
| PNG lossless — total size | 4 | 10.5% | 64.3 ± 3.7% | 62.2 ± 4.3% |
| PNG lossless — total size | 8 | 4.8% | 69.3 ± 3.3% | 68.3 ± 3.7% |
| Progressive JPEG — total size | none | 0.0% | 77.5 ± 3.4% | 77.5 ± 3.3% |
| Progressive JPEG — total size | 2 | 22.5% | 53.5 ± 1.0% | 42.9 ± 0.8% |
| Progressive JPEG — total size | 4 | 12.4% | 55.3 ± 4.0% | 53.9 ± 4.6% |
| Progressive JPEG — total size | 8 | 6.2% | 59.2 ± 2.6% | 56.6 ± 5.0% |
| JPEG XL lossless — total size | none | 0.0% | 92.5 ± 1.9% | 92.4 ± 2.0% |
| JPEG XL lossless — total size | 2 | 26.0% | 60.2 ± 0.8% | 48.2 ± 0.7% |
| JPEG XL lossless — total size | 4 | 13.1% | 68.2 ± 3.4% | 66.4 ± 3.9% |
| JPEG XL lossless — total size | 8 | 6.6% | 75.2 ± 3.5% | 73.1 ± 4.3% |
| Progressive JPEG — per-scan sizes (7 features) | none | 0.0% | 99.8 ± 0.3% | 99.8 ± 0.3% |
| Progressive JPEG — per-scan sizes (7 features) | 2 | 24.6% | 88.3 ± 1.5% | 88.4 ± 1.4% |
| Progressive JPEG — per-scan sizes (7 features) | 4 | 12.3% | 99.5 ± 0.7% | 99.5 ± 0.7% |
| Progressive JPEG — per-scan sizes (7 features) | 8 | 6.7% | 99.8 ± 0.3% | 99.8 ± 0.3% |
| Control: image width & height (not on the wire) | none | 0.0% | 100.0 ± 0.0% | 100.0 ± 0.0% |
