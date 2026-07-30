# TF1-53 [AIOps-W1-T5] - image cho AIOps detector (dung khi deploy in-cluster o Tuan 2)
FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sources.py alerter.py k8s_status.py detector.py rules.yaml ./

# MANDATE-05: khong chay root trong container (runAsNonRoot enforce o admission).
# uid/gid >= 10000 de khong trung user he thong tren node.
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
USER 10001:10001

# Chay lien tuc; URL + webhook truyen qua env/secret khi deploy
ENTRYPOINT ["python", "detector.py"]
