# Fix Guide — 2026-08 Audit Findings

Companion to `REVIEW_FINDINGS_2026_08.md`. That file says what is broken and
why; this file says how to fix it, in enough detail that a different engineer or
agent can pick up any single item without re-deriving the analysis.

**Every code change below was prototyped and verified before being written
down.** The diffs are real, not sketches: they were applied to a scratch copy of
the tree at commit `41f504d`, the suite was re-run after each one (148 passed
throughout), and the before/after numbers quoted are measured output. What is
*not* included is any change to committed tests — adding those is part of the
work, and each task states which tests to add.

Verification environment: macOS, CPython 3.14.6.

## How to use this guide

Each task is independent and separately committable, with one exception noted in
Task 2. Tasks are ordered by user impact, not by size.

| Task | Fixes | Size | Risk |
|---|---|---|---|
| 1. Package the fixtures | P1-1 | medium | low |
| 2. Fail loudly on empty input | P1-1 | small | low |
| 3. Fix `doctor` for installed packages | P1-1 | small | low |
| 4. Reconcile the validation sequence | P1-2 | small | none |
| 5. Korean tokenization | P2-2 | medium | medium |
| 6. Korean marker false positives | new (P2-5) | small | medium |
| 7. Disclose limits, label scaffolding | P2-1, P2-2 | small | none |
| 8. Documentation cleanup | P3 | small | none |
| 9. Prune dead surfaces | P2-3, P2-4 | small | low |

Definition of done for every task: `python scripts/clean_generated_artifacts.py`
then `python -m pytest -q` is green, plus the task's own acceptance check.

---

## Task 1 — Ship the synthetic fixtures as package data

**Fixes:** the root cause of P1-1. Without this, tasks 2 and 3 only convert a
silent wrong answer into a loud failure; they do not make the demo work.

**Problem recap.** `cli._repo_root()` is `Path(__file__).resolve().parents[2]`.
From a source checkout that is the repo root. From an installed wheel it is
`<venv>/lib/python3.x`, where no `examples/` exists. The fixtures are not
declared as package data, so they are absent from the wheel entirely.

**Design decision.** Keep `examples/` at the repo root as the canonical,
human-browsable copy — it is referenced by nine docs and by `README.md`'s
quickstart, and moving it would churn all of them. Ship a copy inside the package
as `youtube_intel/_fixtures`, and resolve through a helper that prefers the
source tree and falls back to the packaged copy.

The alternative — moving `examples/` under `src/youtube_intel/` and leaving a
symlink or a docs redirect — was rejected: it breaks every existing doc path and
makes the public demo inputs less discoverable for a project whose fixtures are
part of its safety story.

### 1a. New module `src/youtube_intel/fixtures.py`

Verified working, 51 lines:

```python
from __future__ import annotations

"""Locate bundled synthetic fixtures in both source-tree and installed layouts.

The public demos read fixtures from ``examples/``. A source checkout keeps that
human-facing tree as the canonical copy. For installed wheels the same files are
shipped as package data under ``youtube_intel/_fixtures``.

Resolution order:

1. the source-tree ``examples/`` directory, when running from a checkout;
2. the packaged ``youtube_intel/_fixtures`` directory, for installed wheels.

``fixtures_root()`` returns ``None`` when neither exists, so callers raise a
specific, actionable error instead of silently producing empty output.
"""

from pathlib import Path

PACKAGED_FIXTURES_DIRNAME = "_fixtures"


def source_tree_root() -> Path | None:
    """Return the repository root when running from a source checkout."""
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "examples").is_dir() and (candidate / "pyproject.toml").is_file():
        return candidate
    return None


def fixtures_root() -> Path | None:
    """Return the directory holding synthetic fixtures, or None if unavailable."""
    source_root = source_tree_root()
    if source_root is not None:
        return source_root / "examples"
    packaged = Path(__file__).resolve().parent / PACKAGED_FIXTURES_DIRNAME
    if packaged.is_dir():
        return packaged
    return None


def require_fixtures_root() -> Path:
    """Return the fixtures root or raise with an actionable message."""
    root = fixtures_root()
    if root is None:
        raise FileNotFoundError(
            "synthetic fixtures are not available in this installation. "
            "Run the demos from a source checkout, or reinstall a build that "
            "includes the youtube_intel._fixtures package data."
        )
    return root
```

