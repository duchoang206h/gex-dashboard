"""Unités monétaires adaptatives (GEX/DEX d'un petit ETF vs SPX)."""
from __future__ import annotations

from gex.app import fmt_money, money_unit


def test_unite_adaptee_a_la_magnitude():
    assert money_unit(40.6e9)[0] == "$Bn"
    assert money_unit(2.63e6)[0] == "$M"
    assert money_unit(961_684)[0] == "$K"
    assert money_unit(423)[0] == "$"


def test_format_signe_et_valeur():
    assert fmt_money(2_634_892, signed=True) == "+2.63 $M"
    assert fmt_money(-2_266_662, signed=True) == "-2.27 $M"
    assert fmt_money(40.6e9, signed=True) == "+40.60 $Bn"
