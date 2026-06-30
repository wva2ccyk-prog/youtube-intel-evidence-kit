from pathlib import Path

from youtube_intel.analysis_worth import build_analysis_worth
from youtube_intel.io_utils import write_json
from youtube_residual import build_residual_package, validate_package


def test_public_residual_package_smoke() -> None:
    package = build_residual_package(
        video_id="synthetic-field-demo",
        title="Synthetic Orchard Sensor Field Notes",
        language="en",
        segments=[
            {
                "text": "The vendor says the orchard sensor kit can cut water use by twenty percent.",
                "time_ref": "00:06",
                "speaker": "narrator",
            },
            {
                "text": "In the field, the cheap probes drifted after two foggy nights, which the sponsored case study did not mention.",
                "time_ref": "00:12",
                "speaker": "narrator",
            },
            {
                "text": "This might be wrong, but local salinity may explain the yield bump more than the sensor software.",
                "time_ref": "00:18",
                "speaker": "narrator",
            },
        ],
    )

    result = validate_package(package)

    assert result.status == "pass"
    assert package.main_candidates
    assert package.aside_candidates


def test_public_analysis_worth_smoke(tmp_path: Path) -> None:
    package_path = tmp_path / "package.json"
    write_json(
        package_path,
        {
            "video": {
                "video_id": "synthetic-field-demo",
                "title": "Synthetic Orchard Sensor Field Notes",
                "language": "en",
                "duration_seconds": 24,
            },
            "genre": {
                "genre": "technical_fieldwork",
                "risk_domain": "medium",
                "required_sections": ["claim_summary", "field_checks", "verification_needed"],
                "score": 1,
                "matched_markers": ["field", "vendor", "sensor"],
                "detection_basis": "synthetic",
            },
            "claim_candidates": [
                {
                    "claim_id": "C0001",
                    "text": "The vendor says the orchard sensor kit can cut water use by twenty percent.",
                    "speaker": "narrator",
                    "time_ref": "00:06",
                    "content_type": "factual_claim",
                    "evidence": "video_internal",
                    "confidence": "medium",
                    "aside_type": "none",
                    "aside_score": 0,
                },
                {
                    "claim_id": "C0002",
                    "text": "In the field, the cheap probes drifted after two foggy nights, which the sponsored case study did not mention.",
                    "speaker": "narrator",
                    "time_ref": "00:12",
                    "content_type": "technical_explanation",
                    "evidence": "video_internal",
                    "confidence": "medium",
                    "aside_type": "type1_hidden_info",
                    "aside_score": 4,
                },
                {
                    "claim_id": "C0003",
                    "text": "This might be wrong, but local salinity may explain the yield bump more than the sensor software.",
                    "speaker": "narrator",
                    "time_ref": "00:18",
                    "content_type": "hypothesis",
                    "evidence": "inference",
                    "confidence": "low",
                    "aside_type": "type2_unformed_thought",
                    "aside_score": 3,
                },
            ],
        },
    )

    result = build_analysis_worth(package_path=package_path, output_dir=tmp_path / "analysis_worth")

    assert result["schema_version"] == "youtube_analysis_worth_v0.1"
    assert result["decision"]["analysis_worth"] == "yes"
    assert "residual_or_uncertainty_candidates" in result["decision"]["why_analyze"]
    assert "promotional_or_hype_noise" in result["decision"]["why_analyze"]
    assert "low_quality_or_uncertain_information" in result["decision"]["why_analyze"]
    assert result["decision"]["information_risks"]["promotional_or_hype_noise"] is True
    assert result["decision"]["auto_gate"]["authority"] == "operator_review"
