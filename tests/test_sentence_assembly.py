"""Unit tests for the Korean-aware sentence assembler (opt-in claim assembly)."""

from __future__ import annotations

import pytest

from youtube_intel.sentence_assembly import (
    Cue,
    assemble_from_dicts,
    assemble_sentences,
    format_timestamp,
    is_sentence_final,
    parse_timestamp,
)


def _cues(*texts, start=0.0, step=3.0):
    out = []
    t = start
    for i, tx in enumerate(texts):
        out.append(Cue(index=i, text=tx, start=t, end=t + step))
        t += step
    return out


class TestIsSentenceFinal:
    @pytest.mark.parametrize(
        "text",
        [
            "화두입니다",
            "생각하지 않습니다",
            "그렇게 봅니다",
            "그건 아니죠",
            "맞아요",
            "그럴 거거든요",
            "하지만 문제잖아요",
            "필요합니다.",
            "정말요?",
            "글쎄요",
        ],
    )
    def test_final_forms_close(self, text):
        assert is_sentence_final(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "묻습니다 국민연금 과연 개인 저축보다",  # ends in "보다" (than) -> non-final
            "나에게 국민 연금은 자이다 영원한",  # ends mid-word
            "그래서 우리는",
            "국민연금 제도의",
            "",
            "   ",
        ],
    )
    def test_non_final_forms_stay_open(self, text):
        assert is_sentence_final(text) is False


class TestAssemble:
    def test_single_final_cue_passthrough(self):
        units = assemble_sentences(_cues("이것은 완전한 문장입니다"))
        assert len(units) == 1
        assert units[0].text == "이것은 완전한 문장입니다"
        assert units[0].cue_indices == [0]
        assert units[0].is_merged is False

    def test_fragments_merge_until_final(self):
        units = assemble_sentences(
            _cues("나에게 국민 연금은", "자이다 영원한", "화두입니다")
        )
        assert len(units) == 1
        assert units[0].text == "나에게 국민 연금은 자이다 영원한 화두입니다"
        assert units[0].cue_indices == [0, 1, 2]
        assert units[0].is_merged is True

    def test_two_sentences_split_on_finals(self):
        units = assemble_sentences(
            _cues(
                "국민 연금은",
                "필요합니다",  # closes 1
                "하지만 보험료가",
                "너무 높아요",  # closes 2
            )
        )
        assert [u.text for u in units] == [
            "국민 연금은 필요합니다",
            "하지만 보험료가 너무 높아요",
        ]

    def test_span_and_traceability(self):
        units = assemble_sentences(
            _cues("첫 조각은", "두번째 조각입니다", start=10.0, step=4.0)
        )
        assert len(units) == 1
        u = units[0]
        assert u.start == 10.0
        assert u.end == 18.0
        assert u.span_seconds == 8.0
        assert u.cue_indices == [0, 1]

    def test_char_cap_forces_close(self):
        # No sentence-final ending anywhere; only the char cap can close.
        long_piece = "가나다라마바사아자차카타파하" * 2  # 28 chars, no ending
        units = assemble_sentences(
            [Cue(i, long_piece, start=i, end=i + 0.5) for i in range(20)],
            max_chars=60,
            max_span_seconds=10_000,
        )
        assert len(units) > 1
        for u in units:
            # each unit stays bounded near the cap (never a single runaway blob)
            assert len(u.text) <= 60 + len(long_piece)

    def test_span_cap_forces_close(self):
        # Cues never end in a final form; only the time-span cap can close.
        cues = [Cue(i, "계속 이어지는 말", start=i * 10.0, end=i * 10.0 + 10.0) for i in range(4)]
        units = assemble_sentences(cues, max_chars=10_000, max_span_seconds=15.0)
        assert len(units) >= 2

    def test_empty_cues_skipped(self):
        units = assemble_sentences(
            _cues("실질적인 내용입니다", "", "   ", "다음 문장이에요")
        )
        assert len(units) == 2
        # skipped empties never appear in any unit's cue_indices
        all_idx = [i for u in units for i in u.cue_indices]
        assert 1 not in all_idx and 2 not in all_idx

    def test_tail_flush_without_final(self):
        # Trailing fragment with no closing ending must still be emitted.
        units = assemble_sentences(_cues("이건 문장입니다", "끝나지 않은 조각"))
        assert len(units) == 2
        assert units[-1].text == "끝나지 않은 조각"

    def test_determinism(self):
        cues = _cues("가", "국민연금은", "필요합니다", "그런데 보험료가", "부담이죠")
        a = [u.to_dict() for u in assemble_sentences(cues)]
        b = [u.to_dict() for u in assemble_sentences(cues)]
        assert a == b

    def test_no_text_invention(self):
        # Assembled text is exactly the space-joined cue texts, nothing added.
        cues = _cues("첫째", "둘째입니다")
        units = assemble_sentences(cues)
        joined = " ".join(c.text for c in cues)
        assert units[0].text == joined

    def test_empty_input(self):
        assert assemble_sentences([]) == []


