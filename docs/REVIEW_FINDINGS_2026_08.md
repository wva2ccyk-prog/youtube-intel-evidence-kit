# Review Findings — 2026-08 Global Audit

This file records an independent, evidence-based audit of the repository. It was
produced by running the package (editable install and a clean wheel install),
executing the documented validation commands, validating generated artifacts
against the shipped schemas, and probing the grouping layer with inputs outside
the synthetic orchard fixture. Documentation claims were treated as claims to be
verified, not as facts.

Audit environment: macOS, CPython 3.14.6, `pip install -e .[dev]`, commit
`41f504d` on `main`.

Step-by-step remediation for everything below, with verified diffs, is in
`REVIEW_FIX_GUIDE_2026_08.md`.

## What Holds Up

These claims were checked and are accurate:

- `python -m pytest -q` passes: **148 passed** on a clean checkout.
- `python -m youtube_mcp_handoff.smoke` passes (`Status: PASSED`).
- `python scripts/check_encoding.py` passes.
- The CI job order in `.github/workflows/ci.yml` reproduces green locally
  (clean, leak scan, encoding, pytest, compileall, smoke).
- Generated `topic_collection.json` and all three `*_knowledge_record.json`
  files validate with zero errors against `schemas/topic_collection.schema.json`
  and `schemas/video_knowledge_record.schema.json` under
  `Draft202012Validator`. Both schema files are themselves valid Draft 2020-12.
- The package genuinely has no runtime dependencies and no media-acquisition
  path: no downloader, scraper, or transcoder import exists in `src/`.
- Truth-neutrality is enforced structurally, not only in prose:
  `truth_status: not_evaluated` and `fact_check_status: not_performed` are
  schema `const` values, and `hesitation_score` is `null` by design.
- The MCP layer is described accurately as a read-only facade; the wording does
  not overclaim MCP compliance.
- `sentence_assembly` behaves as `docs/CLAIM_ASSEMBLY.md` illustrates: the
  documented Korean five-cue example collapses to the two documented sentence
  units with correct cue indices and time spans.

## P1 — Correctness Defects

### P1-1 A wheel install silently produces an empty TopicCollection

Reproduced: build a wheel, install it into a clean virtualenv, then run
`youtube-intel topic-demo --out <dir>`. The command exits `0` and reports
`"ok": true`, but the output is empty: `claim_group_count: 0`,
`opinion_group_warnings: ["opinion_group_builder_no_claim_groups"]`, and no
video records are written.

Cause: `cli._repo_root()` returns `Path(__file__).resolve().parents[2]`, which is
a source-tree assumption. In a wheel install that resolves to
`<venv>/lib/python3.x`, so `examples/topic_demo` does not exist.
`build_topic_demo_from_segments` then globs `video_*.json` in a non-existent
directory, gets zero files, and builds a collection from an empty record list
without complaint. `examples/` is not declared as package data, so the fixtures
are absent from the wheel entirely (confirmed by listing wheel contents).

Why this ranks first: the README quickstart is the primary proof of the
project's thesis, and the failure mode is a silent empty success — the exact
failure class the project's own doctrine ("preserve uncertainty, do not
manufacture it") exists to prevent. An empty terrain reported as `ok: true` is a
manufactured-certainty bug.

The same root cause makes `youtube-intel single-video-demo` exit `1` with an
unhandled `ValueError` traceback from `_load_segment_input`, and makes
`youtube-intel doctor` report `synthetic_demo_available: false`,
`synthetic_topic_demo_available: false`, `leak_scan_script_available: false`, and
`all_required_ignores_present: false` — that is, `doctor` reports a broken
posture for a correctly installed package.

Fix direction (pick one, then make it consistent):

1. Ship the fixtures as package data (`examples/topic_demo/*.json`,
   `examples/synthetic_*.json`) and resolve them with
   `importlib.resources.files("youtube_intel")` instead of `parents[2]`; or
2. Keep fixtures source-only, but detect the non-source-tree case explicitly and
   fail loudly with an actionable message.

