---
id: zizmor-adhoc-packages-lint-runners
vulnerability: "zizmor:adhoc-packages"
status: not_affected
justification: inline_mitigations_already_exist
source: .github/zizmor.yml (theme-lint.yml:48, visual.yml:38)
---
zizmor's `adhoc-packages` rule flags installing packages without a lockfile,
because an unpinned install can resolve to a tampered or unexpectedly newer
package. Two workflows do this on purpose: `theme-lint.yml` installs
major-pinned linters with `--no-save` into an empty checkout — boost ships no
`package.json`, so a lockfile would exist solely for this one step — and
`visual.yml` installs a pinned `puppeteer-core` from
`tests/visual/package.json`, also `--no-save`. Both run on an ephemeral
runner, hold only `contents: read`, and their output gates nothing but
themselves — a compromised lint or screenshot tool in either job cannot reach
a secret or influence a later, privileged job.
