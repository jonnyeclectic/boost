# Support

What boost supports, for how long, and where to ask.

## Where to ask

| You want to | Go here |
|---|---|
| Report a bug | [Open an issue](https://github.com/jonnyeclectic/boost/issues/new/choose) |
| Request a feature | [Open an issue](https://github.com/jonnyeclectic/boost/issues/new/choose) |
| Report a vulnerability | **Not an issue** — [SECURITY.md](SECURITY.md) |
| Diagnose a broken install | [`docs/DEBUGGING.md`](docs/DEBUGGING.md), then `boost doctor` |
| Contribute a change | [CONTRIBUTING.md](CONTRIBUTING.md) |

`boost doctor` is the first thing to run for anything that looks like a
misconfiguration. It names the single next action for each problem it finds
rather than printing a menu, and its output is the most useful thing to paste
into an issue.

## What is supported

**Only the latest release.** boost releases on every merge to `main`, so the
latest version is usually minutes old and the gap between "what you have" and
"what is fixed" is small by design. Bug fixes and security fixes go into the
next release; there are no backport branches and no long-term-support line.

If you are on an older version, the supported answer is to upgrade:

```bash
pipx upgrade boost-skill-cli     # or: pip install -U boost-skill-cli
```

**Supported environments** — these are what CI runs on every pull request, so a
regression on any of them fails the build:

| | Supported |
|---|---|
| Python | 3.12, 3.13, 3.14 (and a non-blocking 3.14 free-threaded canary) |
| Operating system | Linux, macOS, Windows |
| Required external tools | `git` |

Python 3.11 and earlier are **not** supported: the project's floor is
`requires-python = ">=3.12"`.

## When a version stops receiving security updates

**The moment a newer release exists.** A version other than the latest receives
no security updates, and none will be backported to it.

This is stated as a policy rather than left implicit because the alternative
would be misleading. With a release cut on every merge, maintaining a supported
older line would mean supporting hundreds of versions; the project does not do
that and will not pretend to. In exchange, the upgrade path is deliberately
cheap — a single `pipx upgrade`, a stdlib-only runtime with no dependency
resolution to go wrong, and no configuration migration between patch releases.

If a release fixes a publicly known vulnerability, the release notes name it and
its identifier — see
[SECURITY.md](SECURITY.md#vulnerability-fixes-in-release-notes).

## What is not supported

- **The content of third-party skills, rules and workflows.** boost gives you a
  skill's provenance, its integrity digest and a diff. Judging what a skill
  tells your agent to do is yours; see the limits section of
  [`docs/security-design.md`](docs/security-design.md).
- **`boost serve`** as a hardened server. It is a local development
  convenience for a trusted network.
- **Optional extras** (`[rag]`, `[eval]`, `[bdd]`, `[langchain]`) carry
  third-party dependencies and their own compatibility constraints. The default
  install is stdlib-only and is what the support statement above covers.

## Response expectations

This is a single-maintainer project ([MAINTAINERS.md](MAINTAINERS.md)), so
response times depend on one person's availability. Vulnerability reports are
acknowledged within a few days and are the highest priority; ordinary issues are
triaged as they arrive but carry no service-level guarantee.
