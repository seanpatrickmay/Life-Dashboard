from __future__ import annotations

from app.services.imessage_utils import (
    ProjectCatalogEntry,
    _EMOJI_RE,
    _normalize_for_fuzzy_match,
    infer_project_match,
)


SAMPLE_CATALOG = [
    ProjectCatalogEntry(name="Comic Book CV Project", aliases=("Comic Book CV Project", "Comic CV")),
    ProjectCatalogEntry(name="Forest Fire", aliases=("Forest Fire", "FF")),
    ProjectCatalogEntry(name="Personal Ops", aliases=("Personal Ops",)),
    ProjectCatalogEntry(name="Ironman Training", aliases=("Ironman Training", "IM")),
]


def test_comic_cv_conversation_name_matches_with_high_confidence() -> None:
    guess = infer_project_match(
        project_catalog=SAMPLE_CATALOG,
        conversation_name="Comic CV Project \U0001F680",
        participants=["alice@example.com"],
        message_texts=["Let's sync on the layout."],
    )
    assert guess.project_name == "Comic Book CV Project"
    assert guess.confidence >= 0.90


def test_forest_fire_emoji_conversation_name_matches_with_high_confidence() -> None:
    guess = infer_project_match(
        project_catalog=SAMPLE_CATALOG,
        conversation_name="\U0001F525FOREST FIRES\U0001F525",
        participants=["bob@example.com"],
        message_texts=["Any update on the permit?"],
    )
    assert guess.project_name == "Forest Fire"
    assert guess.confidence >= 0.90


def test_generic_group_chat_does_not_match_any_project() -> None:
    guess = infer_project_match(
        project_catalog=SAMPLE_CATALOG,
        conversation_name="random group chat",
        participants=["charlie@example.com"],
        message_texts=["Hey what's up"],
    )
    assert guess.project_name is None or guess.confidence < 0.72


def test_emoji_stripping_removes_emoji_correctly() -> None:
    assert _EMOJI_RE.sub("", "Hello \U0001F680 World \U0001F525") == "Hello  World "
    assert _EMOJI_RE.sub("", "No emoji here") == "No emoji here"
    assert _EMOJI_RE.sub("", "\U0001F680\U0001F525\U0001F4A5") == ""


def test_common_word_stripping_removes_filler_words() -> None:
    assert _normalize_for_fuzzy_match("Comic CV Project") == "comic cv"
    assert _normalize_for_fuzzy_match("Forest Fire Team Chat") == "forest fire"
    assert _normalize_for_fuzzy_match("My Group Chat") == "my"


def test_normalize_for_fuzzy_match_is_case_insensitive() -> None:
    assert _normalize_for_fuzzy_match("FOREST FIRE") == _normalize_for_fuzzy_match("forest fire")
    assert _normalize_for_fuzzy_match("Comic CV PROJECT") == _normalize_for_fuzzy_match("comic cv project")
