Images: 4800, classes: 16, chance accuracy: 6.25%. Random Forest (min_samples_leaf tuned by inner 3-fold CV), stratified 5-fold CV (mean ± sd over outer folds).

| Observed features | Padding K | Bandwidth overhead | Accuracy | Macro-F1 |
|---|---:|---:|---:|---:|
| JPEG q=85 — total size | none | 0.0% | 15.2 ± 0.4% | 12.8 ± 0.4% |
| JPEG q=85 — total size | 2 | 139.9% | 11.2 ± 0.2% | 2.5 ± 0.1% |
| JPEG q=85 — total size | 4 | 67.0% | 14.7 ± 0.5% | 5.9 ± 0.2% |
| JPEG q=85 — total size | 8 | 31.5% | 15.8 ± 0.5% | 8.8 ± 0.9% |
| PNG lossless — total size | none | 0.0% | 15.4 ± 1.4% | 13.6 ± 1.2% |
| PNG lossless — total size | 2 | 267.7% | 11.4 ± 0.2% | 2.5 ± 0.0% |
| PNG lossless — total size | 4 | 128.3% | 14.2 ± 0.6% | 5.7 ± 0.3% |
| PNG lossless — total size | 8 | 60.6% | 15.3 ± 0.4% | 8.7 ± 0.4% |
| Progressive JPEG — total size | none | 0.0% | 15.6 ± 1.3% | 13.3 ± 1.0% |
| Progressive JPEG — total size | 2 | 142.4% | 11.2 ± 0.2% | 2.5 ± 0.0% |
| Progressive JPEG — total size | 4 | 68.1% | 14.6 ± 0.5% | 5.8 ± 0.2% |
| Progressive JPEG — total size | 8 | 32.0% | 15.4 ± 0.4% | 8.4 ± 0.6% |
| JPEG XL lossless — total size | none | 0.0% | 16.7 ± 1.6% | 14.2 ± 1.6% |
| JPEG XL lossless — total size | 2 | 289.5% | 11.3 ± 0.2% | 2.5 ± 0.0% |
| JPEG XL lossless — total size | 4 | 138.9% | 14.9 ± 0.6% | 6.0 ± 0.2% |
| JPEG XL lossless — total size | 8 | 65.7% | 15.7 ± 0.4% | 8.8 ± 0.3% |
| Progressive JPEG — per-scan sizes (7 features) | none | 0.0% | 31.9 ± 1.1% | 30.7 ± 1.0% |
| Progressive JPEG — per-scan sizes (7 features) | 2 | 150.5% | 13.4 ± 0.4% | 6.3 ± 0.4% |
| Progressive JPEG — per-scan sizes (7 features) | 4 | 72.1% | 22.5 ± 1.5% | 19.9 ± 1.2% |
| Progressive JPEG — per-scan sizes (7 features) | 8 | 34.0% | 25.5 ± 1.3% | 23.9 ± 1.2% |
| Control: image width & height (not on the wire) | none | 0.0% | 14.2 ± 0.8% | 9.8 ± 1.0% |
