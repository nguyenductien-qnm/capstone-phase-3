# Platform charts

- `application/` is the current deployable chart. It still contains the
  application and the optional in-cluster observability dependencies so this
  repository reorganization does not change runtime behavior.
- `observability/` documents the future extraction boundary. Do not configure
  Argo CD to deploy it until a real standalone chart has been implemented and
  tested.
