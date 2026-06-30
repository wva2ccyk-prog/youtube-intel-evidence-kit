from pathlib import Path


def test_bootstrap_prompt_exists_and_is_pasteable():
    path = Path("docs/BOOTSTRAP_PROMPT.md")
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert len(text) < 3500
    assert "generic YouTube summarizer" in text


def test_bootstrap_prompt_contains_runtime_contract():
    text = Path("docs/BOOTSTRAP_PROMPT.md").read_text(encoding="utf-8")
    required = [
        "Model output is not evidence",
        "transcript/caption",
        "visual/OCR",
        "Start with caption-first",
        "title or description",
        "timestamp",
        "High-risk genres",
        "video-internal claims",
        "quality gate",
        "analysis-worth",
        "Optional plugins",
        "Preserve uncertainty",
        "one_line_summary",
        "timeline",
        "claim_map",
        "evidence_refs",
        "risk_and_uncertainty",
        "genre_specific_notes",
        "next_actions_or_codex_tasks",
        "quality_gate_status",
    ]
    for item in required:
        assert item in text
