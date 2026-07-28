# Repository Guidelines

## Project Structure & Module Organization

This repository contains the Phase 3 TechX Corp service platform and its operational evidence. Read `RULES.md`, `onboarding/`, and `GETTING_STARTED.md` before changing deployment or runtime behavior.

- `techx-corp-platform/src/` — polyglot microservices, generated protobuf code, and AI review functionality.
- `techx-corp-platform/` — Docker Compose definitions, service tests, and build helpers.
- `aiops/` — incident replay, log clustering, detection, and remediation tooling.
- `platform/` — Helm charts, GitOps values, policies, and deployment configuration.
- `terraform/` — infrastructure modules and environment configuration.
- `tests/` — cross-service, smoke, load, chaos, and validation tests.
- `scripts/` — bootstrap, build, deploy, audit, and repository-validation scripts.
- `docs/`, `mandates/`, and `onboarding/` — ADRs, evidence, requirements, and operating guidance.

## Build, Test, and Development Commands

Run platform commands from `techx-corp-platform/`:

```sh
make start       # Start the full local stack at http://localhost:8080
make start-minimal
make stop        # Stop services and remove test volumes
make build       # Build service images
make run-tests   # Run frontend and trace-based integration tests
make check       # Spell, Markdown, license, and link checks
```

Use `pytest` for Python unit tests, for example `pytest aiops/test_incident_replay.py`. Run `tests/vap/run-dry-run-tests.sh` for admission-policy validation.

## Coding Style & Naming Conventions

Follow the existing language conventions: `gofmt` for Go, standard C# formatting, and four-space indentation for Python. Use descriptive `snake_case` for Python files/functions, `PascalCase` for C# types, and lower-case package names in Go. Keep generated protobuf and Kubernetes files reproducible; regenerate them with `make generate-protobuf` or `make generate-kubernetes-manifests` rather than hand-editing.

## Testing Guidelines

Keep unit tests beside the service or AIOps module they cover; place cross-service tests under `tests/`. Go tests use `*_test.go`, Python tests use `test_*.py`, and .NET tests use xUnit `[Fact]` methods. Run the narrowest relevant test first, then the platform integration checks.

## Commit & Pull Request Guidelines

Use Conventional Commit messages such as `fix(ai): ...`, `feat(evals): ...`, or `docs(readme): ...`. Work on a branch; do not push directly to `main`. PRs should include a concise summary, Jira or incident link, local test results, affected environments, rollback details, and audit evidence. Include screenshots or logs when they clarify UI or operational changes.

## Security & Configuration

Never commit secrets, tokens, full account IDs, `terraform.tfvars`, or shared credentials. Treat infrastructure changes as high risk: review Terraform plans or Helm diffs before applying and preserve a clear change trail.
