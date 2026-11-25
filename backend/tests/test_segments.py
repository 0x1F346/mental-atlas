from atlas.pipeline.segments import build_segments, build_text_segments, quote_time
from atlas.providers.base import Word


def words(script: list[tuple[str, str]]) -> list[Word]:
    out: list[Word] = []
    clock = 0
    for speaker, sentence in script:
        for token in sentence.split():
            out.append(Word(token, clock, clock + 200, speaker))
            clock += 250
    return out


def test_consecutive_words_from_one_speaker_become_one_segment() -> None:
    segments = build_segments(
        words([("a", "How are you?"), ("b", "I felt dread."), ("b", "It passed."), ("a", "Go on.")])
    )
    assert [(s.speaker, s.text) for s in segments] == [
        ("a", "How are you?"),
        ("b", "I felt dread. It passed."),
        ("a", "Go on."),
    ]
    assert (segments[0].start_ms, segments[0].end_ms) == (0, 700)
    assert segments[1].start_ms == 750


def test_positions_index_the_newline_joined_transcript() -> None:
    segments = build_segments(words([("a", "One two."), ("b", "Three."), ("a", "Four five six.")]))
    whole = "\n".join(s.text for s in segments)
    for segment in segments:
        assert whole[segment.start_char : segment.end_char] == segment.text


def test_long_segments_split_at_a_sentence_end() -> None:
    sentence = "This is a sentence of invented words."
    segments = build_segments(words([("a", " ".join([sentence] * 60))]))
    assert len(segments) > 1
    assert all(len(s.text) <= 1200 for s in segments)
    assert all(s.text.endswith(".") and s.text.startswith("This") for s in segments)
    assert " ".join(s.text for s in segments) == " ".join([sentence] * 60)


def test_a_long_run_with_no_sentence_end_still_splits() -> None:
    segments = build_segments(words([("a", " ".join(["word"] * 500))]))
    assert len(segments) > 1 and all(len(s.text) <= 1200 for s in segments)
    assert sum(len(s.text.split()) for s in segments) == 500


def test_word_timings_locate_a_quote() -> None:
    segment = build_segments(words([("a", "I felt dread before the review.")]))[0]
    start = segment.text.index("dread")
    assert quote_time(segment.words, start, start + len("dread before")) == (500, 950)
    assert quote_time(None, 0, 5) == (None, None)


def test_paragraphs_become_segments_with_exact_positions() -> None:
    text = "First paragraph,\nstill the first.\n\n  Second paragraph.  \n\n\nThird."
    segments = build_text_segments(text)
    assert [s.text for s in segments] == [
        "First paragraph,\nstill the first.",
        "Second paragraph.",
        "Third.",
    ]
    for segment in segments:
        assert text[segment.start_char : segment.end_char] == segment.text
        assert segment.start_ms is None


def test_long_paragraphs_split_at_sentence_ends_with_exact_positions() -> None:
    text = " ".join(["An invented sentence about nothing."] * 80)
    segments = build_text_segments(text)
    assert len(segments) > 1
    for segment in segments:
        assert len(segment.text) <= 1200
        assert text[segment.start_char : segment.end_char] == segment.text
        assert segment.text.endswith(".")
