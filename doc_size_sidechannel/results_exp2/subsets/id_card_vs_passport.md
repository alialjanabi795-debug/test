Images: 400, classes: 2, chance accuracy: 50.00%. Random Forest (min_samples_leaf tuned by inner 3-fold CV), stratified 5-fold CV (mean ± sd over outer folds).

| Observed features | Padding K | Bandwidth overhead | Accuracy | Macro-F1 |
|---|---:|---:|---:|---:|
| JPEG q=85 — total size | none | 0.0% | 93.8 ± 2.9% | 93.7 ± 2.9% |
| JPEG q=85 — total size | 2 | 19.5% | 62.0 ± 6.5% | 61.9 ± 6.5% |
| JPEG q=85 — total size | 4 | 10.4% | 62.0 ± 6.5% | 61.9 ± 6.5% |
| JPEG q=85 — total size | 8 | 4.9% | 74.8 ± 4.6% | 74.5 ± 4.8% |
| PNG lossless — total size | none | 0.0% | 95.2 ± 2.9% | 95.2 ± 2.9% |
| PNG lossless — total size | 2 | 14.7% | 80.0 ± 5.4% | 80.0 ± 5.4% |
| PNG lossless — total size | 4 | 8.6% | 80.0 ± 5.4% | 80.0 ± 5.4% |
| PNG lossless — total size | 8 | 5.0% | 78.8 ± 5.5% | 78.5 ± 5.6% |
| Progressive JPEG — total size | none | 0.0% | 95.0 ± 3.1% | 95.0 ± 3.1% |
| Progressive JPEG — total size | 2 | 19.8% | 61.0 ± 6.3% | 60.9 ± 6.3% |
| Progressive JPEG — total size | 4 | 10.6% | 61.0 ± 6.3% | 60.9 ± 6.3% |
| Progressive JPEG — total size | 8 | 5.3% | 78.0 ± 4.0% | 77.9 ± 4.0% |
| JPEG XL lossless — total size | none | 0.0% | 95.5 ± 1.0% | 95.5 ± 1.0% |
| JPEG XL lossless — total size | 2 | 17.0% | 80.0 ± 5.4% | 80.0 ± 5.4% |
| JPEG XL lossless — total size | 4 | 9.0% | 80.0 ± 5.4% | 80.0 ± 5.4% |
| JPEG XL lossless — total size | 8 | 5.9% | 84.5 ± 2.0% | 84.5 ± 2.0% |
| Progressive JPEG — per-scan sizes (7 features) | none | 0.0% | 100.0 ± 0.0% | 100.0 ± 0.0% |
| Progressive JPEG — per-scan sizes (7 features) | 2 | 21.3% | 100.0 ± 0.0% | 100.0 ± 0.0% |
| Progressive JPEG — per-scan sizes (7 features) | 4 | 9.8% | 100.0 ± 0.0% | 100.0 ± 0.0% |
| Progressive JPEG — per-scan sizes (7 features) | 8 | 5.4% | 100.0 ± 0.0% | 100.0 ± 0.0% |
| Control: image width & height (not on the wire) | none | 0.0% | 100.0 ± 0.0% | 100.0 ± 0.0% |
