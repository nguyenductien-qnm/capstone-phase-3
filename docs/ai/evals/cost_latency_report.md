# Before/After Cost & Latency Report (MANDATE-14)

> Sinh tự động bởi `cost_before_after.py`. Mọi số liệu dưới đây đo được từ evidence JSON,
> áp cùng một bảng giá Bedrock on-demand us-east-1 (tra 2026-07-26).
> Chạy `python3 cost_before_after.py` để cập nhật.

## Bảng giá áp dụng
| Model | Input ($/1M) | Output ($/1M) |
|---|---|---|
| Nova Pro | 0.80 | 3.20 |
| Nova Lite | 0.06 | 0.24 |
| Nova Micro | 0.035 | 0.14 |
| Titan Embed v2 | 0.02 | 0.00 |

## So sánh theo run
*(Chạy `python3 cost_before_after.py` để sinh bảng thật)*

| Run | Ngày | Cases | Pass | p50 (s) | p95 (s) | Token In | Token Out | Embed Token | USD/req |
|---|---|---|---|---|---|---|---|---|---|
| 20260724_221123 | 20260724_221123 | 6 | 0.0% | 0.00 | 0.00 | 19474 | 575 | 0 | 0.002903 |
| 20260724_222006 | 20260724_222006 | 6 | 0.0% | 0.00 | 0.00 | 20101 | 567 | 0 | 0.002983 |
| 20260724_222232 | 20260724_222232 | 6 | 0.0% | 0.00 | 0.00 | 20112 | 641 | 0 | 0.003023 |
| 20260724_222535 | 20260724_222535 | 6 | 0.0% | 0.00 | 0.00 | 20845 | 521 | 0 | 0.003057 |
| 20260724_222828 | 20260724_222828 | 6 | 0.0% | 0.00 | 0.00 | 21544 | 506 | 0 | 0.003142 |
| 20260724_223053 | 20260724_223053 | 6 | 0.0% | 0.00 | 0.00 | 18500 | 451 | 0 | 0.002707 |
| 20260724_223458 | 20260724_223458 | 4 | 0.0% | 0.00 | 0.00 | 18857 | 528 | 0 | 0.004194 |
| 20260724_225409 | 20260724_225409 | 12 | 0.0% | 0.00 | 0.00 | 43088 | 1257 | 0 | 0.003208 |
| 20260724_230345 | 20260724_230345 | 12 | 0.0% | 0.00 | 0.00 | 53535 | 1597 | 0 | 0.003995 |
| 20260725_233530 | 20260725_233530 | 21 | 38.1% | 2.11 | 4.83 | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) |
| 20260725_233709 | 20260725_233709 | 21 | 38.1% | 2.13 | 4.81 | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) |
| 20260726_003438 | 20260726_003438 | 39 | 64.1% | 0.01 | 0.14 | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) |
| 20260726_003646 | 20260726_003646 | 39 | 82.1% | 2.01 | 16.57 | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) |
| 20260726_003940 | 20260726_003940 | 18 | 55.6% | 1.97 | 17.21 | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) |
| 20260726_004210 | 20260726_004210 | 7 | 71.4% | 2.14 | 21.82 | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) |
| 20260726_004257 | 20260726_004257 | 18 | 61.1% | 2.22 | 19.82 | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) |
| 20260726_004458 | 20260726_004458 | 18 | 66.7% | 2.09 | 16.04 | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) |
| 20260726_004632 | 20260726_004632 | 39 | 0.0% | 0.12 | 0.19 | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) |
| 20260726_010925 | 20260726_010925 | 39 | 79.5% | 2.10 | 22.48 | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) |
| 20260726_073357 | 20260726_073357 | 35 | 100.0% | 0.77 | 16.79 | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) |
| 20260726_074226 | 20260726_074226 | 36 | 97.2% | 1.10 | 17.16 | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) |
| 20260726_075204 | 20260726_075204 | 36 | 97.2% | 0.91 | 19.72 | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) |
| 20260726_080114 | 20260726_080114 | 4 | 100.0% | 0.01 | 0.48 | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) |
| 20260726_080227 | 20260726_080227 | 36 | 100.0% | 0.99 | 17.79 | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) |
| 20260726_081144 | 20260726_081144 | 36 | 100.0% | 1.02 | 20.06 | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) |
| 20260726_082223 | 20260726_082223 | 16 | 100.0% | 2.76 | 23.86 | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) |
| 20260726_082808 | 20260726_082808 | 36 | 100.0% | 1.24 | 21.98 | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) |
| 20260726_083754 | 20260726_083754 | 24 | 100.0% | 2.81 | 22.62 | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) |
| 20260726_084504 | 20260726_084504 | 36 | 100.0% | 1.43 | 19.26 | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) |
| 20260726_112254 | 20260726_112254 | 36 | 80.6% | 1.87 | 30.01 | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) | n/a (harness cũ không lưu span) |
| 20260726_130630 | 20260726_130630 | 41 | 92.7% | 2.14 | 15.37 | 219478 | 7119 | 92 | 0.001160 |
| 20260726_131733 | 20260726_131733 | 24 | 100.0% | 2.49 | 14.83 | 140067 | 3999 | 35 | 0.001560 |
| 20260726_165145 | 20260726_165145 | 41 | 80.5% | 2.27 | 30.00 | 145637 | 5295 | 55 | 0.000719 |
| 20260726_170614 | 20260726_170614 | 41 | 95.1% | 2.36 | 18.04 | 225093 | 7173 | 91 | 0.002019 |

## Nguyên nhân thay đổi
- Sửa cách chấm điểm (scoring rubric chuẩn hóa)
- Đưa Titan Embed vào sổ chi phí (trước đó span `bedrock_embed` chưa được đo)
- Sửa timeout frontend-proxy (giảm 504)
- **Không** quy công cho "dùng Nova Lite" — model router đã có từ trước
