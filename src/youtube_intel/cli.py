from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from youtube_intel.analysis_worth import build_analysis_worth
from youtube_intel._fixtures import fixture_exists, fixture_path, find_source_root, is_installed_package, is_source_checkout
from youtube_intel.errors import InvalidInputError
from youtube_intel.hesitation_markers import (
    analyze_claim_words,
    build_markers_artifact,
    render_markers_markdown,
)
from youtube_intel.io_utils import read_json, read_required_json, write_json, write_text
from youtube_intel.reporting import write_handoff_bundle
from youtube_intel.topic_collection import CLUSTERERS, build_topic_demo_from_segments
from youtube_plugins.registry import check_all
from youtube_residual import build_residual_package, validate_package


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _print(data: dict[str, Any]) -> int:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
    return 0 if data.get("ok", True) else 2


def _load_segment_input(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = read_required_json(path, label="segments file")
    if isinstance(data, list):
        segments = data
        video: dict[str, Any] = {}
    elif isinstance(data, dict):
        video = data.get("video") if isinstance(data.get("video"), dict) else {}
        segments = data.get("segments")
        if not isinstance(segments, list):
            raise InvalidInputError(
                f"segments file {path} must contain a 'segments' list (got {type(segments).__name__})"
            )
    else:
        raise InvalidInputError(
            f"segments file {path} must be a list or an object with a segments list (got {type(data).__name__})"
        )
    for i, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise InvalidInputError(
                f"segments file {path} segment {i} is not an object (got {type(segment).__name__})"
            )
    return video, segments


def _default_demo_segments() -> Path:
    return fixture_path("synthetic_segments.json")


def cmd_doctor(args: argparse.Namespace) -> int:
    root = find_source_root()
    runtime_mode = (
        "source_checkout" if is_source_checkout()
        else "installed_package" if is_installed_package()
        else "missing_resources"
    )
    checks: dict[str, Any] = {}

    # runtime_resources: source fixtures must exist in source mode; packaged
    # fixtures must exist in installed mode; missing-resource mode always fails.
    if runtime_mode == "missing_resources":
        checks["runtime_resources"] = {
            "ok": False,
            "message": "no source checkout marker and no packaged fixtures are accessible",
        }
    else:
        demo_ok = fixture_path("synthetic_segments.json").exists() and fixture_path("synthetic_package.json").exists()
        topic_ok = fixture_path("topic_demo").is_dir()
        hz_ok = fixture_path("synthetic_hesitation.json").exists()
        checks["runtime_resources"] = {
            "ok": demo_ok and topic_ok and hz_ok,
            "message": (
                "resources present"
                if (demo_ok and topic_ok and hz_ok)
                else "one or more required fixtures are missing"
            ),
        }
        checks["synthetic_demo"] = {"ok": demo_ok}
        checks["topic_demo"] = {"ok": topic_ok}

    # gitignore_safety / repository-only checks apply only in source mode.
    if runtime_mode == "source_checkout":
        assert root is not None
        gitignore = (root / ".gitignore").read_text(encoding="utf-8") if (root / ".gitignore").exists() else ""
        required_ignores = ["outputs/", "pilot_[r]uns/", "codex_state/", ".youtube_intel/", "*.db", "*.log"]
        ignore_status = {pattern: (pattern in gitignore) for pattern in required_ignores}
        missing_ignores = [p for p, ok in ignore_status.items() if not ok]
        script_ok = (root / "scripts" / "public_release_leak_scan.py").exists()
        checks["gitignore_safety"] = {
            "ok": not missing_ignores,
            "missing": missing_ignores,
        }
        checks["repository_safety_scripts"] = {
            "ok": script_ok,
            "message": "leak scan script present" if script_ok else "leak scan script missing",
        }
    else:
        checks["gitignore_safety"] = {"ok": True, "not_applicable": True}
        checks["repository_safety_scripts"] = {"ok": True, "not_applicable": True}

    all_ok = all(c.get("ok") is True for c in checks.values())
    result = {
        "ok": all_ok,
        "schema_version": "youtube_intel_doctor.v0.1",
        "checks": checks,
        "core": {
            "python": sys.version.split()[0],
            "repo_root": str(root) if root else None,
            "runtime_mode": runtime_mode,
            "synthetic_demo_available": checks.get("synthetic_demo", {}).get("ok", False),
            "synthetic_topic_demo_available": checks.get("topic_demo", {}).get("ok", False),
            "repository_only_checks_applicable": runtime_mode == "source_checkout",
        },
        "optional_plugins": check_all(),
        "project_identity": "alpha_cross_video_evidence_contract",
        "not_a_summarizer": True,
        "truth_status": "not_evaluated",
        "alpha_boundary": "deterministic local grouping demo; not production topic synthesis",
        "transcript_boundary": "synthetic fixtures only; users are responsible for lawful transcript acquisition",
        "core_demo_command": "youtube-intel topic-demo --out outputs/topic_demo",
        "recommended_next_command": "youtube-intel topic-demo --out outputs/topic_demo",
    }
    return _print(result)


def cmd_package(args: argparse.Namespace) -> int:
    video, segments = _load_segment_input(Path(args.segments))
    if not segments:
        raise InvalidInputError(
            f"segments file {args.segments} has no segments; refusing to build an empty package"
        )
    # The general package command must never fabricate a synthetic identity:
    # video_id and title must come from --video-id/--title or the input file.
    video_id = args.video_id or video.get("video_id")
    if not video_id or not str(video_id).strip():
        raise InvalidInputError(
            "package requires a non-empty video_id from --video-id or the input file's video.video_id"
        )
    title = args.title or video.get("title")
    if not title or not str(title).strip():
        raise InvalidInputError(
            "package requires a non-empty title from --title or the input file's video.title"
        )
    language = args.language or video.get("language")
    if not language or not str(language).strip():
        # `und` is the explicit documented escape hatch for undefined language.
        raise InvalidInputError(
            "package requires a non-empty language from --language or the input file's "
            "video.language (use the explicit value 'und' for an undefined language)"
        )
    package = build_residual_package(
        video_id=str(video_id),
        title=str(title),
        language=str(language),
        segments=segments,
        duration_seconds=args.duration_seconds or video.get("duration_seconds"),
        genre_override=args.genre,
        claim_assembly=args.claim_assembly,
    )
    validation = validate_package(package).to_dict()
    out = Path(args.out)
    package_path = write_json(out / "residual_package.json", package.to_dict())
    validation_path = write_json(out / "validation.json", validation)
    return _print({
        "ok": validation["status"] == "pass",
        "schema_version": "youtube_intel_package_command.v0.1",
        "paths": {"residual_package_json": str(package_path), "validation_json": str(validation_path)},
        "validation": validation,
    })


def cmd_worth(args: argparse.Namespace) -> int:
    # Validate a user-supplied --package before handing it to build_analysis_worth
    # so a missing file or invalid JSON fails closed instead of a traceback.
    if args.package:
        read_required_json(Path(args.package), label="package file")
    result = build_analysis_worth(
        package_path=args.package,
        run_dir=args.run_dir,
        compare_packages=args.compare_package or [],
        output_dir=args.out,
    )
    return _print({"ok": True, "schema_version": "youtube_intel_worth_command.v0.1", "analysis_worth": result, "paths": result.get("paths", {})})


def cmd_handoff(args: argparse.Namespace) -> int:
    package: dict[str, Any] = {}
    worth: dict[str, Any] = {}
    overlay: dict[str, Any] = {}
    if args.package:
        package = read_required_json(Path(args.package), label="package file")
        if not isinstance(package, dict):
            raise InvalidInputError(
                f"package file {args.package} must be an object (got {type(package).__name__})"
            )
    if args.analysis_worth:
        worth = read_required_json(Path(args.analysis_worth), label="analysis-worth file")
        if not isinstance(worth, dict):
            raise InvalidInputError(
                f"analysis-worth file {args.analysis_worth} must be an object (got {type(worth).__name__})"
            )
    elif args.package:
        worth = build_analysis_worth(package_path=args.package)
    if args.overlay:
        overlay = read_required_json(Path(args.overlay), label="overlay file")
        if not isinstance(overlay, dict):
            raise InvalidInputError(
                f"overlay file {args.overlay} must be an object (got {type(overlay).__name__})"
            )
    manifest = write_handoff_bundle(args.out, package=package, worth=worth, overlay=overlay)
    return _print(manifest)


def cmd_demo(args: argparse.Namespace) -> int:
    out = Path(args.out)
    package_dir = out / "package"
    worth_dir = out / "analysis_worth"
    handoff_dir = out / "handoff"
    segments_path = Path(args.segments) if args.segments else _default_demo_segments()
    video, segments = _load_segment_input(segments_path)
    package = build_residual_package(
        video_id=video.get("video_id") or "synthetic-field-demo",
        title=video.get("title") or "Synthetic Orchard Sensor Field Notes",
        language=video.get("language") or "en",
        segments=segments,
        duration_seconds=video.get("duration_seconds") or 24,
        genre_override=args.genre,
    )
    validation = validate_package(package).to_dict()
    package_dict = package.to_dict()
    residual_path = write_json(package_dir / "residual_package.json", package_dict)
    validation_path = write_json(package_dir / "validation.json", validation)
    worth = build_analysis_worth(package_path=residual_path, output_dir=worth_dir)
    overlay_path = fixture_path("operator_overlay.json")
    overlay = read_json(overlay_path, {}) if overlay_path.exists() else {}
    manifest = write_handoff_bundle(handoff_dir, package=package_dict, worth=worth, overlay=overlay)
    result = {
        "ok": validation["status"] == "pass" and manifest.get("ok") is True,
        "schema_version": "youtube_intel_demo_command.v0.1",
        "decision": worth.get("decision", {}),
        "paths": {
            "residual_package_json": str(residual_path),
            "validation_json": str(validation_path),
            "analysis_worth_json": worth.get("paths", {}).get("json"),
            "analysis_worth_md": worth.get("paths", {}).get("markdown"),
            "handoff_dir": str(handoff_dir),
            "operator_summary_md": manifest.get("paths", {}).get("operator_summary_md"),
            "ai_handoff_prompt_md": manifest.get("paths", {}).get("ai_handoff_prompt_md"),
        },
        "next_command": f"youtube-intel handoff --package {residual_path} --analysis-worth {worth_dir / 'analysis_worth.json'} --out {handoff_dir}",
    }
    return _print(result)


def cmd_topic_demo(args: argparse.Namespace) -> int:
    topic_dir = Path(args.topic_dir) if args.topic_dir else fixture_path("topic_demo")
    manifest = build_topic_demo_from_segments(
        topic_dir,
        topic_id=args.topic_id,
        topic_title=args.topic_title,
        output_dir=Path(args.out),
        clusterer=args.clusterer,
        token_jaccard_threshold=args.token_jaccard_threshold,
    )
    return _print(manifest)


def cmd_hesitation_demo(args: argparse.Namespace) -> int:
    """Run the deterministic hesitation-marker rules over a synthetic
    word-timestamp fixture and write the typed, disclaimed artifact.

    This is a contract demo: it needs no ASR and no audio. In a real run the
    word timestamps come from a need-gated local ASR pass (an escalation gate,
    not a default) over an operator-selected claim span; see
    docs/HESITATION_MARKERS.md.
    """
    fixture = Path(args.fixture) if args.fixture else fixture_path("synthetic_hesitation.json")
    data = read_required_json(fixture, label="hesitation fixture")
    if not isinstance(data, dict):
        raise InvalidInputError(
            f"hesitation fixture {fixture} must be an object with a claims list (got {type(data).__name__})"
        )
    claims = data.get("claims")
    if not isinstance(claims, list) or not claims:
        raise InvalidInputError(
            f"hesitation fixture {fixture} is missing, empty, or malformed "
            f"(expected an object with a non-empty claims list)"
        )
    rows = []
    for i, c in enumerate(claims, start=1):
        if not isinstance(c, dict):
            raise InvalidInputError(
                f"hesitation fixture {fixture} claim row {i} is not an object (got {type(c).__name__})"
            )
        words = c.get("words", [])
        if not isinstance(words, list):
            raise InvalidInputError(
                f"hesitation fixture {fixture} claim row {i} 'words' is not a list (got {type(words).__name__})"
            )
        for wi, w in enumerate(words):
            if not isinstance(w, dict):
                raise InvalidInputError(
                    f"hesitation fixture {fixture} claim row {i} word row {wi} is not an object "
                    f"(got {type(w).__name__}); non-dictionary word rows are rejected "
                    f"(malformed timestamp dictionaries are reported as malformed rows)"
                )
        rows.append(
            analyze_claim_words(
                c.get("claim_id", f"C{i:03d}"),
                words,
                expected_text=c.get("expected_text"),
                span_start=c.get("span_start"),
                span_end=c.get("span_end"),
            )
        )
    if all(row["word_count"] == 0 for row in rows):
        raise InvalidInputError(
            f"no valid word-timestamp rows remain in hesitation fixture {fixture}: "
            f"every claim is invalid (missing, non-numeric, negative, reversed, "
            f"or zero-duration timestamps)"
        )
    artifact = build_markers_artifact(
        rows,
        provenance={"source": "synthetic_fixture", "fixture": str(fixture), "backend": "none_synthetic"},
    )
    out = Path(args.out)
    json_path = write_json(out / "hesitation_markers.json", artifact)
    md_path = write_text(out / "hesitation_markers.md", render_markers_markdown(artifact))
    return _print({
        "ok": True,
        "schema_version": artifact["schema_version"],
        "claim_count": artifact["claim_count"],
        "hesitation_candidate_count": artifact["hesitation_candidate_count"],
        "paths": {"json": str(json_path), "markdown": str(md_path)},
    })


def cmd_check_plugins(args: argparse.Namespace) -> int:
    return _print({"ok": True, "optional_plugins": check_all()})


GENERATED_DIR_NAMES = {"outputs", "pilot_runs", "codex_state", ".youtube_intel"}
GENERATED_FILE_SUFFIXES = {".db", ".log"}
# Protected source directories that must never be deleted, even with --force.
PROTECTED_DIR_NAMES = {"src", ".git", "tests", "schemas", ".github", "docs", "scripts"}


def _clean_plan(
    targets: list[str],
    *,
    repo_root: Path,
    force: bool = False,
) -> tuple[list[Path], list[Path], list[str]]:
    """Resolve every target and return ``(allowed, missing, refusals)``.

    Every path is resolved (symlinks followed) BEFORE any deletion decision.
    Filesystem root, user home, the repository root itself, and any path
    outside the repository are always refused. Only recognized generated-output
    locations are deletable; ``force`` is retained only for API compatibility
    and NEVER widens the deletion set, so arbitrary repository content cannot be
    removed even with ``--force``. Protected source directories (``src``,
    ``.git``, ``tests``, ``schemas``, ``.github``, ``docs``, ``scripts``) are
    always refused. Any refusal means the caller must fail closed and delete
    nothing.
    """
    root = repo_root.resolve()
    home = Path.home().resolve()
    allowed: list[Path] = []
    missing: list[Path] = []
    refusals: list[str] = []
    for raw in targets:
        raw_path = Path(raw)
        if not raw_path.exists() and not raw_path.is_symlink():
            missing.append(raw_path)
            continue
        target = raw_path.resolve()
        if target == Path("/"):
            refusals.append(f"refusing to delete filesystem root: {raw!r}")
            continue
        if target == home:
            refusals.append(f"refusing to delete user home: {raw!r}")
            continue
        if target == root:
            refusals.append(f"refusing to delete repository root: {root}")
            continue
        if root not in target.parents:
            refusals.append(f"refusing to delete path outside the repository: {raw!r} -> {target}")
            continue
        rel = target.relative_to(root)
        first = rel.parts[0]
        if first in PROTECTED_DIR_NAMES:
            refusals.append(
                f"refusing to delete protected source directory: {raw!r} -> {target} "
                f"(protected: {first}/)"
            )
            continue
        is_generated = (
            first in GENERATED_DIR_NAMES
            or (len(rel.parts) == 1 and target.suffix.lower() in GENERATED_FILE_SUFFIXES)
        )
        if not is_generated:
            # Non-generated repository content is never deletable, even with
            # --force, so clean cannot remove arbitrary repository content.
            refusals.append(
                f"refusing to delete non-generated path: {raw!r} -> {target} "
                f"(clean only removes generated-output locations)"
            )
            continue
        allowed.append(target)
    return allowed, missing, refusals


def cmd_clean(args: argparse.Namespace) -> int:
    # clean is a source-workspace maintenance command. It must never operate
    # from an installed wheel, where the module location is inside site-packages
    # and must not be treated as a deletion boundary.
    root = find_source_root()
    if root is None:
        return _print({
            "ok": False,
            "error": "InvalidInputError",
            "message": "clean is available only from a detected source checkout",
        })
    allowed, missing, refusals = _clean_plan(args.path, repo_root=root)
    if refusals:
        # Fail closed: a dangerous or unauthorized target means NOTHING is
        # deleted, and the refusal is returned as structured JSON.
        return _print({
            "ok": False,
            "error": "UnsafeCleanTargetError",
            "message": "refusing to delete dangerous or unauthorized paths",
            "refusals": refusals,
        })
    if args.dry_run:
        return _print({
            "ok": True,
            "dry_run": True,
            "would_remove": [str(p) for p in allowed],
            "missing": [str(p) for p in missing],
        })
    removed: list[str] = []
    for target in allowed:
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()
        removed.append(str(target))
    return _print({"ok": True, "removed": removed, "missing": [str(p) for p in missing]})


def cmd_mcp_stdio(args: argparse.Namespace) -> int:
    from youtube_mcp_handoff.stdio_server import run_stdio_server

    run_stdio_server(overlay_path=args.overlay)
    return 0


def cmd_topic_mcp_stdio(args: argparse.Namespace) -> int:
    from youtube_intel.topic_mcp_facade import run_stdio_server

    run_stdio_server(topic_collection_path=args.topic_collection)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="youtube-intel", description="Alpha cross-video evidence contract. Not a production YouTube intelligence engine, not a summarizer, and not truth verification. Synthetic fixtures are the public demo input; users are responsible for lawful transcript acquisition.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("doctor", help="Check local package safety and optional plugin posture.")
    p.set_defaults(func=cmd_doctor)

    for demo_name in ("demo", "single-video-demo"):
        p = sub.add_parser(demo_name, help="Run the older synthetic single-video input-layer package -> worth -> handoff flow.")
        p.add_argument("--out", default="outputs/demo")
        p.add_argument("--segments")
        p.add_argument("--genre")
        p.set_defaults(func=cmd_demo)

    p = sub.add_parser("topic-demo", help="Run the alpha synthetic cross-video VideoKnowledgeRecord -> TopicCollection -> terrain flow with deterministic grouping and fixture evaluation.")
    p.add_argument("--out", default="outputs/topic_demo")
    p.add_argument("--topic-dir")
    p.add_argument("--topic-id", default="synthetic-orchard-sensors")
    p.add_argument("--topic-title", default="Synthetic orchard sensor adoption terrain")
    p.add_argument("--clusterer", choices=CLUSTERERS, default="normalized")
    p.add_argument("--token-jaccard-threshold", type=float, default=0.5)
    p.set_defaults(func=cmd_topic_demo)

    p = sub.add_parser("package", help="Build a residual package from admitted segment JSON.")
    p.add_argument("--segments", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--video-id")
    p.add_argument("--title")
    p.add_argument("--language")
    p.add_argument("--duration-seconds", type=int)
    p.add_argument("--genre")
    p.add_argument(
        "--claim-assembly",
        choices=["cue", "sentence"],
        default="cue",
        help="cue (default): one claim per segment. sentence: merge consecutive "
        "cues into Korean-aware sentence units before extracting claims.",
    )
    p.set_defaults(func=cmd_package)

    p = sub.add_parser("worth", help="Build analysis-worth JSON and Markdown from a residual package.")
    p.add_argument("--package")
    p.add_argument("--run-dir")
    p.add_argument("--compare-package", action="append")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_worth)

    for handoff_name in ("handoff", "single-video-handoff"):
        p = sub.add_parser(handoff_name, help="Create AI CLI handoff files from single-video package and analysis-worth artifacts.")
        p.add_argument("--package")
        p.add_argument("--analysis-worth")
        p.add_argument("--overlay")
        p.add_argument("--out", required=True)
        p.set_defaults(func=cmd_handoff)

    p = sub.add_parser("hesitation-demo", help="Run the deterministic Tier-1 hesitation-marker rules over a synthetic word-timestamp fixture (no ASR, no audio).")
    p.add_argument("--fixture", help="Path to a word-timestamp fixture JSON (default: examples/synthetic_hesitation.json).")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_hesitation_demo)

    p = sub.add_parser("check-plugins", help="Print optional plugin status.")
    p.set_defaults(func=cmd_check_plugins)

    p = sub.add_parser("clean", help="Remove generated output paths (source-checkout only and fail-closed by default).")
    p.add_argument("path", nargs="+", default=["outputs/demo"])
    p.add_argument("--dry-run", action="store_true", help="Report what would be removed without deleting anything.")
    p.set_defaults(func=cmd_clean)

    p = sub.add_parser("mcp-stdio", help="Run the read-only synthetic overlay MCP-style JSON-RPC stdio smoke server.")
    p.add_argument("--overlay")
    p.set_defaults(func=cmd_mcp_stdio)

    p = sub.add_parser("topic-mcp-stdio", help="Run the read-only TopicCollection MCP-ready JSON-RPC stdio handoff facade.")
    p.add_argument("--topic-collection", required=True)
    p.set_defaults(func=cmd_topic_mcp_stdio)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except InvalidInputError as exc:
        # Expected input failures (missing, empty, malformed, inconsistent)
        # render as structured JSON with exit code 2 -- never a traceback and
        # never a misleading ok:true artifact. Programming errors are not
        # caught here.
        return _print({"ok": False, "error": "InvalidInputError", "message": str(exc)})


if __name__ == "__main__":
    raise SystemExit(main())


