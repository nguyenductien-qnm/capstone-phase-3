# TechX Corp Platform

Internal microservice platform powering the TechX Corp online store: a polyglot,
Kubernetes-native system with a web storefront, product/cart/checkout/payment
services, an async messaging pipeline, an AI product-review summarizer, and a
full observability stack (metrics, logs, traces, dashboards).

## Layout
- `src/` - application microservices + AI review service + LLM
- `kubernetes/` - all-in-one manifest (`techx-corp-platform.yaml`)
- `docker-compose.yml` - local run
- `Makefile` - build / run helpers

Kubernetes deploy: use the Helm chart in `../platform/charts/application` and
the environment values in `../platform/gitops/environments/`.

## Run locally
```sh
docker compose up --force-recreate --remove-orphans --detach
```
Storefront: http://localhost:8080/

## License
Distributed under the Apache License 2.0. See `LICENSE`.