Independently of that choice: **zero input records must never return
`ok: true`.** Add a guard in `build_topic_demo_from_segments` that fails when no
`video_*.json` files are found, and make `doctor` distinguish "installed from a
wheel, repo checks not applicable" from "posture broken". `doctor` currently
treats an unavailable `.gitignore` check as a safety failure; gate the repo-only
checks on whether a source tree was detected.

### P1-2 The README validation sequence fails on a real run

The README instructs, in this order:

```bash
python -m pytest -q tests
python -m youtube_mcp_handoff.smoke
python scripts/public_release_leak_scan.py
```

Run verbatim, the third command **exits 1** with 43 violations — every one a
`__pycache__/*.pyc` artifact created by the pytest run two lines earlier.

CI does not hit this because it runs `scripts/clean_generated_artifacts.py`
first, and the workflow carries a comment explaining exactly this ordering
constraint. That knowledge never reached `README.md`, `SMOKE_TESTS.md`, or
`PACKAGING_CLOSEOUT.md` (whose "Validation Commands" block has the same latent
failure). The result is a contributor-facing footgun: the documented happy path
produces a red failure on a healthy repository.

Fix: document the clean step on every surface that lists the leak scan, or make
the leak scan skip bytecode caches while keeping the tracked-file check CI relies
on. Either is acceptable; the surfaces must agree.

### P1-3 `.gitignore` blanket-ignores extensions the project needs

`.gitignore` ignores `*.jsonl`, `*.html`, `*.log`, and all image extensions to
keep private artifacts out, then re-includes `!examples/**/*.json`,
`!docs/**/*.md`, `!tests/**/*.py`.

Two consequences worth deciding deliberately:

- Any future fixture, doc asset, diagram, or screenshot outside a whitelisted
  path is silently untracked. A contributor adding `docs/img/flow.png` sees it
  vanish from `git status` with no error.
- `*.vtt` is ignored with a single-file exception for
  `examples/synthetic_transcript.vtt`, so a second synthetic caption fixture will
  silently not be tracked.

Denylist-plus-narrow-allowlist is defensible for a privacy-first repo, but it
should be an explicit documented decision with a stated procedure for adding a
new tracked asset, not something contributors discover by accident.

## P2 — Overstated Capability

### P2-1 The grouping layer is fixture-tuned, and the docs do not say so

`topic_collection.py` contains a hardcoded `SYNONYM_MAP` of roughly 40 entries
plus four token-expansion rules whose vocabulary comes directly from the
synthetic orchard fixture: `irrigation -> water`, `subsidy -> policy`,
`salinity -> soil`, `calibration -> maintenance`, and expansions such as
`{water, saving, 20, percent, guarantee} -> add {water, saving}` and
`{yield, software, soil, cause, prove} -> add {yield, causality}`.
`_group_label()` likewise hardcodes display strings such as
`"Water-savings claim"` and `"Sensor reliability / maintenance risk"`.

The reported fixture score (`pair_agreement 0.875`, `status: pass`) is therefore
measured on the same domain the synonym table was written for. It is a
regression guard, not evidence of generalization, and the README phrase "a small
labeled fixture score" does not convey that.

