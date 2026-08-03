# Global Audit Remediation + Four Independent-Review Corrective Passes

## Summary

Code-level remediation of the global audit findings, plus **four independent-review corrective passes** addressing every merge-blocking defect found in the reviews. Not documentation-only: runtime behavior, evidence provenance, packaging, schemas, tests, CI, and safety boundaries are fixed and enforced by regression tests, CI, and this live PR description, which matches the implementation.

**Not merged.** Returned to ready-for-review only after all checks pass.

## Fourth Corrective Pass: Contract and Fail-Closed Defects Fixed

1. **Exact handoff source-trace timestamp coherence** - the analysis-worth trace can no longer invent a `time_ref` absent from the source claim. When the source claim `time_ref` is `null`, a non-null trace timestamp is rejected; when the source has a timestamp, the trace must carry that exact string (missing, null, non-string, or different values are rejected). No truthiness is used for equality. Covered by public `handoff` CLI tests and `validate_handoff_inputs()` unit tests.
2. **Strict shared structured timestamp parsing** - a single `parse_structured_timestamp()` helper is used by both cue and sentence modes. It rejects booleans, NaN/Infinity (numeric and string forms), negative seconds, malformed strings, and end-earlier-than-start; it preserves fractional precision without rounding. Structured `start`/`end` that are present but invalid always fail; legacy `time_ref` remains a start fallback only.
3. **Non-string package CLI identities rejected** - the public `package` command no longer coerces `video_id`/`title`/`language` with `str()`. A shared `require_nonempty_string()` helper rejects non-string and whitespace-only identity values with `InvalidInputError`; valid Unicode and the explicit `"und"` language remain accepted.
4. **Complete dependency-free TopicCollection contract** - the JSON Schema and the dependency-free runtime validator now agree on the required top-level contract (`video_record_count`/`claim_total` required, `minProperties: 1` on the indexes, `minimum: 0` on timestamps). Source-video rows must contain all documented required fields; evidence and coordinate timestamps/types are independently validated (so two matching invalid values cannot bypass validation); every claim belongs to exactly one group (ungrouped and multiply-grouped rejected); terrain lists/relations/outliers are strictly typed with coherent membership.
5. **Expected-grouping evaluation is intrinsically fail-closed** - `evaluate_topic_collection()` now calls `assert_valid_expected_groupings_document()` up front, so malformed rows can never be silently skipped or produce a score from a reduced set. `must_link` is required (null rejected), unknown fields are rejected, and duplicate/reversed-duplicate/contradictory/same-item pairs are rejected. Covered at both the `topic-demo` file boundary and the direct library API.

## Test Additions (fourth pass)

- `test_expected_groupings_fail_closed.py` (19): missing/null `must_link`, malformed pairs, blank/non-string items, duplicate/reversed-duplicate/contradictory/same-item pairs, unknown fields, invalid thresholds, and direct `evaluate_topic_collection()`/`validate_expected_groupings_document()` rejection.
- `test_topic_demo_fail_closed.py` (+8): missing/null `must_link`, duplicate/reversed/contradictory/same-item pairs, unknown fields, valid populated document.
- `test_mcp_runtime_validation.py` (+24): missing source-video required fields, timestamp string/NaN/Infinity/bool/negative/reversed, numeric `time_ref`, invalid speaker/confidence, identical invalid values across evidence/claim/group coordinates, claim in two groups, malformed/missing terrain lists, duplicate terrain group id, duplicate relation id, relation/outlier claim outside its group, invalid limitations.
- `test_evidence_coordinates.py` (+1): schema/runtime parity over a mutation corpus.

## Exact Verification (latest)

- `python -m pytest -W error -q -p no:cacheprovider` -> **578 passed, 0 warnings**
- `python scripts/check_encoding.py` -> passed
- `python scripts/public_release_leak_scan.py` -> PASSED
- `python -m compileall -q src tests scripts` -> ok
- `python -m youtube_mcp_handoff.smoke` -> PASSED
- Wheel build -> 12 fixture entries, no tracked bytecode
- Installed-wheel demos (doctor/topic-demo/single-video-demo/hesitation-demo) -> all `ok: true`, `runtime_mode: installed_package`
- Installed-wheel `clean` -> exit 2, `ok: false`, target untouched

## Third Corrective Pass: Merge-Blocking Defects Fixed

