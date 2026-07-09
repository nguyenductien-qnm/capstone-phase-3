# Đặc tả thiết kế Fallback & Retry cho cuộc gọi LLM (Mô hình Định tuyến Lai - Hybrid Routing)

> **Vùng triển khai:** Đơn vùng `us-east-1` | **Ngân sách:** < $300/tuần | **SLO:** p95 < 1.0s
>
> **Nguồn dữ liệu:**
> - Chi phí model: [AWS Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/)
> - Benchmark TTFT & throughput: [Artificial Analysis](https://artificialanalysis.ai/leaderboards/models)
> - Retry config: [AWS SDK Retry Behavior](https://docs.aws.amazon.com/sdkref/latest/guide/feature-retry-behavior.html)
> - Backoff & Jitter: [AWS Architecture Blog](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
>
> **Quyết định liên quan:** [ADR-004](../ADR-log.md#adr-004---định-tuyến-model-llm-lai-theo-tác-vụ-hybrid-task-specific-routing-cho-đơn-vùng-single-region)

## 1. Flowchart Cơ chế Dự phòng (Fallback & Retry Flowchart)

Sơ đồ dưới đây thể hiện quy trình xử lý lỗi khi các dịch vụ thực hiện cuộc gọi API đến AWS Bedrock (`us-east-1`):

### A. Luồng Tóm tắt Review (Product Reviews Summary) - Tải cao, Độ phức tạp thấp:
```mermaid
graph TD
    Start["Bắt đầu: Yêu cầu tóm tắt review"] --> InitCall["Khởi tạo cuộc gọi Amazon Nova Lite"]
    InitCall --> CallNova{"Gọi Amazon Nova Lite<br>ID: amazon.nova-lite-v1:0"}
    
    CallNova -- "Thành công (200 OK)" --> ReturnResult["Trả về kết quả tóm tắt"]
    
    CallNova -- "Lỗi 429 / 500 / Timeout > 2.0s" --> CheckRetry{"Đã thử lại đủ 2 lần chưa?"}
    CheckRetry -- "Chưa đủ" --> RetryNova["Thực hiện Thử lại (Retry) với Exponential Backoff"]
    RetryNova --> CallNova
    
    CheckRetry -- "Đã đủ 2 lần (Tổng 3 lần lỗi)" --> CheckFallbackFlag{"Feature Flag llmReviewsFallbackEnabled == true?"}
    
    CheckFallbackFlag -- "False (Tắt Fallback)" --> FailResponse["Trả về mã lỗi 500 cho client"]
    
    CheckFallbackFlag -- "True (Bật Fallback)" --> CallNovaMicro{"Gọi Amazon Nova Micro<br>ID: amazon.nova-micro-v1:0"}
    
    CallNovaMicro -- "Thành công (200 OK)" --> ReturnResult
    CallNovaMicro -- "Thất bại (429 / 500 / Timeout)" --> CallMock["Sử dụng Default Mock Summary làm Fallback cuối"]
    
    CallMock --> AlertAIOps["Gửi cảnh báo bất thường đến hệ thống AIOps"]
    ReturnResult --> End["Kết thúc"]
    CallMock --> End
    FailResponse --> End
```

### B. Luồng Trợ lý Chatbot (Shopping Copilot Agent) - Tải thấp, Độ phức tạp cao:
```mermaid
graph TD
    StartChat["Bắt đầu: Yêu cầu chat Copilot"] --> InitCallClaude["Khởi tạo cuộc gọi Claude 3.5 Sonnet"]
    InitCallClaude --> CallSonnet{"Gọi Claude 3.5 Sonnet<br>ID: anthropic.claude-3-5-sonnet-20241022-v2:0"}
    
    CallSonnet -- "Thành công (200 OK)" --> ReturnChat["Trả về câu trả lời + Tool output"]
    
    CallSonnet -- "Lỗi 429 / 500 / Timeout > 5.0s" --> CheckRetryChat{"Đã thử lại đủ 2 lần chưa?"}
    CheckRetryChat -- "Chưa đủ" --> RetrySonnet["Thực hiện Thử lại (Retry) với Exponential Backoff"]
    RetrySonnet --> CallSonnet
    
    CheckRetryChat -- "Đã đủ 2 lần" --> CallHaiku{"Gọi Claude 3.5 Haiku<br>ID: anthropic.claude-3-5-haiku-20241022-v1:0"}
    
    CallHaiku -- "Thành công (200 OK)" --> ReturnChat
    CallHaiku -- "Thất bại (429 / 500 / Timeout)" --> CallMockChat["Trả về câu trả lời mặc định lỗi hệ thống"]
    
    CallMockChat --> EndChat["Kết thúc"]
    ReturnChat --> EndChat
```

---

## 2. Thông số Cấu hình Hệ thống (Configuration Parameters)

Dưới đây là các thông số chi tiết cấu hình cho cơ chế định tuyến và fallback trong Đơn Vùng (`us-east-1`). Giá trị timeout và backoff dựa trên [AWS Architecture Blog — Backoff & Jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/) và benchmark từ [Artificial Analysis](https://artificialanalysis.ai/leaderboards/models):

### A. Luồng Tóm tắt Review (Product Reviews)
| Tham số | Model chính (Primary Model) | Model dự phòng (Fallback Model) |
|---|---|---|
| **Tên Model** | Amazon Nova Lite | Amazon Nova Micro |
| **Model ID AWS Bedrock** | `amazon.nova-lite-v1:0` | `amazon.nova-micro-v1:0` |
| **Timeout tối đa** | **2.0 giây (2000ms)** | **1.0 giây (1000ms)** |
| **Số lần tự động thử lại** | **Tối đa 2 lần** (Tổng cộng tối đa 3 cuộc gọi) | **Tối đa 1 lần** (Tổng cộng tối đa 2 cuộc gọi) |
| **Cơ chế Retry Backoff** | Exponential backoff (Base: 100ms, Factor: 1.5, Jitter: True) | Exponential backoff (Base: 50ms, Factor: 1.5, Jitter: True) |
| **Lỗi kích hoạt** | HTTP 429, HTTP 500/503, ClientTimeout (> 2.0s) | HTTP 429, HTTP 500/503, ClientTimeout (> 1.0s) |

### B. Luồng Trợ lý Chatbot (Shopping Copilot)
| Tham số | Model chính (Primary Model) | Model dự phòng (Fallback Model) |
|---|---|---|
| **Tên Model** | Claude 3.5 Sonnet | Claude 3.5 Haiku |
| **Model ID AWS Bedrock** | `anthropic.claude-3-5-sonnet-20241022-v2:0` | `anthropic.claude-3-5-haiku-20241022-v1:0` |
| **Timeout tối đa** | **5.0 giây (5000ms)** | **2.0 giây (2000ms)** |
| **Số lần tự động thử lại** | **Tối đa 2 lần** (Tổng cộng tối đa 3 cuộc gọi) | **Tối đa 1 lần** (Tổng cộng tối đa 2 cuộc gọi) |
| **Cơ chế Retry Backoff** | Exponential backoff (Base: 200ms, Factor: 1.5, Jitter: True) | Exponential backoff (Base: 100ms, Factor: 1.5, Jitter: True) |
| **Lỗi kích hoạt** | HTTP 429, HTTP 500/503, ClientTimeout (> 5.0s) | HTTP 429, HTTP 500/503, ClientTimeout (> 2.0s) |

---

## 3. Cấu hình biến môi trường (Environment Variables)

Các biến môi trường được cấu hình linh động cho Pod `product-reviews` trong cụm K8s:

*   **Cho Reviews Summary:**
    *   `LLM_REVIEWS_MAIN_MODEL`: ID model tóm tắt chính (Mặc định: `amazon.nova-lite-v1:0`).
    *   `LLM_REVIEWS_FALLBACK_MODEL`: ID model tóm tắt dự phòng (Mặc định: `amazon.nova-micro-v1:0`).
    *   `LLM_REVIEWS_TIMEOUT`: Timeout cho Nova Lite (Mặc định: `2.0`).
    *   `LLM_REVIEWS_MAX_RETRIES`: Số lần thử lại tối đa (Mặc định: `2`).
*   **Cho Shopping Copilot:**
    *   `LLM_COPILOT_MAIN_MODEL`: ID model chatbot chính (Mặc định: `anthropic.claude-3-5-sonnet-20241022-v2:0`).
    *   `LLM_COPILOT_FALLBACK_MODEL`: ID model chatbot dự phòng (Mặc định: `anthropic.claude-3-5-haiku-20241022-v1:0`).
    *   `LLM_COPILOT_TIMEOUT`: Timeout cho Sonnet (Mặc định: `5.0`).
    *   `LLM_COPILOT_MAX_RETRIES`: Số lần thử lại tối đa (Mặc định: `2`).

---

## 4. Rollback & Feature Flags

*   **Flagd Key:** `llmReviewsFallbackEnabled` (Boolean - Mặc định: `true`)
    *   *True:* Tự động kích hoạt chuyển đổi sang model dự phòng (Nova Micro) và Mock Summary khi Nova Lite bị lỗi hàng loạt. Đảm bảo SLO Availability > 99.9%.
    *   *False:* Tắt cơ chế dự phòng. Khi Nova Lite gặp lỗi sau số lần retry, ứng dụng trả thẳng lỗi 500 về storefront để bảo đảm tính nhất quán chất lượng bản dịch.
