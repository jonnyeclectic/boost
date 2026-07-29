---
id: sbom-declares-the-wrong-version
board: code
section: trust
status: shipped
category: Supply chain · Bug
complexity: S
impact: High
wow: 5
note: fixed — release v1.0.278's SBOM declared 1.0.277; the version is now pinned to the tag
order: 68
owner: loop/sbom-tag-version
pr:
title: The SBOM can declare a different version than the release it is attached to
---
<code>sbom.yml</code> builds each released tag separately so that every release gets an SBOM
describing <em>its own</em> version. It does that by checking the tag out:
<code>git checkout --detach "refs/tags/$TAG"</code>. The premise is wrong.
<b>setuptools-scm derives the version from the commit, not from the ref used to reach it</b>, so
when one commit carries two tags every checkout resolves to the same version — whichever one
<code>git describe</code> picks, which is not the highest.

Measured against the real repository, detached at each tag in turn:

<code>checked out v1.0.278 -&gt; setuptools-scm says: 1.0.277</code><br>
<code>checked out v1.0.277 -&gt; setuptools-scm says: 1.0.277</code>

And confirmed in production rather than in a fixture — the published asset on
<code>v1.0.278</code>, downloaded from the release, contains
<code>{"name": "boost-skill-cli", "version": "1.0.277"}</code>. <b>The SBOM attached to release
v1.0.278 describes v1.0.277.</b> A consumer resolving that release's bill of materials gets a
document for a different version, which is precisely the trust property an SBOM exists to provide.

The blast radius is bounded by how often one commit cuts two releases, which
<code>one-commit-can-cut-two-releases</code> documents happening three times so far
(<code>246</code>/<code>247</code>, <code>248</code>/<code>249</code>, <code>277</code>/<code>278</code>).
Every duplicate pair mislabels one of its two SBOMs. It is <em>not</em> latent in
<code>publish.yml</code>, which builds the PyPI dist: that job checks out before the sibling run's
tag exists, so it happens to resolve correctly — all 281 PyPI versions are present and correctly
numbered. The defect is specific to the job that runs <em>after</em> both tags are in place.

<b>Shipped.</b> The build now pins the version to the tag it is building
(<code>SETUPTOOLS_SCM_PRETEND_VERSION_FOR_BOOST_SKILL_CLI="${TAG#v}"</code>) and then asserts the
wheel it produced carries that version, so a package rename — which would silently unhook the
scoped variable and restore the bug — fails the job instead of shipping a mislabelled document.
Verified both ways against the live repository: without the pin, <code>v1.0.278</code> resolves to
<code>1.0.277</code>; with it, <code>1.0.278</code>.

The same exercise settled the other thing this workflow had never proven: the multi-tag loop
itself. Both <code>run:</code> blocks were extracted verbatim from the YAML and driven against a
fixture repository with two tags on one commit, with <code>gh</code> and the build toolchain
stubbed. Resolution returns both tags newest-first, the loop iterates both, and it issues a
separate <code>upload</code> and a separate post-upload <code>view</code> assertion per tag. That
path had never executed in production — every commit since it shipped has carried exactly one tag.
