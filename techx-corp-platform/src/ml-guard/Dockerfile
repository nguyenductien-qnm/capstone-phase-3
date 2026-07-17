# ml-guard — grounding NLI gate (MANDATE-06 / ADR-014). MANDATE-05: non-root, pinned base.
FROM python:3.12-slim-bookworm@sha256:72d3d75f2639ab82b34b29390ad3d6e0827c775befee94edda8e9976818f488d AS build

WORKDIR /app
COPY ./src/ml-guard/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Bake model vào image: pod không cần egress tới HF Hub, không cold-download.
FROM python:3.12-slim-bookworm@sha256:72d3d75f2639ab82b34b29390ad3d6e0827c775befee94edda8e9976818f488d

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

USER 10001:10001
EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=3s --start-period=90s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/healthz')"
CMD ["python", "server.py"]
