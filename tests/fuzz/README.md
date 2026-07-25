# Fuzz targets

Coverage-guided fuzzing of boost's hand-rolled parsers, via
[atheris](https://github.com/google/atheris) (Python bindings for libFuzzer).

| Target | Covers |
|---|---|
| `fuzz_frontmatter.py` | `core/frontmatter.parse` — every skill, rule and workflow boost indexes |
| `fuzz_registry.py` | `core/registry.parse_spec`, plus `secretscan`/`injectscan`/`semver_gt` over untrusted text |

## Why these parsers

Both take input boost does not control. A tapped repository is a third party's
Markdown, and a tap spec is whatever the user types. Both parsers are hand-rolled
— `frontmatter` is a stdlib-only YAML *subset*, not PyYAML — so no upstream
project's fuzzing covers them.

## It has already paid for itself

The frontmatter harness found that numeric coercion was **lossy**:

```yaml
version: 1.10     # ten patch releases past 1.1
```

`float("1.10")` is `1.1`, and `str(1.1)` is `"1.1"`. So boost read a skill
published at 1.10 as 1.1, compared it as *older* than 1.9, and never offered the
update — `boost outdated` reported "everything up to date" while the tap was nine
releases ahead. Leading zeros (`007` → `7`) and exponents (`1e5` → `100000.0`)
corrupted identically.

Fixed in `frontmatter._scalar`: a number is coerced only when `str()` of the
result gives back exactly what the author wrote. The seed that found it is
committed as `corpus/frontmatter/02-lossy-version.md`.

Note which invariant caught it. Asserting "`parse` doesn't crash" would have
missed it entirely — the parser never crashed. So would round-tripping through
`dump`, because the wrong value is *stable* under a round trip. The property has
to compare the parsed value against the **source text**, and the first draft of
this harness got that wrong; `test_fuzz_targets.py` now pins that the invariant
fails on the old behavior.

## Running

```bash
make fuzz                     # 30s per target (default)
FUZZ_SECONDS=300 make fuzz    # longer

# directly, with libFuzzer flags
python3 tests/fuzz/fuzz_frontmatter.py tests/fuzz/corpus/frontmatter \
    -max_total_time=60 -artifact_prefix=/tmp/
```

Without atheris installed each target runs its seed corpus and exits 0 — atheris
publishes **manylinux wheels only** (cp312/cp313/cp314), so a real fuzzing run
needs Linux and Python ≥ 3.12. No clang or LLVM build is required.

## Where each layer runs

| Layer | Where | Blocking? |
|---|---|---|
| Seeds through every invariant | `tests/unit/test_fuzz_targets.py`, the normal suite | **yes** |
| Coverage-guided run | `.github/workflows/fuzz.yml` — weekly, or the `check-fuzz` PR label | no |

The fuzzing run is deliberately **not** a merge gate: a fuzzer is a search, and a
timed search is not reproducible enough to sit in front of a merge. The cheap
deterministic half is, which is what keeps a rotted harness from passing
silently between scheduled runs. A crash uploads the reproducing input as a
30-day artifact and fails the run, so the scheduled-failure alert fires.

## Adding a target

1. Write `fuzz_<name>.py` exporting `check(text)` and `fuzz_one_input(bytes)`,
   with the same no-atheris seed-corpus fallback.
2. Seed `corpus/<name>/` — include a regression seed for every bug it finds.
3. Add `<name>` to `TARGETS` in `tests/unit/test_fuzz_targets.py` and to the
   matrix in `.github/workflows/fuzz.yml`.

Assert **properties**, not just absence of crashes. "It didn't raise" is the
weakest possible invariant, and the bug above proves it: the parser never raised.

## OSS-Fuzz

These targets follow the [OSS-Fuzz Python
contract](https://google.github.io/oss-fuzz/getting-started/new-project-guide/python-lang/)
— module-level `fuzz_one_input(data: bytes)` plus `atheris.Setup`/`atheris.Fuzz`
under `__main__` — so an OSS-Fuzz `build.sh` needs only
`compile_python_fuzzer tests/fuzz/fuzz_frontmatter.py`. boost has to be accepted
into OSS-Fuzz first (it needs a maintained, reasonably-used OSS project and a
security contact); until then the scheduled workflow provides the same coverage
guidance at a smaller scale.
