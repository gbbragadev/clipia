from app.services.subtitles import group_words


def test_group_words_max_3():
    words = [
        {"word": "Voce", "start": 0.0, "end": 0.3},
        {"word": "sabia", "start": 0.3, "end": 0.6},
        {"word": "que", "start": 0.6, "end": 0.8},
        {"word": "o", "start": 0.8, "end": 0.9},
        {"word": "oceano", "start": 0.9, "end": 1.3},
    ]
    chunks = group_words(words, max_words=3)
    assert len(chunks) == 2
    assert len(chunks[0]) == 3
    assert len(chunks[1]) == 2
    assert chunks[0][0]["word"] == "Voce"
    assert chunks[1][0]["word"] == "o"


def test_group_words_empty():
    assert group_words([], max_words=3) == []
