# Cross-service tests

Place end-to-end, load, chaos and smoke tests that span multiple services here.
Unit tests remain next to the service or AIOps module they validate.

- `gatekeeper/` — admission-policy negative/positive test package (Directive #5):
  manifests a mentor can apply to see Gatekeeper reject violating pods. See
  [gatekeeper/README.md](gatekeeper/README.md).