Note the `source_tree_root()` guard checks for *both* `examples/` and
`pyproject.toml`. Checking only `parents[2]` would false-positive whenever a
site-packages parent happens to contain a directory named `examples`.

### 1b. Declare the package data in `pyproject.toml`

```toml
[tool.setuptools.package-data]
"youtube_intel._fixtures" = ["*.json", "*.vtt", "**/*.json", "**/*.md"]
```

Both the flat and nested globs are needed: `examples/` has files at the top level
and inside `topic_demo/` and `synthetic_overlay_demo/`.

### 1c. Populate the packaged copy at build time

During prototyping the copy was made with `cp -R examples/. src/youtube_intel/_fixtures/`.
**Do not commit that as the mechanism** — two copies of the same fixtures drifting
apart is a worse bug than the one being fixed. Pick one:

- **Preferred:** add a `MANIFEST.in`-driven or `setup.py`-hook copy so the
  packaged tree is generated during `python -m build`, and add
  `src/youtube_intel/_fixtures/` to `.gitignore`. Then add a CI assertion that
  the built wheel contains 12 fixture entries, so a build-time regression fails
  loudly.
- **Acceptable:** commit the packaged copy and add a test that walks both trees
  and asserts byte-identical contents, so drift fails the suite.

Whichever you choose, state it in a comment next to the `package-data` block.

### 1d. Replace fixture lookups in `src/youtube_intel/cli.py`

Add the import:

```python
from youtube_intel.fixtures import fixtures_root, require_fixtures_root, source_tree_root
```

Then four call-site replacements:

```python
# _default_demo_segments()
-    return _repo_root() / "examples" / "synthetic_segments.json"
+    return require_fixtures_root() / "synthetic_segments.json"

# cmd_topic_demo()
-    root = _repo_root()
-    topic_dir = Path(args.topic_dir) if args.topic_dir else root / "examples" / "topic_demo"
+    topic_dir = Path(args.topic_dir) if args.topic_dir else require_fixtures_root() / "topic_demo"

# cmd_hesitation_demo()
-    fixture = Path(args.fixture) if args.fixture else _repo_root() / "examples" / "synthetic_hesitation.json"
+    fixture = Path(args.fixture) if args.fixture else require_fixtures_root() / "synthetic_hesitation.json"

# cmd_demo() — overlay is genuinely optional, so this one must not raise
-    overlay_path = _repo_root() / "examples" / "synthetic_overlay_demo" / "operator_overlay.json"
-    overlay = read_json(overlay_path, {}) if overlay_path.exists() else {}
+    fixtures = fixtures_root()
+    overlay_path = (fixtures / "synthetic_overlay_demo" / "operator_overlay.json") if fixtures else None
+    overlay = read_json(overlay_path, {}) if overlay_path and overlay_path.exists() else {}
```

The overlay case deliberately uses the nullable `fixtures_root()` rather than
`require_fixtures_root()`: `cmd_demo` already treats a missing overlay as an
empty dict, and turning that into a hard failure would be a behavior change
outside this fix.

Keep `_repo_root()` — `doctor` still needs it for repo-only checks — but add a
docstring marking it as not-for-fixtures so the next reader does not reintroduce
the bug.

### 1e. Two more `parents[2]` sites

Same latent bug, same fix, outside `cli.py`:

- `src/youtube_mcp_handoff/server.py:16` — `_resolve_overlay_path()`
- `src/youtube_mcp_handoff/smoke.py:40`

These are lower impact (both accept an explicit path argument, and `smoke.py` is
CI-invoked from the source tree) but they will silently break for anyone running
`youtube-mcp-handoff` from an installed wheel.

### Acceptance

