# TF1-72 [AIOps-W2] - image cho remediation engine.
#
# LUU Y: remediation.py tai dung sources.py/alerter.py cua aiops/detector/ (khong
# duplicate code) -> build context PHAI la thu muc aiops/ (cha cua ca detector/ va
# remediation/), KHONG PHAI aiops/remediation/ don le:
#
#   docker buildx build --platform linux/amd64 \
#     -f aiops/remediation/Dockerfile \
#     -t 804372444787.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp:1.0-aiops-remediation \
#     --push aiops
FROM python:3.12-slim

WORKDIR /app
COPY remediation/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY detector/sources.py detector/alerter.py ./
COPY remediation/remediation.py remediation/k8s_actions.py remediation/verifier.py \
     remediation/blast_radius.py remediation/circuit_breaker.py \
     remediation/remediation_policy.yaml ./
COPY detector/rules.yaml ./detector_rules.yaml

# MANDATE-05: khong chay root trong container (runAsNonRoot enforce o admission).
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
USER 10001:10001

# --rules tro ve file rules.yaml da COPY rieng (detector/rules.yaml khong nam cung
# thu muc trong image nay nhu luc dev, xem remediation.py --rules default).
ENTRYPOINT ["python", "remediation.py", "--rules", "detector_rules.yaml"]
