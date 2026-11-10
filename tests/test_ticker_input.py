"""Saisie libre d'un ticker depuis le dashboard (barre de recherche).

Le téléchargement CBOE n'est pas testé ici (réseau) ; on couvre la
normalisation et la persistance, qui sont la partie locale du contrat.
"""
from __future__ import annotations

import json

import pytest

from gex import config


def test_normalize_ticker_accepte_les_formes_courantes():
    assert config.normalize_ticker(" soxl ") == "SOXL"
    assert config.normalize_ticker("$tqqq") == "TQQQ"
    assert config.normalize_ticker("brk.b") == "BRK.B"


def test_normalize_ticker_refuse_les_entrees_dangereuses():
    for raw in ("", "   ", "_SPX", "A B", "../../etc/passwd", "TOOLONGTICKER", "$$"):
        with pytest.raises(ValueError):
            config.normalize_ticker(raw)


def test_add_remove_target_persiste_dans_le_fichier(monkeypatch, tmp_path):
    ticker = "ZZZT"
    monkeypatch.setattr(config, "USER_TICKERS_FILE", tmp_path / "tickers.json")
    monkeypatch.setattr(config, "_USER_TICKERS", set())
    monkeypatch.setattr(config, "_WATCHED", set())
    try:
        u, created = config.add_target(ticker)
        assert created and u.role == "target" and u.source == "cboe"
        assert ticker in config.UNDERLYINGS
        assert json.loads((tmp_path / "tickers.json").read_text())["targets"] == [ticker]

        assert config.remove_target(ticker)
        assert ticker not in config.UNDERLYINGS
        assert json.loads((tmp_path / "tickers.json").read_text())["targets"] == []
    finally:
        config.UNDERLYINGS.pop(ticker, None)


def test_watch_constituent_ajoute_un_onglet_sans_changer_le_role(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "USER_TICKERS_FILE", tmp_path / "tickers.json")
    monkeypatch.setattr(config, "_USER_TICKERS", set())
    monkeypatch.setattr(config, "_WATCHED", set())
    u, newly = config.watch_constituent("NVDA")
    assert newly and u.role == "constituent"
    assert config.is_watched("NVDA")
    assert "NVDA" in {x.key for x in config.selectable_underlyings()}
    # Le rôle de constituant reste intact : ce n'est pas une cible/échelle.
    assert "NVDA" not in {x.key for x in config.targets()}
    assert json.loads((tmp_path / "tickers.json").read_text())["watched"] == ["NVDA"]
    _u, again = config.watch_constituent("NVDA")
    assert not again


def test_watch_refuse_une_cible_ou_un_inconnu(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "USER_TICKERS_FILE", tmp_path / "tickers.json")
    monkeypatch.setattr(config, "_WATCHED", set())
    u, newly = config.watch_constituent("SPX")
    assert not newly and u.role == "target"
    with pytest.raises(KeyError):
        config.watch_constituent("NOPE")
