# Repository scripts

- `bootstrap/`: one-time cluster/bootstrap operations.
- `build/`: build and publish application artifacts.
- `deploy/`: deployment and seed-image helpers.
- `validate/`: non-mutating repository and deployment checks.

Scripts that access repository files resolve the repository root themselves and
can be invoked from any working directory.
