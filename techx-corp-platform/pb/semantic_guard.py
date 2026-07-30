"""Rule-guard cho L2 semantic cache — chặn "trả sai im lặng".

Vì sao cần: sweep đo thật ngày 27/07 (`docs/ai/evals/param_sweep_m23.md`) cho thấy
embedding Titan v2 xếp cặp *khác nghĩa* ("pin bền không" ↔ "pin KHÔNG bền phải
không") gần nhau hơn cả cặp *cùng ý*. Hai nhóm chồng lấn hoàn toàn nên KHÔNG tồn
tại ngưỡng cosine nào vừa bắt được paraphrase vừa không trả sai. Ngưỡng một mình
là không đủ; phải có luật chặn trên các token quyết định nghĩa.

Luật: hai câu chỉ được coi là cùng một câu hỏi khi trùng nhau ở cả bốn mặt
    1. phủ định    — "không / chẳng / chưa / not / no"
    2. so sánh giá — "dưới / trên / hơn / under / over / above / below"
    3. con số      — 200 USD ≠ 500 USD
    4. tên riêng   — token viết hoa / mã sản phẩm xuất hiện ở câu này mà không ở câu kia

Guard chỉ trả lời "hai câu này có phải một không". Câu trả lời còn đúng hay không
là việc của `scope_key` (đã ghim content fingerprint).
"""
import re

_NEGATION = re.compile(r"\b(không|khong|chẳng|chang|chưa|chua|not|no|isn't|doesn't)\b", re.I)
_COMPARATOR = {
    "duoi": re.compile(r"(dưới|duoi|under|below|less than|rẻ hơn|re hon|<)", re.I),
    "tren": re.compile(r"(trên|tren|over|above|more than|hơn|hon|đắt hơn|dat hon|>)", re.I),
}
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
# Tên riêng/mã sản phẩm: token có chữ hoa giữa câu, hoặc mã kiểu OLJCESPC7Z.
_PROPER = re.compile(r"\b(?:[A-Z][a-zA-Z]{2,}|[A-Z0-9]{8,})\b")
_STOP_PROPER = {"Ban", "Toi", "Minh", "Cho", "Co", "Xin", "Hay", "San", "Gia"}


def _has_negation(text: str) -> bool:
    return bool(_NEGATION.search(text or ""))


def _comparators(text: str) -> set:
    return {k for k, rx in _COMPARATOR.items() if rx.search(text or "")}


def _numbers(text: str) -> set:
    return {n.replace(",", ".").rstrip("0").rstrip(".") or "0" for n in _NUMBER.findall(text or "")}


def _strip_sentence_initial(text: str) -> str:
    """Bỏ từ đầu mỗi câu trước khi dò tên riêng.

    Tiếng Việt viết hoa chữ đầu câu, nên "Kính thiên văn nào…" và "Người mới nên…"
    sinh ra hai 'tên riêng' giả khác nhau → guard chặn oan cặp cùng ý (đo bằng sweep:
    recall tụt từ 75% xuống 50%)."""
    out = []
    for sentence in re.split(r"[.?!\n]+", text or ""):
        parts = sentence.strip().split(" ", 1)
        out.append(parts[1] if len(parts) > 1 else "")
    return " ".join(out)


def _propers(text: str) -> set:
    body = _strip_sentence_initial(text)
    return {w.lower() for w in _PROPER.findall(body) if w not in _STOP_PROPER}


def same_question(a: str, b: str) -> bool:
    """True khi hai câu an toàn để dùng chung một câu trả lời."""
    if _has_negation(a) != _has_negation(b):
        return False
    if _comparators(a) != _comparators(b):
        return False
    if _numbers(a) != _numbers(b):
        return False
    # Tên riêng: chặn khi MỖI bên có thực thể riêng mà bên kia không nhắc — đó là hai
    # câu hỏi về hai sản phẩm khác nhau. Nếu một bên chỉ là tập con (paraphrase lược
    # bớt "Ống nhòm ...") thì vẫn là cùng câu hỏi; đòi trùng khít làm recall tụt một
    # nửa trong sweep mà không chặn thêm được false-hit nào.
    pa, pb = _propers(a), _propers(b)
    if (pa - pb) and (pb - pa):
        return False
    return True


def demo():
    """Chạy: python3 semantic_guard.py — fail ngay nếu luật vỡ."""
    same = [
        ("Pin dùng được lâu không?", "Pin có bền không?"),
        ("Kính này giá bao nhiêu?", "Giá của kính này là bao nhiêu?"),
        ("Nó có phù hợp cho người mới không?", "Nó hợp cho người mới chứ, không khó dùng?"),
    ]
    diff = [
        ("Pin dùng được lâu không?", "Pin dùng được lâu"),                  # phủ định
        ("Kính dưới 200 USD nào tốt?", "Kính trên 200 USD nào tốt?"),        # so sánh
        ("Kính dưới 200 USD nào tốt?", "Kính dưới 500 USD nào tốt?"),        # con số
        ("Roof Binoculars giá bao nhiêu?", "Solar Filter giá bao nhiêu?"),   # tên riêng
    ]
    for a, b in same:
        assert same_question(a, b), f"phải coi là CÙNG: {a!r} vs {b!r}"
    for a, b in diff:
        assert not same_question(a, b), f"phải coi là KHÁC: {a!r} vs {b!r}"
    print(f"semantic_guard demo OK — {len(same)} cặp cùng ý, {len(diff)} cặp khác nghĩa")


if __name__ == "__main__":
    demo()
