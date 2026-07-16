# GitOps layout

- `bootstrap/`: root Argo CD application installed once per cluster.
- `applications/`: child applications managed by the root application.
- `environments/`: Helm values owned per environment.
- `projects/`: Argo CD project boundaries when the default project is replaced.

The current child application uses the sandbox values and retains the existing
automated sync behavior.
