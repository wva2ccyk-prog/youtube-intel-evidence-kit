# Global Audit Remediation: Evidence Integrity, Installed-Package Behavior, and Fail-Closed Validation

## Summary

Code-level remediation of the global audit findings. This is **not** a documentation-only change: runtime behavior, evidence provenance, packaging, schemas, tests, CI, and safety boundaries were all fixed. It builds on **PR #1** (run-verified audit, `review/global-audit-2026-08`) but does not merge it as-is; the implementation branch is based on current `main` and incorporates additional critical defects found during the fix.

## Root Causes Fixed

1. **Speaker/timestamp/modality provenance loss (P0-A)** - `assemble_segments_to_sentences()` could merge cues across speaker/modality/source-hint boundaries and attribute the merged text to the first speaker. Speaker, modality, and source-hint changes now force an assembly boundary; assembled units and serialized claims carry `cue_indices`, `source_time_refs`, `span_start`, `span_end`, `speaker`, `modality`, `source_hint`.
2. **Input record mutation (P0-B)** - `build_topic_collection()` wrote `claim_group_key`/`claim_group_label`/`normalized_tokens` onto caller dicts and hashed after mutation. Now works on deep copies; `input_record_hashes` are computed from original inputs before any transformation.
3. **Duplicate/dangling identifier overwrite (P0-C)** - `videos[video_id]`, `claim_index[claim_uid]`, `evidence_index[evidence_id]` silently overwrote duplicates; fallback IDs (`unknown-video`, etc.) made collisions easy. The build now fails closed with `EvidenceIntegrityError`.
4. **Broad empty-input success paths (P0-D)** - `topic-demo`, `package`, `worth`, `handoff`, `hesitation-demo`, and the TopicCollection MCP facade returned successful artifacts for missing/empty/malformed inputs. All now fail with structured `InvalidInputError` (exit code 2), and no final manifest is written after a failed source validation.
5. **Single-video handoff manifest mismatch (P0-E)** - `write_handoff_bundle()` wrote `handoff_manifest.json` before adding its own path to the in-memory `paths`; returned and on-disk manifests were different. The complete manifest is now constructed first, then written.
6. **Cluster bridge chaining / input-order dependence (P1-A)** - the single-link rule let weak bridges (A~B~C) chain unrelated claims, and `_dominant_axis()` picked the first enum axis. Both clusterers now use a deterministic complete-link cohesion rule with sorted input, record `grouping_note`/`cohesion_min_similarity`, and opinion-axis dominance is decided by actual role counts with deterministic ties.
7. **Misleading evidence-coordinate field (P1-B)** - group-level `evidence_coordinates` contained evidence ID strings. Now a real array of coordinate objects (`evidence_id`, `video_id`, `timestamp_start`, `timestamp_end`, `time_ref`, `speaker`, `speaker_confidence`, `modality`), enforced by a strict schema (`additionalProperties: false`, non-empty IDs, unique IDs, `minItems`).
8. **Unsafe `clean` command (P1-F)** - arbitrary paths could be `rmtree`'d. Now repository-bound and fail-closed (root/home/repo-root/parent/outside/symlink-escape refused), with `--dry-run` and `--force` for non-generated paths.
9. **Leak-scan extension gaps + untracked denylist enforcement (P1-G)** - now prefers `git ls-files -z`, scans all text-decodable tracked files (including `.env*`, `.sh`, `.ini`, `.cfg`, `.jsonl`, `.html`, extensionless), fails if local denylist files are tracked, and never skips a file merely because UTF-8 decode fails (decode-with-replacement + NUL-byte binary filter).
10. **Fixtures absent from wheel / `_repo_root()` source-checkout assumption (P1-H)** - fixtures are packaged under `src/youtube_intel/_fixtures/`, resolved via `importlib.resources` with a source-checkout fallback; `doctor` reports `runtime_mode` (`source_checkout` / `installed_package` / `missing_resources`).
11. **Hesitation word-count mismatch (P1-E)** - `word_count` was based on the raw input list while pause analysis used only timestamp-valid rows. Now validity/word count are based on normalized valid rows; malformed rows are tracked explicitly; negative/reversed/zero-duration/overlapping timestamps are rejected or reported; claims with insufficient valid timestamps are `insufficient_words`, never clean speech.

## User-Visible Behavior Changes

