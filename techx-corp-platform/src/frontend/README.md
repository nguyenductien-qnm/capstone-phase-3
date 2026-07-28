# Frontend service

The frontend is a [Next.js](https://nextjs.org/) application that is composed
by two layers.

1. Client side application. Which renders the components for the OTEL webstore.
2. API layer. Connects the client to the backend services by exposing REST endpoints.

## API contract

### `POST /api/checkout` requires `Idempotency-Key`

Placing an order is retried inside checkout when the database connection blips
(managed failover, engine switchover, parameter-group reboot). The key is what
lets a retry return the original order instead of creating a second one, so the
endpoint requires it:

| Rule | Value |
|---|---|
| Header | `Idempotency-Key` |
| Format | 8–128 chars, `A-Z a-z 0-9 . _ : -`, first char alphanumeric |
| Recommended | UUID v4 |
| Missing or malformed | `400` |

The key identifies one checkout **attempt**, not a user and not an order — it
must be new per attempt and identical across retries of that attempt. The web UI
generates one per "Place Order" click (`components/Cart/CartDetail.tsx`); the
load generator generates one per request (`src/load-generator/locustfile.py`).

Calling it by hand:

```shell
curl -X POST "$HOST/api/checkout?currencyCode=USD" \
  -H "content-type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d @order.json
```

## Build Locally

By running `docker compose up` at the root of the project you'll have access to
the frontend client by going to <http://localhost:8080/>.

## Local development

Currently, the easiest way to run the frontend for local development is to execute

```shell
docker compose run --service-ports -e NODE_ENV=development --volume $(pwd)/src/frontend:/app --volume $(pwd)/pb:/app/pb --user node --entrypoint sh frontend
```

from the root folder.

It will start all of the required backend services
and within the container simply run `npm run dev`.
After that the app should be available at <http://localhost:8080/>.
