"""Verbatim normalization: artifacts removed, words and punctuation kept."""

from book_rag.normalize import normalize


def test_dehyphenates_line_break_hyphens():
    assert normalize("com-\nbat") == "combat"


def test_keeps_hyphen_as_space_before_capital():
    assert normalize("New-\nYork") == "New York"


def test_expands_ligatures():
    assert normalize("ﬁnancial ﬂow") == "financial flow"


def test_removes_soft_hyphens():
    assert normalize("be\u00adgin") == "begin"


def test_collapses_inline_whitespace():
    assert normalize("a   b\tc") == "a b c"


def test_preserves_paragraph_boundaries():
    assert normalize("para one\n\n  para two  ") == "para one\n\npara two"


def test_strips_surrounding_blank_lines():
    assert normalize("\n\n  hello  \n\n") == "hello"


def test_keeps_punctuation_verbatim():
    assert normalize("Well... really? Yes!\n") == "Well... really? Yes!"
