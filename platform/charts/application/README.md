# TechX Corp Platform - Helm Chart

Helm chart to deploy the TechX Corp platform on Kubernetes: application
microservices, AI review service + LLM, and the bundled observability stack
(collector, metrics, logs, traces, dashboards).

## Install
```sh
helm install techx-corp ./ -n techx-corp --create-namespace
```

## License
Apache License 2.0.