```bash
python -m build --wheel
unzip -l dist/*.whl | grep -c _fixtures     # expect 12
python -m venv vclean && vclean/bin/python -m pip install dist/*.whl
vclean/bin/youtube-intel topic-demo --out /tmp/t
vclean/bin/youtube-intel single-video-demo --out /tmp/s
```

Measured on the prototype: `claim_group_count: 4` (was `0`),
`opinion_group_warnings: []` (was `["opinion_group_builder_no_claim_groups"]`),
and `single-video-demo` returns `ok: true` instead of a `ValueError` traceback.

**Test to add:** a test that monkeypatches `fixtures.source_tree_root` to return
`None`, then asserts `fixtures_root()` finds the packaged directory. Without it,
the installed-layout path stays untested — and it is precisely the path CI never
exercises, which is how this bug survived in the first place.

---

## Task 2 — Never report an empty TopicCollection as success

**Fixes:** the reporting half of P1-1. Independent of Task 1, but land Task 1
first or the demo goes from wrong-and-quiet to broken-and-loud.

This is the most important change in the guide relative to the project's own
doctrine. `build_topic_demo_from_segments` globbing zero files and returning
`ok: true` is manufactured certainty, which is the exact failure mode
`PUBLIC_THESIS.md` and `TOPIC_LIMITATIONS` exist to prevent.

In `src/youtube_intel/topic_collection.py`:

```python
-    for segments_file in sorted(topic_dir.glob("video_*.json")):
+    segment_files = sorted(topic_dir.glob("video_*.json"))
+    if not segment_files:
+        # An empty terrain must never be reported as a successful run: silently
+        # returning ok=true with zero claim groups manufactures certainty, which
+        # is exactly what this package refuses to do.
+        raise FileNotFoundError(
+            f"no video_*.json fixtures found in {topic_dir}. "
+            "A TopicCollection cannot be built from zero video records."
+        )
+    for segments_file in segment_files:
```

Then stop the CLI from dumping tracebacks for expected failures. In
`cli.main()`:

```python
     args = parser.parse_args(argv)
-    return int(args.func(args))
+    try:
+        return int(args.func(args))
+    except (FileNotFoundError, ValueError) as exc:
+        # Missing fixtures or malformed operator input are expected failures, not
+        # crashes. Report them as a structured error with a non-zero exit code
+        # instead of dumping a traceback.
+        return _print({"ok": False, "error": type(exc).__name__, "message": str(exc)})
+
```

`_print` already returns `2` for `ok: false`, so the exit code is non-zero
without extra work. This also cleans up the `single-video-demo` traceback from
P1-1 and the `_load_segment_input` `ValueError` path for malformed operator JSON.

Scope note: catching only `FileNotFoundError` and `ValueError` is deliberate.
A blanket `except Exception` would hide real bugs, which is the opposite of the
goal.

### Acceptance

```bash
mkdir /tmp/empty
youtube-intel topic-demo --topic-dir /tmp/empty --out /tmp/o; echo $?
```

Measured: structured `{"ok": false, "error": "FileNotFoundError", "message": ...}`
and exit `2`, with the normal run unaffected (`claim_group_count: 4`).

**Tests to add:** one asserting `build_topic_demo_from_segments` raises on an
empty directory; one asserting `main()` returns non-zero and prints `ok: false`
rather than propagating.

---

## Task 3 — Make `doctor` honest about installed packages

**Fixes:** the diagnostic half of P1-1. `doctor` currently reports
`all_required_ignores_present: false` and missing fixtures for a *correctly
installed* package, because it looks for `.gitignore` and `scripts/` that only
exist in a checkout. A health check that cries wolf on a healthy install trains
users to ignore it.

Replace the head of `cmd_doctor`:

