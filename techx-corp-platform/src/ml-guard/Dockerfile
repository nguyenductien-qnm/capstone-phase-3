# ml-guard — grounding NLI gate (MANDATE-06 / ADR-014). MANDATE-05: non-root, pinned base.
FROM python:3.12-slim-trixie@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de AS build

WORKDIR /app
COPY ./src/ml-guard/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt
# Install auto-instrumentation plugins (same pattern as product-reviews)
RUN PYTHONPATH=/install/lib/python3.12/site-packages /install/bin/opentelemetry-bootstrap -a install --prefix=/install || true

# Install grpc_health_probe
RUN apt-get update && apt-get install -y wget && \
    wget -qO /install/bin/grpc_health_probe https://github.com/grpc-ecosystem/grpc-health-probe/releases/download/v0.4.19/grpc_health_probe-linux-amd64 && \
    chmod +x /install/bin/grpc_health_probe

# Bake model vào image: pod không cần egress tới HF Hub, không cold-download.
FROM python:3.12-slim-trixie@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

COPY --from=build /install /usr/local
WORKDIR /app
ENV HF_HOME=/app/hf-cache \
    ML_GUARD_MODEL=MoritzLaurer/mDeBERTa-v3-base-mnli-xnli \
    PROMPT_GUARD_MODEL=protectai/deberta-v3-base-prompt-injection-v2 \
    ML_GUARD_PORT=8090
RUN python -m spacy download en_core_web_lg && \
    python -c "from transformers import AutoTokenizer, AutoModelForSequenceClassification as M, pipeline; \
    import os; m = os.environ['ML_GUARD_MODEL']; AutoTokenizer.from_pretrained(m); M.from_pretrained(m); \
    p = os.environ['PROMPT_GUARD_MODEL']; pipeline('text-classification', model=p)" \
    && chown -R 10001:10001 /app

COPY ./src/ml-guard/server.py .
COPY ./src/ml-guard/ml_guard_pb2.py .
COPY ./src/ml-guard/ml_guard_pb2_grpc.py .
# Tái dùng assume-role client factory của product-reviews (single source, không fork).
COPY ./src/product-reviews/bedrock_client.py .

USER 10001:10001
EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=3s --start-period=90s \
    CMD ["grpc_health_probe", "-addr=127.0.0.1:8090"]
CMD ["opentelemetry-instrument", "python", "server.py"]