1. **Default `cue`-mode timestamp provenance** - the default `claim_assembly="cue"` path lost structured `start`/`end` because raw segments were not normalized into `span_start`/`span_end`/`source_cue_coordinates`. A shared `normalize_segment_provenance()` now converts each raw segment into a complete single-cue structure (structured start/end take precedence; `time_ref` is only a legacy start fallback; absent end stays `None`; full fractional precision retained). Sentence mode passes its assembled provenance through unchanged. Both modes reject present-but-unparseable structured timestamps with `InvalidInputError`. Public `package` and `topic-demo` CLI paths are covered; representative coordinates are exactly equal across claim record, `evidence_coordinate`, `evidence_index`, and group coordinates.
2. **Dependency-free TopicCollection/MCP validation completed** - `validate_topic_collection_document()` is rewritten into focused helpers enforcing exact schema identity, non-empty/unique source video ids, required positive-integer counts, claim/evidence index key equality, full evidence-id resolution (not just the coordinate-selected one), claim/evidence coordinate agreement (evidence_id, video_id, timestamps, time_ref, speaker, speaker_confidence, modality), group member-array agreement, complete coordinate coverage, and terrain reference resolution. 25 negative mutations are rejected through the public `load_topic_collection()` loader with `InvalidInputError`.
3. **Expected-grouping fail-closed validation** - `expected_groupings.json` is now strictly validated: `must_link`/`cannot_link` must be exact two-item non-empty string pairs; `threshold` must be int/float (bool rejected), finite (NaN/Infinity rejected), and within `[0, 1]`. The evaluator no longer coerces through `float()`. Malformed documents fail with exit 2, structured `InvalidInputError`, no traceback, and no output artifacts.
4. **Strict residual-package string contracts** - required identity/text fields (`video_id`/`title`/`language`/`claim_id`/`text`) must actually be strings, non-empty after stripping (no `str()` coercion; whitespace-only values rejected); claim IDs are checked against the reserved fallback set; duplicate detection uses normalized values. Both `worth` and `handoff` consume the shared validator and fail closed.
5. **Complete handoff identity and source-trace coherence** - analysis-worth requires a non-empty `video.title`; package/worth `video_id` and `title` must match exactly (missing values are structural errors, no guarded comparisons). Every source-trace row must carry non-empty `claim_id`/`evidence`/`confidence`, resolve to a package claim, be non-duplicated, and agree with the source claim's `time_ref`/`claim_type`/`evidence`/`confidence`. No bundle is written before validation succeeds.

## Test Additions (third pass)

- `test_representative_timestamps.py` (+6): default cue-mode fractional timestamps via `package`/`topic-demo` CLIs, legacy `time_ref`-only, structured-only, invalid timestamp rejection in cue and sentence modes.
- `test_mcp_runtime_validation.py` (+26): wrong schema version, empty topic id/title, empty/duplicate source videos, missing/non-integer/mismatched counts, claim-index key/uid mismatch, empty claim text, secondary dangling & duplicate evidence ids, evidence-index key/id mismatch, coordinate time_ref/speaker_confidence/modality mismatch, member-array mismatch, empty group evidence ids/coordinates, unlisted/duplicate coordinate ids, terrain/disagreement/outlier dangling ids.
- `test_topic_demo_fail_closed.py` (+17): threshold string/null/bool/out-of-range/NaN/Infinity, must_link/cannot_link scalar and malformed rows, empty/non-string pair items, valid success.
- `test_package_strict_strings.py` (17): whitespace-only and non-string identity/text values, reserved claim id, whitespace-normalized duplicates, valid unicode + `und`, through `worth` and `handoff` CLIs.
- `test_handoff_bundle.py` (+13): missing/blank worth title, title mismatch, whitespace/duplicate trace claim ids, missing/invalid time_ref, missing/blank evidence and confidence, trace time/evidence/confidence mismatch with source claim, valid complete trace.

## CI Jobs

- `test (3.10)`, `test (3.12)` - source-mode tests, `-W error`, source-mode assertions, extended malformed CLI smoke (cue-mode timestamps, worth strict strings, expected-grouping threshold, handoff trace, MCP validator, handoff fabricated-timestamp rejection, package non-string identity rejection, boolean/NaN timestamp rejection, expected-groupings missing `must_link` rejection, MCP loader matching-invalid-coordinate / multi-group / missing-source-field rejection)
- `wheel-install` - clean wheel build/install, demos, schema validation, installed-wheel `clean` refusal
- Status on latest push: **pass (all 3)**

## Pull Request Status

- **PR #2 remains open and unmerged.**
- **PR #1 was not modified or merged.**
- No approval was self-issued; the branch is ready for another independent review.
- Final head SHA: `80888fb5c8eace94361285e6701d859af96cdb82`
- Latest Actions run: `30797404768` — `test (3.10)` SUCCESS, `test (3.12)` SUCCESS, `wheel-install` SUCCESS

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

