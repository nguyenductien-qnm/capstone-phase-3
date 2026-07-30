# Observability chart boundary

The current Prometheus, Grafana, Jaeger, OpenSearch and OTel configuration is
still packaged by `../application/`. This directory intentionally does not
contain a `Chart.yaml`: it must not be treated as a deployable chart yet.

Extract observability only in a dedicated change that preserves values,
ownership, upgrade order and rollback behavior.