Verified on out-of-domain English input: two claims a human would group ("The new
tariff raised laptop prices by 15 percent" vs. "Laptop prices did not rise
because of the tariff") score `0.435`, above the `0.20` threshold, so that pair
survives. But it survives on English morphology and shared tokens, not on the
synonym layer, which contributes nothing outside the orchard domain.

Action: label the orchard vocabulary as fixture scaffolding in code comments,
state in `README.md` and `ROADMAP.md` that the score is in-domain, and add at
least one fixture from an unrelated domain so the number carries information.
Longer term, move the synonym table out of module scope into a loadable,
per-topic resource.

### P2-2 "Korean-aware" is true for assembly and false for grouping

`docs/CLAIM_ASSEMBLY.md` and the changelog advertise Korean-aware handling, and
`sentence_assembly` earns it: sentence-final endings are handled correctly,
verified against the documented example.

The grouping layer does not. Measured directly against
`youtube_intel.topic_collection`:

| Korean input pair | Similarity | Expected |
|---|---|---|
| `이 정책은 청년 고용을 늘린다` vs `청년 고용이 늘어난다고 보기 어렵다` | `0.0` | should group (same proposition, opposed stance) |
| `이 센서는 물 사용량을 20퍼센트 줄인다` vs `센서 도입으로 물 사용량이 20퍼센트 감소했다` | `0.1911` | should group, falls **below** the `0.20` threshold |

Cause: `_normalize_claim_tokens` splits on whitespace and applies English suffix
stripping. Korean particles are never separated, so `고용을` and `고용이` are
distinct tokens. The `len(token) < 3` filter then discards every two-syllable
Korean word outright: `고용 증가`, `정책 효과`, `물가 상승`, and `센서 오차` all
normalize to `[]` — an empty token set, and similarity `0.0` against everything.

This is the largest gap relative to stated intent. `docs/PUBLIC_THESIS.md` names
Korean-heavy material (local development, policy commentary, field reports) as
the motivating use case, and `analysis_worth` ships Korean marker detection, so a
Korean operator reaches a grouping layer that cannot group their claims, with no
warning anywhere in the output.

Minimum honest fix now: document the limitation in `README.md`,
`docs/CLAIM_ASSEMBLY.md`, and `TOPIC_LIMITATIONS` (which is surfaced in every
handoff bundle), and make the length filter language-aware so it stops silently
emptying CJK token sets. Real fix: particle-aware Korean tokenization (a
deterministic suffix-strip list, no new dependency) plus a Korean fixture under
`examples/`, tracked as an explicit roadmap item.

### P2-3 The plugin registry advertises modules that do not exist here

`youtube_plugins/registry.py` lists `transcribe_critic` ->
`youtube_external_bridge.transcribe_critic_bridge` and `codex_review` ->
`youtube_model_flow.codex_review_pack`. Neither module exists in this
repository; `youtube_external_bridge` is not even a package here, so `find_spec`
raises `ModuleNotFoundError` (caught, so `doctor` still runs).

These are private-tree references leaking into the public surface as
permanently-unavailable entries. Either drop them from `PLUGIN_SPECS` or mark
them explicitly as external/private integrations so `doctor` output is not
misleading noise.

### P2-5 Short Korean markers match inside longer compounds

Found while validating the Korean tokenization fix, so it is not in the original
finding set. `claim_axes._scan` does unconditional substring matching, and the
`medical_advice` marker `용량` ("dosage") matches inside `사용량` ("usage
volume"):

| Input | Classified as |
|---|---|
| `이 센서를 도입하면 물 사용량을 20퍼센트 줄일 수 있습니다` | `medical_advice` |
| `서버 사용량이 급증했다` | `medical_advice` |
| `이 배터리는 용량이 크다` | `medical_advice` |
| `이 앱의 보안 설계를 설명한다` | `product_recommendation` |

This is not cosmetic. `content_type` feeds `HIGH_VALUE_TYPES` in
`analysis_worth.py:243`, and `medical_advice` is a member, so a misclassified
irrigation claim inflates the high-value count and changes cost-gate output —
the gate that decides whether to spend on ASR, OCR, or source verification. It
also leaks into operator-visible labels: a Korean fixture produced the group
label `"센서 Medical Advice 도입 사용량"`, which is how the bug surfaced.

`_CONTENT_MARKERS` holds many other short entries (`보안`, `분류`, `회귀`,
`지문`, `무게`) with the same mid-compound exposure, so the three observed cases
are unlikely to be the only ones. Fix direction and a verified patch are in the
fix guide; the durable fix is to require two independent markers before assigning
a high-risk `content_type`, since single-marker matches are where false positives
concentrate.

### P2-4 Two dead code paths

- `youtube_ops_cli.py` exists twice: the root copy inserts `src` into
  `sys.path`; `src/youtube_ops_cli.py` (the one actually shipped via
  `py-modules`) does not. Neither is referenced by any entry point, document, or
  test — the `youtube-ops` console script points at `youtube_intel.cli:main`
  directly. Delete both, or keep one and document it.
- `youtube_quality/gate.py` and `youtube_model_flow/quality_gate.py` are
  reachable only from `tests/test_quality_gate_runtime_contract.py`. No CLI
  command, no document, and no other module imports them, yet
  `docs/BOOTSTRAP_PROMPT.md` tells an agent to "run the quality gate before final
  report creation". Either wire it to a CLI subcommand or state that it is a
  library-only contract.

## P3 — Documentation Accuracy

- `README.md` and `SMOKE_TESTS.md` give `. .venv/Scripts/activate`, a Windows
  path, as the primary activation line. On macOS/Linux the correct form is
  `. .venv/bin/activate`. The README inline comment then labels the Windows form
  as the PowerShell alternative, so no line works on POSIX.
- `SMOKE_TESTS.md` promises `2 passed` for `tests/test_public_smoke.py`.
  Currently accurate (verified), but a hardcoded count drifts the moment a smoke
  test is added. Prefer "passes".
- Status strings disagree across documents for the same commit: `README.md` says
  `alpha_cross_video_evidence_contract_with_deterministic_grouping_demo`;
  `PACKAGING_CLOSEOUT.md` and `docs/SCOPE_BOUNDARY.md` say
  `alpha_cross_video_evidence_contract_pending_public_repo` (stale — the repo is
  public); `docs/PUBLIC_THESIS.md` and `PUBLICATION_RISK_REVIEW.md` say
  `public_oss_candidate_with_synthetic_topic_collection_and_mcp_handoff`. Pick
  one canonical status, keep it in one place, and have the others point to it.
- `docs/PUBLIC_RELEASE_CHECKLIST.md` still shows `[ ] GitHub repo is public`
  unchecked, though the repository is public.
- `CHANGELOG.md` links a `v0.1.0` compare URL and release URL, but no git tag and
  no GitHub release exist (`git ls-remote --tags origin` returns nothing). Both
  links are dead. Cut the `v0.1.0` tag, or drop the link block until you do.
- `PACKAGING_CLOSEOUT.md` and `docs/mcp_handoff/CODEX_USAGE.md` lead with
  `youtube-intel demo`, the deprecated alias, rather than `single-video-demo`.

## Recommended Order Of Work

1. P1-1: make fixture resolution install-safe and make empty output fail loudly.
   This is the only defect that breaks a user's first five minutes.
2. P1-2: reconcile the documented validation sequence with CI.
3. P2-2: document the Korean grouping limitation in `TOPIC_LIMITATIONS` and the
   README, then fix the CJK length filter.
4. P2-1: mark the orchard synonym table as fixture scaffolding and add an
   out-of-domain fixture.
5. P3: single canonical status string, fix the activation lines, cut a `v0.1.0`
   tag or drop the dead links.
6. P2-3 and P2-4: prune private-tree plugin references and dead modules.

`REVIEW_FIX_GUIDE_2026_08.md` breaks this into nine independently committable
tasks with verified diffs, measured before/after numbers, and the tests to add
for each.

## Audit Method

```bash
# clean checkout, editable install
python3 -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"

# documented validation, CI order
python scripts/clean_generated_artifacts.py
python scripts/public_release_leak_scan.py
python scripts/check_encoding.py
python -m pytest -q -p no:cacheprovider
python -m compileall -q src tests scripts
python -m youtube_mcp_handoff.smoke

# README order (reproduces P1-2)
python -m pytest -q tests && python scripts/public_release_leak_scan.py

# clean wheel install (reproduces P1-1)
python -m build --wheel
python -m venv vclean && vclean/bin/python -m pip install dist/*.whl
vclean/bin/youtube-intel doctor
vclean/bin/youtube-intel topic-demo --out out_topic
vclean/bin/youtube-intel single-video-demo --out out_sv
```

Schema conformance was checked with `jsonschema.Draft202012Validator` against
generated artifacts. Grouping behaviour was probed by calling
`youtube_intel.topic_collection` internals directly with out-of-domain English
and Korean claim pairs.