class TestProvenanceBoundaries:
    """A speaker, modality, or source-hint change must force an assembly boundary."""

    def test_unfinished_cue_speaker_change_forces_boundary(self):
        # Speaker A's cue is NOT sentence-final, yet Speaker B's cue must never
        # be merged into A's sentence.
        cues = [
            Cue(0, "국민연금 제도의", start=0.0, end=2.0, speaker="host"),
            Cue(1, "과연 개인 저축보다", start=2.0, end=4.0, speaker="guest"),
        ]
        units = assemble_sentences(cues)
        assert len(units) == 2
        assert units[0].text == "국민연금 제도의"
        assert units[0].speaker == "host"
        assert units[1].text == "과연 개인 저축보다"
        assert units[1].speaker == "guest"

    def test_speaker_change_with_no_punctuation(self):
        cues = [
            Cue(0, "the sensor kit can cut", start=0.0, end=3.0, speaker="vendor"),
            Cue(1, "water use by twenty percent", start=3.0, end=6.0, speaker="operator"),
            Cue(2, "that is what the brochure says", start=6.0, end=9.0, speaker="operator"),
        ]
        units = assemble_sentences(cues)
        assert len(units) == 2
        assert units[0].cue_indices == [0]
        assert units[1].cue_indices == [1, 2]
        assert units[1].speaker == "operator"

    def test_modality_change_forces_boundary(self):
        cues = [
            Cue(0, "caption text that keeps going", start=0.0, end=3.0, modality_source="caption"),
            Cue(1, "screen text read from the chart", start=3.0, end=6.0, modality_source="ocr"),
        ]
        units = assemble_sentences(cues)
        assert len(units) == 2
        assert units[0].modality_source == "caption"
        assert units[1].modality_source == "ocr"

    def test_source_hint_change_forces_boundary(self):
        cues = [
            Cue(0, "the transcript continues", start=0.0, end=3.0, source_hint="transcript"),
            Cue(1, "but the external pack adds context", start=3.0, end=6.0, source_hint="external_pack"),
        ]
        units = assemble_sentences(cues)
        assert len(units) == 2
        assert units[0].source_hint == "transcript"
        assert units[1].source_hint == "external_pack"

    def test_same_speaker_still_merges(self):
        cues = [
            Cue(0, "국민 연금은", start=0.0, end=2.0, speaker="host"),
            Cue(1, "과연 필요한가요", start=2.0, end=4.0, speaker="host"),
        ]
        units = assemble_sentences(cues)
        assert len(units) == 1
        assert units[0].cue_indices == [0, 1]

    def test_unit_keeps_full_provenance(self):
        cues = [
            Cue(0, "첫 조각", start=10.0, end=13.0, speaker="A", modality_source="caption", source_hint="transcript"),
            Cue(1, "둘째 조각입니다", start=13.0, end=16.0, speaker="A", modality_source="caption", source_hint="transcript"),
        ]
        unit = assemble_sentences(cues)[0]
        d = unit.to_dict()
        assert d["cue_indices"] == [0, 1]
        assert d["source_time_refs"] == [10.0, 13.0]
        assert d["start"] == 10.0 and d["end"] == 16.0
        assert d["speaker"] == "A"
        assert d["modality_source"] == "caption"
        assert d["source_hint"] == "transcript"


class TestFromDicts:
    def test_mmss_timestamps(self):
        rows = [
            {"text": "국민연금", "start": "03:06", "end": "03:10"},
            {"text": "필요합니다", "start": "03:10", "end": "03:14"},
        ]
        units = assemble_from_dicts(rows)
        assert len(units) == 1
        assert units[0].start == 186.0
        assert units[0].end == 194.0
        assert units[0].cue_indices == [0, 1]


class TestTimestampHelpers:
    def test_parse_and_format_roundtrip(self):
        assert parse_timestamp("03:06") == 186.0
        assert parse_timestamp("01:02:03") == 3723.0
        assert parse_timestamp(12.5) == 12.5
        assert parse_timestamp(None) is None
        assert parse_timestamp("") is None
        assert format_timestamp(186.0) == "03:06"
        assert format_timestamp(3723.0) == "01:02:03"
        assert format_timestamp(None) is None
