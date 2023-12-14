import re

from suppgram.emoji import EMOJI_SEQUENCE


def test_emoji():
    regexp = re.compile(f"{EMOJI_SEQUENCE}+")
    assert not regexp.match("x")
    assert regexp.match("😅")
    assert regexp.match("👷🏿")
    # assert not regexp.match("🏿")
    assert regexp.match("‼️")
