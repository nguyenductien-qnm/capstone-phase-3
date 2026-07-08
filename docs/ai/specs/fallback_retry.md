# Đặc tả thiết kế Fallback & Retry cho cuộc gọi LLM

## 1. Flowchart Cơ chế Dự phòng (Fallback & Retry Flowchart)

Sơ đồ dưới đây thể hiện quy trình xử lý lỗi khi dịch vụ `product-reviews` thực hiện cuộc gọi API tóm tắt review đến AWS Bedrock:

```mermaid
graph TD
    Start[Bắt đầu: Yêu cầu tóm tắt review] --> InitCall[Khởi tạo cuộc gọi Claude 3.5 Sonnet]
    InitCall --> CallSonnet{Gọi Claude 3.5 Sonnet<br>ID: anthropic.claude-3-sonnet-20240229-v1:0}
    
    CallSonnet -- Thành công (200 OK) --> ReturnResult[Trả về kết quả tóm tắt]
    
    CallSonnet -- Lỗi 429 / 500 / Timeout > 2.0s --> CheckRetry{Đã thử lại đủ 2 lần chưa?}
    CheckRetry -- Chưa đủ --> RetrySonnet[Thực hiện Thử lại (Retry) với Exponential Backoff]
    RetrySonnet --> CallSonnet
    
    CheckRetry -- Đã đủ 2 lần (Tổng 3 lần lỗi) --> CheckFallbackFlag{Feature Flag llmReviewsFallbackEnabled == true?}
    
    CheckFallbackFlag -- False (Tắt Fallback) --> FailResponse[Trả về mã lỗi 500 cho client]
    
    CheckFallbackFlag -- True (Bật Fallback) --> CallHaiku{Gọi Claude 3 Haiku<br>ID: anthropic.claude-3-haiku-20240307-v1:0}
    
    CallHaiku -- Thành công (200 OK) --> ReturnResult
    CallHaiku -- Thất bại (429 / 500 / Timeout) --> CallMock[Sử dụng Default Mock Summary làm Fallback cuối]
    
    CallMock --> AlertAIOps[Gửi cảnh báo bất thường đến hệ thống AIOps]
    ReturnResult --> End[Kết thúc]
    CallMock --> End
    FailResponse --> End
```

## 2. Thông số Cấu hình Hệ thống (Configuration Parameters)

Dưới đây là các thông số chi tiết cấu hình cho cơ chế Fallback và Retry:

| Tham số | Model chính (Primary Model) | Model dự phòng (Fallback Model) |
|---|---|---|
| **Tên Model** | Claude 3.5 Sonnet | Claude 3 Haiku |
| **Model ID AWS Bedrock** | `anthropic.claude-3-sonnet-20240229-v1:0` | `anthropic.claude-3-haiku-20240307-v1:0` |
| **Timeout tối đa (p95 threshold)** | **2.0 giây (2000ms)** | **1.0 giây (1000ms)** |
| **Số lần tự động thử lại (Retries)** | **Tối đa 2 lần** (Tổng cộng tối đa 3 cuộc gọi) | **Tối đa 1 lần** (Tổng cộng tối đa 2 cuộc gọi) |
| **Cơ chế giãn cách (Retry Backoff)** | Exponential backoff (Base: 200ms, Factor: 1.5, Jitter: True) | Exponential backoff (Base: 100ms, Factor: 1.5, Jitter: True) |
| **Lỗi kích hoạt thử lại & fallback** | HTTP 429 (Rate Limit), HTTP 500/503 (Server Error), ClientTimeout (> 2.0s) | HTTP 429, HTTP 500/503, ClientTimeout (> 1.0s) |

### Chi tiết về Retry Backoff cho Model chính:
- Lần thử lại 1: Đợi ~200ms (kèm ngẫu nhiên jitter để giảm tải đồng loạt).
- Lần thử lại 2: Đợi ~300ms.
- Nếu cả 2 lần thử lại đều thất bại hoặc timeout, tiến hành chuyển tiếp sang Model dự phòng (Claude 3 Haiku).

## 3. Rollback & Feature Flags

Cơ chế fallback được điều khiển động qua OpenFeature để quản trị rủi ro vận hành:

- **Flagd Key:** `llmReviewsFallbackEnabled`
- **Kiểu dữ liệu:** `Boolean` (Mặc định: `true`)
- **Hành vi khi bật (`true`):** Tự động chuyển đổi sang Claude 3 Haiku và sau đó là Mock Summary khi Claude 3.5 Sonnet sập hoàn toàn. Đảm bảo độ sẵn sàng dịch vụ (SLO Availability > 99.9%).
- **Hành vi khi tắt (`false`):** Nếu Claude 3.5 Sonnet bị lỗi sau số lần retry chỉ định, dịch vụ Product Reviews sẽ dừng ngay lập tức và trả về mã lỗi 500 trực tiếp cho storefront, không gọi Haiku hay Mock. Kịch bản này được dùng khi nhà phát triển muốn cô lập lỗi hoặc bảo vệ chất lượng dữ liệu tuyệt đối (không chấp nhận bản tóm tắt chất lượng thấp hơn của Haiku).