```python
    # Fixture availability is independent of layout: it works from a source
    # checkout and from an installed wheel that carries the packaged fixtures.
    fixtures = fixtures_root()
    demo_available = bool(
        fixtures
        and (fixtures / "synthetic_segments.json").exists()
        and (fixtures / "synthetic_package.json").exists()
    )
    topic_demo_available = bool(fixtures and (fixtures / "topic_demo").is_dir())

    # Repo-only posture checks. An installed package has no .gitignore and no
    # scripts/ directory, so these are reported as not_applicable rather than as
    # safety failures.
    source_root = source_tree_root()
    if source_root is None:
        safety: dict[str, Any] = {
            "checks_applicable": False,
            "reason": "installed_package_not_source_checkout",
            "gitignore_patterns": {},
            "all_required_ignores_present": None,
        }
        leak_scan_available = None
    else:
        gitignore_path = source_root / ".gitignore"
        gitignore = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
        required_ignores = ["outputs/", "pilot_[r]uns/", "codex_state/", ".youtube_intel/", "*.db", "*.log"]
        ignore_status = {pattern: (pattern in gitignore) for pattern in required_ignores}
        safety = {
            "checks_applicable": True,
            "gitignore_patterns": ignore_status,
            "all_required_ignores_present": all(ignore_status.values()),
        }
        leak_scan_available = (source_root / "scripts" / "public_release_leak_scan.py").exists()
```

And the result block:

```python
-        "ok": True,
-        "schema_version": "youtube_intel_doctor.v0.1",
+        "ok": demo_available and topic_demo_available,
+        "schema_version": "youtube_intel_doctor.v0.2",
         "core": {
             "python": sys.version.split()[0],
+            "install_layout": "source_checkout" if source_root else "installed_package",
-            "repo_root": str(root),
+            "repo_root": str(source_root) if source_root else None,
+            "fixtures_root": str(fixtures) if fixtures else None,
             ...
         },
-        "safety": { ... },
+        "safety": safety,
```

Two behavior changes worth calling out in review:

- `ok` was a hardcoded `True`, which made it useless as a health signal. It now
  reflects fixture availability. If any caller depends on `ok` always being true,
  that caller is relying on a bug.
- The schema version bumps to `v0.2` because `safety` gained `checks_applicable`
  and `all_required_ignores_present` can now be `null`. Consumers that treat
  `null` as falsy would misread a not-applicable check as a failure, so the bump
  is load-bearing, not cosmetic.

### Acceptance

Measured on a clean wheel install: `install_layout: "installed_package"`,
`fixtures_root` pointing into site-packages, both fixture flags `true`,
`safety.checks_applicable: false`, and `ok: true`.

---

## Task 4 — Make the documented validation sequence actually pass

**Fixes:** P1-2. No code change; this is a pure docs/consistency fix, and the
cheapest win in the guide.

The constraint is currently recorded only as a comment inside
`.github/workflows/ci.yml`. Propagate it to every surface that tells a human to
run the leak scan:

- `README.md`, "Run tests and public smoke checks"
- `SMOKE_TESTS.md`, "Optional Broader Local Check"
- `PACKAGING_CLOSEOUT.md`, "Validation Commands"

In each, insert the clean step before the scan:

```bash
python -m pytest -q tests
python -m youtube_mcp_handoff.smoke
python scripts/clean_generated_artifacts.py   # pytest leaves __pycache__; the scan rejects it
python scripts/public_release_leak_scan.py
```

The alternative is making `public_release_leak_scan.py` skip `__pycache__` and
`.pyc` instead of failing on them. That is defensible but strictly worse here:
the scan's job is to guarantee nothing generated reaches a public tree, and
`tests/test_public_release_leak_scan.py` asserts the current rejecting behavior.
Changing the scan means changing that contract; changing the docs does not.

**Acceptance:** copy each documented block verbatim into a fresh shell and
confirm exit 0.

---

## Task 5 — Korean tokenization in the grouping layer

**Fixes:** P2-2, the largest gap between what the docs promise and what the code
does.

**Problem recap.** `_normalize_claim_tokens` splits on whitespace and applies
English suffix rules. Korean particles stay glued to the noun, so `고용을` and
`고용이` never match. Worse, the shared `len(token) < 3` filter discards every
two-syllable Korean word, so `고용 증가` normalizes to `[]` — an empty token set
that scores `0.0` against everything.

In `src/youtube_intel/topic_collection.py`, add above `_normalize_claim_tokens`:

