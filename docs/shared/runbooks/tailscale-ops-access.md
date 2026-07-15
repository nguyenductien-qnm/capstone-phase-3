# Tailscale ops access for mentor and grader

Use this guide to access Grafana, Jaeger, ArgoCD, and Locust. No AWS,
`kubectl`, Helm, or Kubernetes knowledge is required.

## Admin preparation

1. Add reviewer email to `group:ops-reviewers` in Tailscale ACLs.
2. Send a one-time tailnet invite. Never commit the invite URL.
3. Confirm MagicDNS and HTTPS certificates are enabled.
4. Confirm these tagged endpoints appear online in Tailscale Machines:
   `tag:ops-grafana`, `tag:ops-jaeger`, `tag:ops-argocd`, and
   `tag:ops-locust`.

Official references:

- [Invite a user](https://tailscale.com/kb/1271/invite-any-user)
- [Install Tailscale](https://tailscale.com/kb/1017/install)
- [Download Tailscale](https://tailscale.com/download)

## Reviewer setup

1. Open the invite using the invited email account.
2. Install Tailscale for your operating system.
3. Sign in with the same identity used for the invite.
4. Confirm the Tailscale client shows `Connected`.
5. Open the private endpoints below. Replace `<tailnet-name>` with the
   organization tailnet DNS name.

```text
https://grafana-tf1.<tailnet-name>.ts.net
https://jaeger-tf1.<tailnet-name>.ts.net
https://argocd-tf1.<tailnet-name>.ts.net
https://locust-tf1.<tailnet-name>.ts.net
```

Grafana and ArgoCD can still request application credentials. Send those
credentials through the approved secret channel, never through Git.

## Access verification

While Tailscale is connected:

```bash
curl -I https://grafana-tf1.<tailnet-name>.ts.net
curl -I https://jaeger-tf1.<tailnet-name>.ts.net
curl -I https://argocd-tf1.<tailnet-name>.ts.net
curl -I https://locust-tf1.<tailnet-name>.ts.net
```

Expected: endpoint resolves and returns an HTTP response. A login redirect is
acceptable.

Disconnect Tailscale and repeat one request. Expected: private endpoint does
not resolve or cannot be reached. Do not use the public storefront or
Cloudflare quick-tunnel URL for ops access.

## Troubleshooting

- Name does not resolve: reconnect Tailscale; confirm invite acceptance and
  MagicDNS.
- Request times out: admin checks endpoint machine status, ACL group, and
  per-service tag.
- Browser shows certificate warning: admin checks Tailscale HTTPS certificates
  and Ingress readiness. Do not bypass the warning.
- Login page loads but rejects credentials: Tailscale works; fix application
  credentials separately.

## Remove access

Admin removes reviewer from `group:ops-reviewers` and the tailnet when review
ends. This revokes network access without changing Kubernetes or AWS.
