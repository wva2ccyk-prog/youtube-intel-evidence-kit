import json

from youtube_plugins.registry import (
    EXCLUDED_FROM_PUBLIC_DISCOVERY,
    PLUGIN_SPECS,
    check_all,
    check_plugin,
)


def test_registry_includes_v6_optional_plugins():
    expected = {
        "summarize",
        "transcribe_critic",
        "faster_whisper",
        "whisperx",
        "paddleocr",
        "tesseract",
        "gemini_flash",
        "codex_review",
    }
    assert expected.issubset(set(PLUGIN_SPECS))


def test_acquisition_tooling_is_excluded_from_public_discovery():
    # The public alpha must not advertise a YouTube media download or
    # media-processing acquisition path in default plugin discovery.
    for name in EXCLUDED_FROM_PUBLIC_DISCOVERY:
        assert name not in PLUGIN_SPECS
    names = {status["name"] for status in check_all()}
    assert "yt_dlp" not in names
    assert "ffmpeg" not in names
    roles = {status["role"] for status in check_all()}
    assert "caption_or_media_fetch_fallback" not in roles
    assert "audio_video_processing" not in roles


def test_all_optional_plugins_return_structured_status_and_json():
    statuses = check_all()
    json.dumps(statuses, ensure_ascii=False)
    for status in statuses:
        assert {"name", "available", "status", "role", "required", "warning", "check_type"}.issubset(status)
        assert status["status"] in {"available", "unavailable", "not_configured"}


def test_missing_plugin_does_not_crash():
    status = check_plugin("__definitely_missing_plugin__")
    assert status.name == "__definitely_missing_plugin__"
    assert status.available is False
    assert status.status == "unavailable"
    assert "optional" in status.warning
