# Verifying a boost release

Every published boost artifact carries a cryptographically signed record of
which workflow built it, from which commit, in which repository. This page is
how you check that yourself rather than taking it on trust.

You need [`gh`](https://cli.github.com/) 2.49 or newer. Nothing here requires an
account with the project, a paid service, or a key exchanged out of band.

## Verify the artifact you actually installed

Download the exact file, then verify it:

```bash
# Fetch the wheel without installing it
pip download boost-skill-cli --no-deps --only-binary :all: -d ./verify
cd verify

# Check its build provenance
gh attestation verify boost_skill_cli-*.whl --repo jonnyeclectic/boost
```

A successful run reports the verified attestation and the predicate type
`https://slsa.dev/provenance/v1`. Anything else — no attestation found, a
signature that does not verify, a different repository — means **do not install
it**, and is worth [reporting](../SECURITY.md).

The same command works on the sdist and on any asset attached to a
[GitHub release](https://github.com/jonnyeclectic/boost/releases).

## Verify who built it

The attestation is only as useful as the identity inside it, so check that too:

```bash
gh attestation verify boost_skill_cli-*.whl \
  --repo jonnyeclectic/boost \
  --signer-workflow jonnyeclectic/boost/.github/workflows/publish.yml
```

This asserts more than "someone at GitHub signed this". It asserts that the
artifact was produced by **`publish.yml` in this repository**, and it fails if
the file was built by a different workflow, from a fork, or from a branch other
than the one that workflow runs on.

To read the provenance rather than just check it:

```bash
gh attestation verify boost_skill_cli-*.whl --repo jonnyeclectic/boost --format json \
  | jq '.[0].verificationResult.signature.certificate
        | {workflow: .buildSignerURI, sha: .sourceRepositoryDigest, ref: .sourceRepositoryRef}'
```

The `sha` is the commit on `main` that produced the release. Every line of that
commit is public, and it is the same commit the corresponding git tag points at.

### What the identity means

There is **no maintainer signing key** to distribute, trust, or rotate, and that
is deliberate. boost publishes through
[PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/): PyPI mints
a short-lived OpenID Connect token for `publish.yml` at the moment of upload.
The signing identity is the *workflow*, bound to this repository — not a person
and not a long-lived secret. A stolen laptop cannot sign a boost release,
because there is nothing on it to steal.

The consequence for you: verify the **workflow identity** above, not a key
fingerprint. If you ever see instructions telling you to trust a personal
PGP key for boost, they did not come from this project.

## What is attached to a release

| Asset | What it is | How to check it |
|---|---|---|
| Wheel and sdist (on PyPI) | The installable artifacts | `gh attestation verify` as above |
| CycloneDX SBOM | Generated at build time per released wheel, attached to the GitHub release | Read it; it enumerates the dependency set for that exact build |
| Git tag | Points at the commit the release was built from | `git verify-tag` is *not* applicable — tags are unsigned; the provenance attestation is the authority |
| Release notes | Assembled from the merged pull requests in that release | [Releases page](https://github.com/jonnyeclectic/boost/releases) |

## Can you rebuild it yourself? Yes — the measurement

A reproducible build lets a third party rebuild the artifact from source and
get the same bytes, which is a stronger guarantee than provenance alone:
provenance says *this workflow produced these bytes*, reproducibility says
*and here is how you check that without trusting the workflow*.

`scripts/check_reproducible.py` is what keeps this a measurement rather than an
opinion: it builds the project twice with `SOURCE_DATE_EPOCH` pinned to the
same value both times, runs the same sdist fix `publish.yml` runs, and diffs
the results by sha256. Run it yourself:

```bash
python3 scripts/check_reproducible.py
```

```text
 match  boost_skill_cli-1.2.31.dev5+gc954caf33-py3-none-any.whl
 match  boost_skill_cli-1.2.31.dev5+gc954caf33.tar.gz

SOURCE_DATE_EPOCH=1787969408
REPRODUCIBLE
```

Both artifacts are now bit-identical across two independent builds. `--skip-
normalize` reruns without the sdist fix, to show the gap it closes:

```bash
python3 scripts/check_reproducible.py --skip-normalize
```

```text
 match  boost_skill_cli-1.2.31.dev5+gc954caf33-py3-none-any.whl
differ  boost_skill_cli-1.2.31.dev5+gc954caf33.tar.gz

SOURCE_DATE_EPOCH=1787969408
NOT REPRODUCIBLE
```

The wheel was already reproducible once `SOURCE_DATE_EPOCH` is set, because
`setuptools` honours it when stamping the zip entries. The sdist was not:
`setuptools` writes each tar member's real build-time mtime, and the builder's
`uid`, `gid` and user name, into the sdist, with no environment variable to
override either — tracked upstream as
[pypa/setuptools#2133](https://github.com/pypa/setuptools/issues/2133), open
since 2020 with no fix landed as of the version boost pins. Two builds two
seconds apart therefore differed in 54 members — every directory, plus the
files generated during the build (`PKG-INFO`, the `.egg-info` set) — and a
build on another machine would have differed in the ownership fields as well.
The gzip header carries its own timestamp on top of that.

Two things closed this gap:

1. **The release toolchain is pinned.** `publish.yml` used to run `pip install
   build twine` unpinned, so the toolchain that produced last month's wheel was
   not recoverable from the repository. It now installs from the hash-pinned
   `requirements/release-tools.txt` — the same file `package-metadata.yml` and
   `pip-audit.yml` already install from. The part of the toolchain that
   actually determines the artifacts' bytes is `setuptools` and
   `setuptools-scm`, resolved fresh into an isolated build environment on every
   `python -m build` regardless of what the outer environment has installed —
   so `pyproject.toml`'s `[build-system].requires` is now exact-pinned
   (`setuptools==83.0.0`, `setuptools-scm==10.2.1`) rather than left as a
   floor. PEP 508's requirement-string syntax has no hash field, so an exact
   version is the strongest pin available at that layer.
2. **The sdist is normalised.** `scripts/normalize_sdist.py` rewrites the
   tarball `python -m build` produces — clamping every member's mtime to
   `SOURCE_DATE_EPOCH`, zeroing uid/gid, blanking uname/gname, and resetting
   the gzip header's own timestamp — before `twine check` and before the
   artifact is attested. It is a small, stdlib-only post-processing step
   rather than a new build-backend dependency on purpose: the one PyPI package
   that already patches this (`setuptools-reproducible`) does so by replacing
   `build-backend` entirely, and its closure could not be hash-pinned the way
   the rest of boost's toolchain is (again, no hash field in
   `[build-system].requires`). `publish.yml` runs it between `python -m build`
   and `twine check dist/*`, so nothing is ever attested un-normalised.

**This applies to releases cut after this fix landed, not to every release
already on PyPI.** Every artifact published before it predates
`SOURCE_DATE_EPOCH` being set in `publish.yml` at all and predates
`scripts/normalize_sdist.py` existing — rebuilding one of those tags with the
recipe below will not reproduce it, because the published bytes were never
built this way to begin with. Check the release date against when this
section last changed (`git log -p -- docs/verifying-releases.md`) before
relying on a match, or before reporting a mismatch as a compromise.

**Rebuilding from the sdist alone**, without cloning the repository, needs one
more value this page can supply but the sdist itself cannot: the sdist carries
no `.git` history, so `git log -1 --format=%ct` — what `publish.yml` uses to
set `SOURCE_DATE_EPOCH` — has nothing to read. Clone the repository at the
release's git tag instead (`git checkout <tag>`, matching what
[verify build provenance](#verify-who-built-it) already points you at) and
compute it the same way `publish.yml` does:

```bash
git checkout <tag>   # the tag this release's attestation names
export SOURCE_DATE_EPOCH=$(git log -1 --format=%ct)
export SETUPTOOLS_SCM_PRETEND_VERSION=<version>   # sdist has no .git either way
python -m build
python3 scripts/normalize_sdist.py dist/*.tar.gz
shasum -a 256 dist/*
```

Compare the reported hashes against the ones on PyPI (`pip download
boost-skill-cli --no-deps -d . && shasum -a 256 *`). A mismatch on a release
built after this fix landed is not automatically a compromise — a different OS
or Python patch version can still shift bytes in ways this project has not
chased down — but on the same platform and toolchain the two should agree.

`build_reproducible` is answered **Met** in
[openssf-badge.md](openssf-badge.md) on that basis: falsifiable per-commit via
`scripts/check_reproducible.py`, going forward from this change.

## Why the ordering in `publish.yml` matters

The workflow attests **after** `twine check` and **before** the PyPI upload, so
the bytes that are signed are exactly the bytes that are published — there is no
window in which an unattested or modified artifact could be substituted. The
build itself runs from `main` at full history depth, with the version derived by
`setuptools-scm` from the git tag rather than from any hand-edited constant.

## If verification fails

Do not install the artifact. Open a
[private vulnerability report](https://github.com/jonnyeclectic/boost/security/advisories/new)
rather than a public issue, and include the file's sha256, where you obtained
it, and the full `gh attestation verify` output. See [SECURITY.md](../SECURITY.md).

## Related

- [`security-design.md`](security-design.md) — the threat model, including
  delivery and supply-chain compromise
- [`dependencies.md`](dependencies.md) — how dependencies are pinned by hash
- [`../MAINTAINERS.md`](../MAINTAINERS.md) — who holds which credential (and why
  the release path holds none)