```python
# --- Korean (Hangul) handling -------------------------------------------------
#
# The English path relies on whitespace tokenization plus suffix stripping. That
# fails for Korean twice over: particles are attached to the noun (고용을 vs
# 고용이 are different tokens), and the shared `len(token) < 3` filter discards
# every two-syllable word, emptying the token set entirely so similarity is 0.0
# against everything.
#
# These two helpers keep the fix deterministic and dependency-free: strip a fixed
# list of trailing particles/endings, and apply a Hangul-aware minimum length.

_HANGUL_RE = re.compile(r"[가-힣]")

# Longest-first: 으로는 must be tried before 으로 and 는.
KOREAN_TRAILING_PARTICLES = (
    "으로는", "에서는", "에게는", "으로도", "이라고", "라고는",
    "에서", "에게", "으로", "라고", "부터", "까지", "처럼", "만큼",
    "보다", "이나", "든지", "마다", "조차", "밖에", "이란", "이든",
    "은", "는", "이", "가", "을", "를", "의", "에", "와", "과",
    "도", "만", "로", "나", "든", "야", "랑", "께",
)

# Verb/adjective endings that carry no grouping signal on their own.
KOREAN_TRAILING_ENDINGS = (
    "습니다", "합니다", "입니다", "했습니다", "됩니다",
    "한다", "된다", "이다", "했다", "됐다", "간다", "온다",
    "이라", "하다", "되다",
)

# A Hangul syllable carries far more information than a Latin character, so the
# Latin-oriented minimum length would discard meaningful words.
MIN_HANGUL_TOKEN_LEN = 2


def _is_hangul(token: str) -> bool:
    return bool(_HANGUL_RE.search(token))


def _strip_korean_suffixes(token: str) -> str:
    """Strip one trailing ending and one trailing particle, longest match first.

    Deterministic and conservative: a strip never shortens a token below two
    syllables, so `이가` (a valid two-syllable word) is not reduced to nothing.
    """
    for ending in KOREAN_TRAILING_ENDINGS:
        if token.endswith(ending) and len(token) - len(ending) >= MIN_HANGUL_TOKEN_LEN:
            token = token[: -len(ending)]
            break
    for particle in KOREAN_TRAILING_PARTICLES:
        if token.endswith(particle) and len(token) - len(particle) >= MIN_HANGUL_TOKEN_LEN:
            token = token[: -len(particle)]
            break
    return token
```

Then branch inside the token loop, before the English suffix rules:

```python
     for raw in lowered.split():
         token = SYNONYM_MAP.get(raw, raw)
+        if _is_hangul(token):
+            token = _strip_korean_suffixes(token)
+            token = SYNONYM_MAP.get(token, token)
+            if token in STOPWORDS or len(token) < MIN_HANGUL_TOKEN_LEN:
+                continue
+            tokens.append(token)
+            continue
         if token.endswith("ies") and len(token) > 5:
```

Design constraints that shaped this, and which a reviewer should hold the change
to:

- **No new dependency.** A morphological analyzer (KoNLPy, mecab-ko) would be
  more accurate, but the package advertises zero runtime dependencies and
  stdlib-only determinism. A fixed suffix list keeps that promise.
- **Never strip below two syllables.** Without the length floor, `이가` (a real
  word) reduces to nothing, and short nouns get mangled. The floor is why the
  strip is safe to apply unconditionally.
- **Longest match first.** `으로는` must precede `으로` and `는`, or the longer
  particle is never reached.
- **English path untouched.** The Hangul branch `continue`s, so no English
  behavior changes. All 148 existing tests, including the `pair_agreement 0.875`
  fixture assertion, stay green — verified.

### Measured results

Token preservation, previously all `[]`:

| Input | Before | After |
|---|---|---|
| `고용 증가` | `[]` | `['고용', '증가']` |
| `정책 효과` | `[]` | `['정책', '효과']` |
| `물가 상승` | `[]` | `['물가', '상승']` |
| `센서 오차` | `[]` | `['센서', '오차']` |

