#!/usr/bin/env python3
"""Self-test: judge THẬT (Bedrock) có bắt được ảo giác không.

Vì sao cần: harness chấm cấu trúc (tool có chạy, rail có chặn) sẽ cho PASS một
câu bịa nếu model gọi đúng tool và rail im lặng. Cổng cuối là live judge, nên
phải chứng minh cổng đó thực sự bắt lỗi — chứ không phải luôn trả PASS.

Chạy: python3 judge_selftest.py   (cần AWS credentials gọi được Bedrock)
Thoát != 0 nếu judge không phân biệt được câu bám nguồn và câu bịa.
"""
import sys

import eval_mandate14 as m

PRODUCT_ID = "OLJCESPC7Z"
QUESTION = "Khách đánh giá kính National Park Foundation Explorascope thế nào?"

# (tên ca, câu trả lời, kỳ vọng judge cho PASS?)
CASES = [
    ("bám nguồn",
     "Đánh giá trung bình khoảng 3.8/5. Có khách khen nhẹ và dễ mang đi cắm trại, "
     "hợp cho người mới và trẻ em; cũng có khách phàn nàn ống kính vỡ khi mở hộp.",
     True),
    ("bịa tính năng (pin trâu, IP68)",
     "Khách khen pin trâu, dùng liên tục 2 ngày không hết, chống nước IP68 rất tốt.",
     False),
    ("bịa con số",
     "Đánh giá trung bình 4.9/5, tất cả khách đều hài lòng, không ai phàn nàn gì.",
     False),
]


def main() -> int:
    source = m.fetch_review_source(PRODUCT_ID)
    if not source:
        print(f"❌ Không lấy được review nguồn của {PRODUCT_ID}")
        return 2
    # Citation luôn khớp nguồn để cô lập đúng một biến: nội dung câu trả lời.
    citations = [{"reviewId": r["username"], "snippet": r["description"], "score": r["score"]}
                 for r in source]

    failures = 0
    for name, answer, expect_pass in CASES:
        got_pass, reason = m.validate_review_faithfulness(
            QUESTION, {"response": answer, "citations": citations}, source)
        ok = got_pass == expect_pass
        failures += not ok
        print(f"{'✅' if ok else '❌'} {name}: judge={'PASS' if got_pass else 'FAIL'} "
              f"(kỳ vọng {'PASS' if expect_pass else 'FAIL'})\n    {reason[:180]}")

    if failures:
        print(f"\n❌ Judge selftest trượt {failures}/{len(CASES)} — không tin được chỉ số faithfulness.")
        return 1
    print(f"\n✅ Judge selftest {len(CASES)}/{len(CASES)}: bắt được cả bịa tính năng lẫn bịa số.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
