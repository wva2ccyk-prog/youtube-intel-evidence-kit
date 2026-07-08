from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from youtube_intel.analysis_worth import build_analysis_worth
from youtube_intel.io_utils import read_json, write_json, write_text
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
    data = read_json(path, {})
    if isinstance(data, list):
        return {}, data
    if isinstance(data, dict):
        video = data.get("video") if isinstance(data.get("video"), dict) else {}
        segments = data.get("segments")
        if isinstance(segments, list):
            return video, segments
    raise ValueError(f"segments file must be a list or an object with a segments list: {path}")


def _default_demo_segments() -> Path:
    return _repo_root() / "examples" / "synthetic_segments.json"


def cmd_doctor(args: argparse.Namespace) -> int:
    root = _repo_root()
    gitignore = (root / ".gitignore").read_text(encoding="utf-8") if (root / ".gitignore").exists() else ""
    required_ignores = ["outputs/", "pilot_[r]uns/", "codex_state/", ".youtube_intel/", "*.db", "*.log"]
    ignore_status = {pattern: (pattern in gitignore) for pattern in required_ignores}
    demo_available = _default_demo_segments().exists() and (root / "examples" / "synthetic_package.json").exists()
    topic_demo_available = (root / "examples" / "topic_demo").is_dir()
    leak_scan_available = (root / "scripts" / "public_release_leak_scan.py").exists()
    result = {
        "ok": True,
        "schema_version": "youtube_intel_doctor.v0.1",
        "core": {
            "python": sys.version.split()[0],
            "repo_root": str(root),
            "synthetic_demo_available": demo_available,
            "synthetic_topic_demo_available": topic_demo_available,
            "leak_scan_script_available": leak_scan_available,
        },
        "safety": {
            "gitignore_patterns": ignore_status,
            "all_required_ignores_present": all(ignore_status.values()),
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
    package = build_residual_package(
        video_id=args.video_id or video.get("video_id") or "synthetic-field-demo",
        title=args.title or video.get("title") or "Synthetic Orchard Sensor Field Notes",
        language=args.language or video.get("language") or "en",
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
        package = read_json(Path(args.package), {}) or {}
    if args.analysis_worth:
        worth = read_json(Path(args.analysis_worth), {}) or {}
    elif args.package:
        worth = build_analysis_worth(package_path=args.package)
    if args.overlay:
        overlay = read_json(Path(args.overlay), {}) or {}
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
    overlay_path = _repo_root() / "examples" / "synthetic_overlay_demo" / "operator_overlay.json"
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
    root = _repo_root()
    topic_dir = Path(args.topic_dir) if args.topic_dir else root / "examples" / "topic_demo"
    manifest = build_topic_demo_from_segments(
        topic_dir,
        topic_id=args.topic_id,
        topic_title=args.topic_title,
        output_dir=Path(args.out),
        clusterer=args.clusterer,
        token_jaccard_threshold=args.token_jaccard_threshold,
    )
    return _print(manifest)


def cmd_check_plugins(args: argparse.Namespace) -> int:
    return _print({"ok": True, "optional_plugins": check_all()})


def cmd_clean(args: argparse.Namespace) -> int:
    targets = [Path(p) for p in args.path]
    removed: list[str] = []
    for target in targets:
        if not target.exists():
            continue
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        removed.append(str(target))
    return _print({"ok": True, "removed": removed})


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

    p = sub.add_parser("check-plugins", help="Print optional plugin status.")
    p.set_defaults(func=cmd_check_plugins)

    p = sub.add_parser("clean", help="Remove generated output paths.")
    p.add_argument("path", nargs="+", default=["outputs/demo"])
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
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())


