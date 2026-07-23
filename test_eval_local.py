import os
os.environ["BASE_URL"] = "http://localhost:3000/api"
with open("docs/ai/evals/eval_mandate06_prod.py", "r") as f:
    code = f.read()
code = code.replace('"https://ecommerce.nguyenductien.cloud/api"', 'os.environ.get("BASE_URL", "https://ecommerce.nguyenductien.cloud/api")')
with open("eval_mandate06_local.py", "w") as f:
    f.write(code)