Pair similarity, against the `0.20` grouping threshold:

| Pair | Before | After | Expected |
|---|---|---|---|
| `이 정책은 청년 고용을 늘린다` / `청년 고용이 늘어난다고 보기 어렵다` | `0.0` | **`0.3821`** | group (same proposition, opposed stance) |
| `이 센서는 물 사용량을 20퍼센트 줄인다` / `센서 도입으로 물 사용량이 20퍼센트 감소했다` | `0.1911` | **`0.6125`** | group |
| `이 정책은 청년 고용을 늘린다` / `금리 인상은 물가를 잡는다` | `0.0` | `0.0` | stay apart |

The unrelated pair staying at `0.0` matters as much as the other two moving: the
fix raises recall without inventing similarity.

End-to-end, a two-video Korean fixture produced a genuine cross-video group
(`G0002`, 2 videos, 3 claims) where the same fixture previously could not group
at all.

**Tests to add:** a `tests/test_korean_tokenization.py` covering the token
preservation table, the three similarity pairs with threshold assertions, and a
guard that `_strip_korean_suffixes` never returns fewer than two syllables.

**Fixture to add:** a Korean `examples/topic_demo_ko/` with its own
`expected_groupings.json`, so the behavior is defended by the labeled-fixture
harness rather than by unit tests alone. This also starts paying down P2-1.

---

## Task 6 — Korean marker false positives in content classification

**Fixes:** a defect found while validating Task 5, not present in the original
findings file. Filed as **P2-5**.

