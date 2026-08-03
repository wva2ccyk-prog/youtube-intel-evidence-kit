# Global Audit Remediation + Independent-Review Corrective Pass

## Summary

Code-level remediation of the global audit findings, **plus a corrective pass addressing every merge-blocking defect found in the independent review** of PR #2. This is not a documentation-only change: runtime behavior, evidence provenance, packaging, schemas, tests, CI, and safety boundaries were fixed and are enforced by regression tests, CI, and a live PR description that matches the implementation.

**Not merged.** Draft opened and returned to ready-for-review only after all checks pass.

## Newly Corrected Merge Blockers (from the independent review)

1. **Opinion-axis majority on the real build path** - `build_topic_collection()` now preserves role multiplicity as `support_role_counts` (role -> claim count); `_dominant_axis()` computes majority from those counts, so 1 supporting + 3 challenging selects `challenging`. End-to-end tests through `build_topic_collection()` cover majority, ties, and permutations.
2. **Cue start/end provenance** - `assemble_segments_to_sentences()` parses structured `start`/`end` (seconds or `mm:ss`), keeps `time_ref` as the legacy start fallback, sets `span_start` = first valid cue start and `span_end` = final cue end (None when no end exists - no fabricated duration), and emits `source_cue_coordinates` per cue that survives ClaimCandidate, ResidualClaimPackage, VideoKnowledgeRecord, and TopicCollection claim/evidence records. `assemble_from_dicts()` propagates speaker/modality/source-hint with configurable keys.
3. **Structured fail-closed input errors** - added `read_required_json` (missing/non-UTF-8/invalid JSON -> InvalidInputError) and segment/hesitation row validation, so 12 malformed-input CLI cases return exit 2 with structured JSON and no traceback.
4. **No synthetic identity in the package command** - `package` now requires non-empty `video_id`, `title`, and `language` (explicit `und` escape hatch) from flags or file metadata; synthetic defaults remain only in demo commands.
5. **Handoff structural + coherence validation** - `write_handoff_bundle()` validates residual-package and analysis-worth structure (schema version, identity, claims, duplicate claim ids) and mutual coherence (matching video id/title, resolving source-trace claim ids) before writing anything; complete handoff requires both artifacts and the manifest records `bundle_completeness: complete`.
6. **Correct source-checkout detection** - `find_source_root()` walks ancestors for `pyproject.toml` + `src/youtube_intel`; `is_source_checkout()`/`is_installed_package()` are unambiguous, and fixture resolution uses the canonical `examples/` tree via an explicit `PACKAGED_TO_EXAMPLES` mapping in source mode.
7. **Installed-wheel `clean` safety** - `clean` requires a detected source checkout and fails closed (exit 2) in a wheel; `--force` can never delete protected source dirs (`src`, `.git`, `tests`, `schemas`, `.github`, `docs`, `scripts`).
8. **Topic input + evidence reference integrity** - non-dict rows are rejected (never silently filtered); claims require non-empty source/text and >=1 evidence id; evidence coordinates are cross-checked against `evidence_ids` and the referenced evidence record; `validate_topic_collection_document` validates built collections (group references, representative membership, counts, coordinates) and is enforced at build time and in the MCP facade.
9. **Schema contract** - `minLength: 1`, `minItems: 1`, `uniqueItems`, `minimum: 1` counts, and `additionalProperties: false` on core objects (topic, status, evidence coordinate, claim/evidence index records).
10. **`doctor` reflects actual health** - computes checks (runtime_resources, gitignore_safety, repository_safety_scripts) and exits 2 when resources or ignore rules are missing; installed mode marks repo-only checks `not_applicable`.
11. **MCP runtime validation** - the TopicCollection facade validates loaded documents with the dependency-free validator; overlay server loads every overlay through `load_validated_operator_overlay` in summary/groups/group_detail/limitations.
12. **Fixture source-of-truth** - explicit `PACKAGED_TO_EXAMPLES` mapping, no ambiguous basename flattening, byte-for-byte parity test, no tracked bytecode.

## Test Additions

End-to-end/CLI tests added for opinion-axis majority, cue timing provenance through every layer, 12 structured malformed-input cases, package identity contract, handoff validation (7 cases), source-checkout/runtime-mode detection, clean safety (15 cases incl. installed-wheel), doctor health (6 cases), 16 topic-integrity negatives, schema contract (10 cases), and MCP runtime validation (12 cases).

## Exact Verification (latest)

- `python -m pytest -W error -q -p no:cacheprovider` -> **343 passed, 0 warnings**
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
