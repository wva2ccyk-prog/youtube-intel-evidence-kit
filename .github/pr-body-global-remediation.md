# Global Audit Remediation + Two Independent-Review Corrective Passes

## Summary

Code-level remediation of the global audit findings, plus **two independent-review corrective passes** addressing every merge-blocking defect found in the reviews. This is not a documentation-only change: runtime behavior, evidence provenance, packaging, schemas, tests, CI, and safety boundaries were fixed and are enforced by regression tests, CI, and a live PR description that matches the implementation.

**Not merged.** Returned to ready-for-review only after all checks pass.

## Second Corrective Pass: Merge-Blocking Defects Fixed

1. **Representative evidence timestamps** - `_make_evidence_record()` now uses the real structured span (`span_start`/`span_end`) as `timestamp_start`/`timestamp_end` with full fractional precision (never rounded), falling back to `time_ref` only for legacy start and keeping end `None` when no real end exists. Values propagate identically into the claim record, `evidence_coordinate`, `evidence_index`, and group coordinates. Cross-layer equality is enforced by tests.
2. **`worth` / `topic-demo` fully fail-closed** - `worth` now strictly validates the primary package, every compare package (indexed in errors, never silently ignored), and run-dir inputs (dir existence, `residual/package.json`, strict optional `metadata.json`). `topic-demo` strictly reads and validates every `video_*.json` (top-level object, video object, non-empty identity never fabricated from filename stems, non-empty segments, per-segment object with non-empty text) and validates `expected_groupings.json` before writing any artifact, so a malformed later source cannot leave a half-written output directory.
3. **Dependency-free TopicCollection validator strengthened** - `validate_topic_collection_document()` now structurally validates claim_index/evidence_index records (non-empty ids, resolving references, coordinate-vs-evidence agreement), declared `video_record_count` consistency, and claim coverage by groups; the MCP facade inherits all of this.
4. **`clean --force` no longer deletes arbitrary content** - only recognized generated-output locations are deletable; `--force` was removed from the CLI and never widens the deletion set, so non-generated and protected repository content cannot be removed.
5. **Handoff `source_trace` validation cannot be bypassed** - every source-trace row must be an object with a non-empty claim_id that resolves to a package claim; malformed/empty rows are rejected with their index.
6. **Source-checkout `topic-demo` resolves canonical `examples/topic_demo`** - `fixture_path()` now resolves directories (including `topic_demo`) to `examples/` in a source checkout instead of the packaged `_fixtures` copy, via the explicit `PACKAGED_TO_EXAMPLES` map.

## Test Additions (second pass)

- `test_representative_timestamps.py` (7): fractional/no-time-ref/legacy timestamps, cross-layer equality, no precision loss, source-checkout topic_demo resolution.
- `test_worth_fail_closed.py` (18): all invalid-package, compare-package, run-dir, and metadata cases.
- `test_topic_demo_fail_closed.py` (17): all malformed/empty/invalid source and expected-grouping cases, one-valid-one-invalid atomicity, success paths.
- `test_clean_safety.py` (+2): non-generated content never deletable via CLI, even with `--force`.
- `test_mcp_runtime_validation.py` (+4): empty source video, empty evidence video, uncovered claim, missing evidence_coordinate.
- `test_handoff_bundle.py` (+3): non-dict/empty source-trace rows rejected.

## Exact Verification (latest)

- `python -m pytest -W error -q -p no:cacheprovider` -> **393 passed, 0 warnings**
- `python scripts/check_encoding.py` -> passed
- `python scripts/public_release_leak_scan.py` -> PASSED
- `python -m compileall -q src tests scripts` -> ok
- `python -m youtube_mcp_handoff.smoke` -> PASSED
- Wheel build -> 12 fixture entries, no tracked bytecode
- Installed-wheel demos (doctor/topic-demo/single-video-demo/hesitation-demo) -> all `ok: true`, `runtime_mode: installed_package`
- Installed-wheel `clean` -> exit 2, `ok: false`, target untouched

## CI Jobs

- `test (3.10)`, `test (3.12)` - source-mode tests, `-W error`, source-mode assertions, malformed CLI smoke
- `wheel-install` - clean wheel build/install, demos, schema validation, installed-wheel `clean` refusal
- Status on latest push: **pass (all 3)**

## Deferred Work (not release blockers for this PR scope)

- **P1-C** Korean high-risk marker false positives (substring matching): tracked in **#3**.
- **P1-D** aside-detector corpus overfitting: tracked in **#4**.
Both remain heuristic/alpha and are clearly disclaimed; issues include user-visible impact and next steps.

## Relationship to PR #1

PR #1 (run-verified audit documentation) remains open and is retained as **historical audit documentation**. This branch's implementation supersedes its prototype-fix guide with run-verified, tested fixes. PR #1 should be closed or explicitly superseded during review; PR #2 is the authoritative implementation.

## Remaining Limitations

- The labeled orchard fixture score is an in-domain regression measurement (0.625 with complete-link vs 0.875 single-link); `expected_groupings.json` ground truth is untouched.
- Korean grouping needs lower thresholds; the public MCP facility remains a read-only stdio facade.
- This is **opinion-terrain evidence tooling, not truth verification**. Synthetic fixtures only for demos.
