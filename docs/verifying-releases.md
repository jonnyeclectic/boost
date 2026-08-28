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
