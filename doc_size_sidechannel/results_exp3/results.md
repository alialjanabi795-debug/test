Images: 800 (16 classes, chance 6.25%). Model: `microsoft/dit-base-finetuned-rvlcdip`. Both formats JPEG q=85; sequential is truncated at the progressive scan's byte count.

| Bytes received | Progressive: % of file | Progressive acc / macro-F1 | Sequential: % of file | Sequential acc / macro-F1 |
|---|---:|---:|---:|---:|
| end of scan 1 (4.6 KB) | 5.6% | 87.2% / 87.2% | 4.8% | 14.2% / 9.3% |
| end of scan 2 (15.8 KB) | 16.5% | 91.4% / 91.4% | 14.3% | 45.9% / 45.4% |
| end of scan 3 (47.6 KB) | 46.2% | 91.5% / 91.5% | 40.4% | 80.1% / 80.1% |
| end of scan 4 (70.4 KB) | 67.5% | 91.5% / 91.5% | 59.0% | 85.2% / 85.2% |
| end of scan 5 (72.8 KB) | 71.8% | 91.6% / 91.6% | 62.6% | 86.4% / 86.4% |
| end of scan 6 (102.7 KB) | 100.0% | 91.4% / 91.4% | 87.3% | 89.9% / 89.9% |
| full sequential file (115.6 KB) | — | — | 100.0% | 91.4% / 91.4% |

| Format | Full-file accuracy | % of bytes to reach 90% of it: first checkpoint (interpolated) |
|---|---:|---:|
| progressive | 91.4% | 5.6% (5.6%) |
| sequential | 91.4% | 59.0% (48.1%) |