- `topic-demo`, `package`, `worth`, `handoff`, `hesitation-demo` now **fail closed** (exit 2, structured `{"ok": false, "error": "InvalidInputError", ...}`) on empty/malformed/inconsistent inputs.
- `clean` refuses dangerous paths (filesystem root, home, repo root, outside-workspace, symlink escapes), requires `--force` for non-generated repo paths, and supports `--dry-run`.
- `doctor` reports `runtime_mode`.
- Demos work from an installed wheel.

## Schema Changes

- `topic_collection.schema.json`: `evidence_coordinates` is now `items: {$ref: evidenceCoordinate}`; new `evidenceCoordinate` definition (required fields, `additionalProperties: false`, `minLength: 1` IDs, `minItems: 1` modality); `evidence_ids` unique; `claimIndexRecord` uses the coordinate ref; `disagreementRelation.relation_type` adds `opposing_stances_pair`.

## Test Additions

- `tests/test_sentence_assembly.py`, `tests/test_claim_provenance.py` (P0-A)
- `tests/test_topic_input_immutability.py` (P0-B)
- `tests/test_identifier_integrity.py` (P0-C)
- `tests/test_fail_closed_inputs.py`, `tests/test_handoff_bundle.py`, hesitation CLI fail-closed tests (P0-D/P0-E)
- `tests/test_clustering_determinism.py` (P1-A)
- `tests/test_evidence_coordinates.py` (P1-B)
- hesitation timestamp validation tests (P1-E)
- `tests/test_clean_safety.py` (P1-F)
- expanded `tests/test_public_release_leak_scan.py` (P1-G)
- `tests/test_fixture_parity.py` (P1-H byte-for-byte sync + runtime mode)
## Wheel-Install Verification

Built `dist/youtube_intel_evidence_kit-0.1.0-py3-none-any.whl`, installed into a clean venv (`/tmp/youtube-intel-wheel-test`), and ran (all under `runtime_mode: installed_package`):

- `youtube-intel doctor` - ok, demos available
- `youtube-intel topic-demo` - 6 groups, artifacts non-empty
- `youtube-intel single-video-demo` - ok, `analysis_worth: yes`
- `youtube-intel hesitation-demo` - ok, 4 claims / 3 candidates

## Security and Destructive-Operation Hardening

- `clean`: path resolution, boundary checks, symlink-escape rejection, dry-run, `--force` gate, structured refusal that deletes nothing.
- Leak scan: tracked-file scanning, local denylist tracking failure, gitignore enforcement.
- No runtime dependencies added; the deterministic core remains dependency-free.

## Before/After Examples

**Before:** `youtube-intel topic-demo --topic-dir /tmp/empty` wrote a manifest with 0 groups and `ok: true`.
**After:** structured `ok: false`, `InvalidInputError`, exit 2, no manifest written.

**Before:** group `evidence_coordinates: ["e1", "e2"]`.
**After:** `[{"evidence_id": "e1", "video_id": "...", "timestamp_start": ..., ...}]`.

**Before:** single-video returned manifest != on-disk `handoff_manifest.json`.
**After:** `json.loads(manifest_path.read_text()) == returned_manifest` (new regression test).

## Known Remaining Limitations

- The labeled orchard fixture score is an **in-domain regression measurement**, not a benchmark: the must-link labels encode semantic topic relatedness while the alpha clusterer uses lexical normalized similarity. The complete-link cohesion rule deliberately separates weakly bridged claims, so the fixture score moved from 0.875 (single-link, bridge chaining) to ~0.625; `expected_groupings.json` ground truth is left untouched.
- Korean normalized similarity runs lower than English (no space-delimited tokenization benefit); Korean grouping may require an explicit lower threshold.
- The public MCP facility remains a read-only stdio facade, not a full MCP server.

## Relationship to PR #1

PR #1 (`Add run-verified audit plus prototype-verified fix guide`) remains open and is referenced for its audit scope. This branch fixes the implementation defects that PR #1's documentation identified plus additional defects found during the work. PR #1 is intentionally **not** automatically closed; its documentation can be superseded/incorporated during review.

## Verification Commands

```bash
python -m pytest -q -p no:cacheprovider        # 240 passed
python scripts/check_encoding.py               # passed
python scripts/public_release_leak_scan.py     # PASSED
python -m compileall -q src tests scripts      # ok
python -m youtube_mcp_handoff.smoke            # PASSED
python -m build --wheel && inspect fixtures    # 12 fixture entries, no __pycache__
```
