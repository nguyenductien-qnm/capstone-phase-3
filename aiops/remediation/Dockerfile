# TF1-72 [AIOps-W2] - image cho remediation engine.
#
# LUU Y: remediation.py tai dung sources.py/alerter.py cua aiops/detector/ (khong
# duplicate code) -> build context PHAI la thu muc aiops/ (cha cua ca detector/ va
# remediation/), KHONG PHAI aiops/remediation/ don le:
#
#   docker buildx build --platform linux/amd64 \
#     -f aiops/remediation/Dockerfile \
#     -t 384511757667.dkr.ecr.us-east-1.amazonaws.com/ecommerce-dev-techx-corp:1.1-aiops-remediation \
#     --push aiops
FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a

WORKDIR /app
COPY remediation/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY detector/sources.py detector/alerter.py ./
# CANH BAO: danh sach nay liet ke TUNG FILE. Them module moi vao remediation/ ma
# quen them vao day thi image thieu file -> pod CrashLoopBackOff voi
# "ModuleNotFoundError" NGAY tren cum, va CI khong bat duoc vi test chay tren source
# tree chu khong chay trong image. Da dinh dung loi nay 28/07 voi audit.py (TF1-112).
# Co test chan: test_dockerfile_copies_all_modules.
COPY remediation/remediation.py remediation/k8s_actions.py remediation/verifier.py \
     remediation/blast_radius.py remediation/circuit_breaker.py remediation/audit.py \
     remediation/audit_report.py \
     remediation/remediation_policy.yaml ./
COPY detector/rules.yaml ./detector_rules.yaml

# MANDATE-05: khong chay root trong container (runAsNonRoot enforce o admission).
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
USER 10001:10001

# --rules tro ve file rules.yaml da COPY rieng (detector/rules.yaml khong nam cung
# thu muc trong image nay nhu luc dev, xem remediation.py --rules default).
ENTRYPOINT ["python", "remediation.py", "--rules", "detector_rules.yaml"]
