"""Palettes clair/sombre : le thème est choisi par requête via un ContextVar."""
from __future__ import annotations

from gex.app import C, CURRENT_THEME, _PALETTES, create_app


def test_les_deux_palettes_ont_les_memes_cles():
    assert set(_PALETTES["light"]) == set(_PALETTES["dark"])


def test_palette_suit_le_contexte_de_la_requete():
    token = CURRENT_THEME.set("dark")
    try:
        assert C["page"] == "#16181d"
        assert C["surface"] == "#1f2228"
        assert C["ink"] == "#e8e6e1"
    finally:
        CURRENT_THEME.reset(token)
    assert C["page"] == "#f2f2f0"
    assert C["surface"] == "#f7f7f4"


def test_index_lit_le_cookie_de_theme_avant_le_css():
    app = create_app()
    index = app.index_string
    assert "gex_theme" in index
    assert index.index("gex_theme") < index.index("{%css%}")
