# Selenium checkout runner

This runner replaces direct API checkout traffic for MANDATE-09 validation. It
opens the storefront in Chrome, adds a product to the cart, submits the real
React checkout form, and verifies that the browser sent a UUID
`Idempotency-Key` before accepting the resulting order page.

It does not modify or import the mentor-owned Locust file.

## Local Chrome

Python 3.10+ and Chrome are required. Selenium Manager resolves the compatible
driver automatically.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r tests/selenium-checkout/requirements.txt
python tests/selenium-checkout/checkout_runner.py \
  --base-url http://localhost:8080 \
  --workers 2 \
  --iterations 5 \
  --output selenium-checkout-results.json
```

On PowerShell, activate the environment with:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Selenium Grid

Point the same runner at an existing Grid:

```bash
python tests/selenium-checkout/checkout_runner.py \
  --base-url https://storefront.example.test \
  --remote-url http://localhost:4444/wd/hub \
  --workers 5 \
  --iterations 10
```

Each worker owns one browser session. Before every iteration the runner clears
cookies and browser storage, which makes the storefront create a new user and a
new checkout key through its normal React code.

Selenium is intentionally used for a small number of high-fidelity browser
journeys. It is much heavier than HTTP load generation and should not be used
to claim hundreds of concurrent users from a single runner.
