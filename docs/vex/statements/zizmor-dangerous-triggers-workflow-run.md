---
id: zizmor-dangerous-triggers-workflow-run
vulnerability: "zizmor:dangerous-triggers"
status: not_affected
justification: inline_mitigations_already_exist
source: .github/zizmor.yml (ci-failure-issue.yml:28, publish.yml:19, post-deploy.yml:21, sbom.yml:29)
---
zizmor's `dangerous-triggers` rule flags `workflow_run`, because the classic
failure mode is a privileged run executing pull-request-controlled code. Four
workflows use it — `ci-failure-issue.yml`, `publish.yml`, `post-deploy.yml`,
`sbom.yml` — and each carries the mitigation that makes the pattern safe in
its specific case, recorded inline in `.github/zizmor.yml`: none of them
checks out the triggering run's head SHA (each explicitly checks out `main`,
a release tag, or nothing at all), so no code a fork's pull request could
influence ever runs in the privileged context. `publish.yml`, the one job that
holds write credentials (PyPI Trusted Publisher OIDC), is additionally scoped
to `push` events from this repository only — a fork PR opened from a branch
named `main` cannot satisfy that filter. `sbom.yml` is gated on
`head_repository == this repository` for the same reason. The remaining two
hold only `contents: read` and no secrets.
