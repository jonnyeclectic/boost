---
id: openvex
author: "the boost project (https://github.com/jonnyeclectic/boost)"
version: 1
timestamp: "2026-08-28T00:00:00Z"
---
Document-level identity for `docs/vex/openvex.json`, hand-edited the way a
changelog is: bump `version` and set `timestamp` to the date of the change
whenever a statement under `statements/` is added, changed, or removed.
Neither field is computed — `scripts/build_vex.py` deliberately never reads
the wall clock, so `--check` can compare byte-for-byte. This body is prose
for humans editing the file; it is not part of the generated document.
