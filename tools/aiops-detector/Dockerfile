# TF1-53 [AIOps-W1-T5] - image cho AIOps detector (dung khi deploy in-cluster o Tuan 2)
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sources.py alerter.py detector.py rules.yaml ./

# Chay lien tuc; URL + webhook truyen qua env/secret khi deploy
ENTRYPOINT ["python", "detector.py"]
