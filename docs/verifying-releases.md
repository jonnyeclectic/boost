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

## Can you rebuild it yourself? Partly — the measurement

A reproducible build lets a third party rebuild the artifact from source and
get the same bytes, which is a stronger guarantee than provenance alone:
provenance says *this workflow produced these bytes*, reproducibility says
*and here is how you check that without trusting the workflow*.

boost is **not** fully reproducible today, and this is the measurement rather
than an opinion. Two builds of the same commit, on the same machine and
toolchain, seconds apart:

```bash
export SOURCE_DATE_EPOCH=$(git log -1 --format=%ct)
python -m build --outdir dist-a .
python -m build --outdir dist-b .
shasum -a 256 dist-a/* dist-b/*
```

| Artifact | With `SOURCE_DATE_EPOCH` set | Without |
|---|---|---|
| Wheel (`.whl`) | **identical** | differs |
| Source distribution (`.tar.gz`) | differs | differs |

The wheel is reproducible once `SOURCE_DATE_EPOCH` is set, because
`setuptools` honours it when stamping the zip entries. The sdist is not, and it
is not a setting this project holds: `setuptools` writes each tar member's
real mtime, and the builder's `uid`, `gid` and user name, into the sdist. Two
builds two seconds apart therefore differ in 54 members — every directory, plus
the files generated during the build (`PKG-INFO`, the `.egg-info` set) — and a
build on another machine would differ in the ownership fields as well. The gzip
header carries its own timestamp on top of that.

Two things are still missing before boost could claim this, and both are
recorded rather than hidden:

1. `publish.yml` installs its build tooling unpinned (`pip install build
   twine`), so the toolchain that produced last month's wheel is not
   recoverable from the repository.
2. The sdist needs the mtimes and ownership normalised, which means
   post-processing the tarball or a `setuptools` release that clamps them.

Until both are done, `build_reproducible` is answered **Unmet** in
[openssf-badge.md](openssf-badge.md). Use the provenance attestation above,
which is the guarantee boost does offer.

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