**What happens.** `claim_axes._scan` does unconditional substring matching. The
`medical_advice` marker `용량` ("dosage") matches inside `사용량` ("usage
volume"), so an irrigation claim classifies as medical advice:

```
"이 센서를 도입하면 물 사용량을 20퍼센트 줄일 수 있습니다"
  -> ('medical_advice', ['용량'])
"이 배터리는 용량이 크다"       -> ('medical_advice', ['용량'])
"이 앱의 보안 설계를 설명한다"    -> ('product_recommendation', ['보안'])
```

**Why this is not cosmetic.** `content_type` feeds `HIGH_VALUE_TYPES` in
`analysis_worth.py:243`, and `medical_advice` is in that set. A misclassified
irrigation claim therefore inflates the high-value count and changes cost-gate
output — the gate that decides whether to spend on ASR, OCR, or source
verification. It also leaked into a group label, which is how it was noticed:
the Korean fixture produced `label="센서 Medical Advice 도입 사용량"`.

**Minimal verified fix**, in `src/youtube_residual/claim_axes.py`:

```python
# Substring matching on short Korean markers produces false positives inside
# longer compounds: "용량" (dosage) matches "사용량" (usage volume), classifying an
# irrigation or battery claim as medical_advice. Because content_type feeds
# HIGH_VALUE_TYPES in the analysis-worth gate, such a misread changes cost-gate
# output, so these markers must not match mid-compound.
#
# Each entry maps a short marker to the preceding syllables that make the match
# spurious. Keep this table minimal and evidence-driven: add an entry only for a
# false positive that has actually been observed.
_KOREAN_MARKER_BLOCKING_PREFIXES: dict[str, tuple[str, ...]] = {
    "용량": ("사용량", "수용량", "허용량", "가용량", "저용량", "총용량", "배터리 용량"),
    "보안": ("정보안",),
    "분류": ("미분류",),
}


def _is_spurious_korean_match(text: str, marker: str) -> bool:
    blocking = _KOREAN_MARKER_BLOCKING_PREFIXES.get(marker)
    if not blocking:
        return False
    # Spurious when every occurrence of the marker sits inside a blocking compound.
    occurrences = 0
    blocked = 0
    start = 0
    while True:
        idx = text.find(marker, start)
        if idx == -1:
            break
        occurrences += 1
        if any(
            text[max(0, idx - len(b) + len(marker)) : idx + len(marker)].endswith(b)
            for b in blocking
        ):
            blocked += 1
        start = idx + 1
    return occurrences > 0 and blocked == occurrences
```

and in `_scan`, after a marker matches:

```python
         if m in text or m in lowered:
+            if _is_spurious_korean_match(text, m):
+                continue
             found.append(m)
```

The "every occurrence blocked" rule is the important detail: a sentence
containing both `사용량` and a real `복용 용량` still classifies as medical
advice, because only one of the two occurrences is spurious.

### Measured results

| Input | Before | After |
|---|---|---|
| `서버 사용량이 급증했다` | `medical_advice` | `other` |
| `이 센서를 도입하면 물 사용량을 20퍼센트...` | `medical_advice` | `other` |
| `개인정보안 처리 방침` | `product_recommendation` | `other` |
| `하루 복용 용량을 지키세요` | `medical_advice` | `medical_advice` (correct, preserved) |
| `처방된 용량을 확인하세요` | `medical_advice` | `medical_advice` (correct, preserved) |

The Korean fixture's group label cleaned up from
`"센서 Medical Advice 도입 사용량"` to `"센서 도입 사용량 있습니다"`. 148 tests
still pass.

**Known remaining gap, deliberately not fixed here.** `이 배터리는 용량이 크다`
still classifies as `medical_advice`, because bare `용량` genuinely is the dosage
marker and only surrounding context distinguishes the two senses. A prefix
denylist cannot resolve that; it needs either a co-occurrence requirement (a
`medical_advice` hit on `용량` alone is insufficient without a second medical
marker) or a domain-scoped marker table. **Recommended follow-up:** require two
independent markers before assigning a high-risk `content_type`, since a
single-marker match is exactly where false positives concentrate. Track it as a
roadmap item rather than expanding the denylist indefinitely.

A broader audit of the other marker tables is also warranted. `_CONTENT_MARKERS`
contains many short entries (`보안`, `분류`, `회귀`, `지문`, `무게`) with the same
mid-compound exposure; only the three observed cases are handled above.

**Tests to add:** the before/after table, plus explicit preservation cases for
genuine `복용 용량` and `처방` sentences so a future denylist edit cannot silently
disable real medical detection.

---

## Task 7 — Say out loud what the system cannot do

**Fixes:** the disclosure half of P2-1 and P2-2. No behavior change. Do this even
if Tasks 5 and 6 are deferred — an undocumented limitation is worse than a
documented one.

### 7a. Add the Korean limitation to `TOPIC_LIMITATIONS`

`TOPIC_LIMITATIONS` in `topic_collection.py` is surfaced in every handoff bundle
and MCP `limitations` response, which makes it the one place an operator is
guaranteed to see. If Task 5 is not yet landed, add:

```python
    "Korean claim grouping is weak: tokenization is whitespace-and-particle "
    "naive, so Korean claims may not group even when they state the same "
    "proposition",
```

If Task 5 *is* landed, replace it with the honest post-fix version — particle
stripping is a heuristic, not morphological analysis, so a caveat still belongs
there.

### 7b. Label the orchard vocabulary as scaffolding

Above `SYNONYM_MAP` in `topic_collection.py`:

```python
# Fixture scaffolding, not a general-purpose synonym resource. This vocabulary
# was written for examples/topic_demo (orchard sensors), so the reported
# pair_agreement score is an in-domain regression guard rather than evidence of
# generalization. Adding a topic means adding vocabulary; the roadmap tracks
# moving this into a loadable per-topic resource.
```

Same note above the four token-expansion blocks in `_token_set` and the label map
in `_group_label`.

### 7c. Qualify the score in `README.md`

`README.md:102` currently says "a small labeled fixture score". Replace with
wording that states it is measured on the same synthetic domain the synonym table
targets, and that cross-domain performance is unmeasured. The current phrasing is
not false, but it invites a reader to treat `0.875` as a generalization result.

---

## Task 8 — Documentation cleanup

**Fixes:** P3. Mechanical, no code.

1. **Broken activation lines.** `README.md:27` and `SMOKE_TESTS.md:9` both give
   `. .venv/Scripts/activate`, which is Windows-only; the README then labels the
   *same* Windows form as the PowerShell alternative, so no line works on POSIX.
   Fix to:
   ```bash
   . .venv/bin/activate            # Windows: .venv\Scripts\Activate.ps1
   ```
2. **One canonical status.** Three different strings across four files, one stale
   (`pending_public_repo`, though the repo is public). Keep the canonical value in
   `README.md` and have `PACKAGING_CLOSEOUT.md`, `docs/SCOPE_BOUNDARY.md`,
   `docs/PUBLIC_THESIS.md`, and `PUBLICATION_RISK_REVIEW.md` reference it instead
   of restating it.
3. **Release checklist.** Tick `[x] GitHub repo is public` in
   `docs/PUBLIC_RELEASE_CHECKLIST.md`.
4. **Dead changelog links.** `CHANGELOG.md` links a `v0.1.0` compare URL and
   release URL, but `git ls-remote --tags origin` is empty. Either
   `git tag -a v0.1.0 <sha> && git push origin v0.1.0`, or drop the link block.
   Tagging is preferable — the changelog already describes a shipped 0.1.0.
5. **Brittle count.** `SMOKE_TESTS.md` promises `2 passed`. Say "passes".
6. **Deprecated alias in docs.** `PACKAGING_CLOSEOUT.md` and
   `docs/mcp_handoff/CODEX_USAGE.md` lead with `youtube-intel demo`; use
   `single-video-demo`, matching the README.

---

## Task 9 — Prune dead surfaces

**Fixes:** P2-3 and P2-4. Do this last; it is cleanup, not correctness.

1. **Private-tree plugin references.** `youtube_plugins/registry.py` lists
   `transcribe_critic` → `youtube_external_bridge.transcribe_critic_bridge` and
   `codex_review` → `youtube_model_flow.codex_review_pack`. Neither exists here;
   `youtube_external_bridge` is not a package in this repo, so `find_spec` raises
   `ModuleNotFoundError` (caught, so `doctor` survives). Drop both entries, or add
   a `visibility: "external_private"` field so `doctor` can label them instead of
   listing them as plain unavailable.
2. **Duplicated `youtube_ops_cli.py`.** Two copies, differing only in a
   `sys.path` insert; the shipped one is `src/youtube_ops_cli.py` via
   `py-modules`. Nothing references either — `youtube-ops` points at
   `youtube_intel.cli:main`. Delete both and drop `py-modules` from
   `pyproject.toml`.
3. **Unexposed quality gate.** `youtube_quality/gate.py` and
   `youtube_model_flow/quality_gate.py` are imported only by
   `tests/test_quality_gate_runtime_contract.py`, yet
   `docs/BOOTSTRAP_PROMPT.md` instructs agents to "run the quality gate before
   final report creation". Either add a `youtube-intel quality-gate --report ...`
   subcommand, or state in the doc that it is a library-only contract with no CLI
   surface. Leaving an instruction with no way to follow it is the worst of the
   three options.

---

## Prototype verification log

What was actually run, so the numbers above can be re-derived:

```bash
# scratch copy of the tree at 41f504d, editable install
python3 -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"

# after each change
.venv/bin/python -m pytest -q -p no:cacheprovider     # 148 passed, every time

# Task 1 + 2 + 3 verification
.venv/bin/python -m build --wheel -o dist_proto
unzip -l dist_proto/*.whl | grep -c _fixtures          # 12
python3 -m venv vclean && vclean/bin/python -m pip install dist_proto/*.whl
vclean/bin/youtube-intel doctor                        # installed_package, ok: true
vclean/bin/youtube-intel topic-demo --out o1           # claim_group_count: 4
vclean/bin/youtube-intel single-video-demo --out o2    # ok: true
vclean/bin/youtube-intel topic-demo --topic-dir empty --out o3   # ok: false, exit 2

# Task 5 + 6 verification: similarity probes against topic_collection internals,
# classify_content_axis probes, and a two-video Korean fixture run end to end.
```

Tasks 4, 7, 8, and 9 are documentation and deletion work; they were specified
from verified evidence but not prototyped, since there is no behavior to measure.
