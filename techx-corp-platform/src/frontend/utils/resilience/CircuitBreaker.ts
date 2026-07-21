// CDO-218 (Mandate 17 — R1): Circuit breaker + timeout + fallback cho lời gọi downstream
// không-thiết-yếu (ad, recommendation...). Tự viết, không phụ thuộc thư viện ngoài để
// không phải thêm dependency / npm install. KHÔNG đụng code team AI.

export type CircuitState = 'closed' | 'open' | 'half-open';

export interface CircuitBreakerOptions {
  name: string;
  // Số lần lỗi liên tiếp để "mở mạch".
  failureThreshold?: number;
  // Thời gian giữ mạch mở trước khi thử lại (ms).
  openMs?: number;
  // Deadline cho mỗi lời gọi (ms). Quá hạn coi như lỗi.
  timeoutMs?: number;
}

/**
 * Bọc một thao tác async: nếu downstream lỗi/chậm liên tục thì mở mạch và trả fallback
 * ngay (không dội lỗi), sau openMs cho 1 nhịp half-open để dò phục hồi.
 */
export class CircuitBreaker {
  private readonly name: string;
  private readonly failureThreshold: number;
  private readonly openMs: number;
  private readonly timeoutMs: number;

  private state: CircuitState = 'closed';
  private failureCount = 0;
  private openedAt = 0;
  // #3 single-flight: ở half-open chỉ cho ĐÚNG 1 probe đi, request khác trả fallback ngay
  // (tránh dội burst xuống downstream vừa hồi). An toàn vì Node single-thread: đoạn kiểm+set
  // cờ chạy đồng bộ trước await đầu tiên.
  private probeInProgress = false;

  constructor(opts: CircuitBreakerOptions) {
    this.name = opts.name;
    this.failureThreshold = opts.failureThreshold ?? 5;
    this.openMs = opts.openMs ?? 10_000;
    this.timeoutMs = opts.timeoutMs ?? 2_000;
  }

  /**
   * @param operation Thao tác cần bảo vệ.
   * @param fallback  Giá trị trả về khi mạch mở hoặc thao tác lỗi/timeout.
   */
  async execute<T>(operation: () => Promise<T>, fallback: T): Promise<T> {
    if (this.state === 'open') {
      if (Date.now() - this.openedAt < this.openMs) {
        return fallback; // mạch đang mở → trả fallback ngay
      }
      this.transitionTo('half-open'); // hết thời gian mở → cho dò
    }

    // #3: ở half-open, chỉ 1 probe được thực thi; các request đồng thời trả fallback.
    let isProbe = false;
    if (this.state === 'half-open') {
      if (this.probeInProgress) {
        return fallback;
      }
      this.probeInProgress = true;
      isProbe = true;
    }

    try {
      const result = await this.withTimeout(operation());
      this.onSuccess();
      return result;
    } catch (err) {
      this.onFailure();
      return fallback;
    } finally {
      if (isProbe) {
        this.probeInProgress = false;
      }
    }
  }

  private withTimeout<T>(promise: Promise<T>): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      const timer = setTimeout(
        () => reject(new Error(`[circuit-breaker:${this.name}] timeout after ${this.timeoutMs}ms`)),
        this.timeoutMs
      );
      promise.then(
        value => {
          clearTimeout(timer);
          resolve(value);
        },
        err => {
          clearTimeout(timer);
          reject(err);
        }
      );
    });
  }

  // #4: log CHỈ khi trạng thái thật sự đổi (không spam mỗi request). Dùng console.warn để
  // log lọt vào stdout -> log pipeline; KHÔNG thêm OTel metric để tránh coupling/cardinality.
  private transitionTo(next: CircuitState): void {
    if (this.state === next) {
      return;
    }
    const prev = this.state;
    this.state = next;
    if (next === 'open') {
      this.openedAt = Date.now();
    }
    // eslint-disable-next-line no-console
    console.warn(`[circuit-breaker:${this.name}] state ${prev} -> ${next} (failures=${this.failureCount})`);
  }

  private onSuccess(): void {
    this.failureCount = 0;
    this.transitionTo('closed');
  }

  private onFailure(): void {
    this.failureCount += 1;
    if (this.state === 'half-open' || this.failureCount >= this.failureThreshold) {
      this.transitionTo('open');
    }
  }
}
