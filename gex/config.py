"""Configuration centrale du dashboard GEX."""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

def _default_data_dir() -> Path:
    """data/ à la racine du dépôt si on tourne depuis les sources, sinon dans
    le dossier courant (cas d'un `pip install` : le code vit dans
    site-packages, où l'on n'écrit pas)."""
    root = Path(__file__).resolve().parent.parent
    if (root / ".git").exists() or (root / "pyproject.toml").exists():
        return root / "data"
    return Path.cwd() / "data"


DATA_DIR = _default_data_dir()

# Taux sans risque annualisé, REPLI uniquement : le calcul live charge le SOFR
# du jour via gex/rates (current_rate). Cette constante ne sert plus que si
# l'API NY Fed est injoignable, et pour la reconstruction historique
# (backfill), où le taux du jour serait anachronique.
RISK_FREE_RATE = 0.045

# Multiplicateur de contrat (SPX, NDX, SPY, QQQ : 100).
CONTRACT_MULTIPLIER = 100


@dataclass(frozen=True)
class Underlying:
    key: str            # identifiant interne ("SPX")
    cboe_symbol: str    # symbole endpoint CBOE ("_SPX")
    label: str          # libellé affiché ("SPX / ES")
    future: str | None = None   # future CME associé, pour la conversion de basis
    # Famille d'indice : la transposition entre familles est possible mais son
    # ratio dérive dans le temps (cf. gex/scales.py).
    family: str = "SP"
    enabled: bool = True
    # "target"      : sous-jacent analysé, visible dans l'interface
    # "constituent" : collecté uniquement pour alimenter les niveaux de
    #                 confluence (Blind Spots) — jamais proposé à l'affichage,
    #                 et pullé plus lentement car ses murs reposent sur l'open
    #                 interest, publié une fois par jour
    # "context"     : pas une chaîne d'options — juste un ticker de contexte
    #                 (VIX) pullé à part (scheduler.pull_vix) et absent de
    #                 pull_all. Listé ici uniquement pour que
    #                 rtquote.resolve_symbols l'inclue dans l'abonnement
    #                 dxFeed du compte courtier, quand un est configuré.
    role: str = "target"
    # Cibles que ce constituant informe. Un titre présent dans deux indices
    # (AAPL, MSFT…) en alimente deux.
    links: tuple[str, ...] = ()
    # "cboe"    : chaîne pullée depuis l'endpoint CBOE toutes les 60 s
    #             (gex/ingest.py), boucle pull_all normale.
    # "futopt"  : chaîne d'options sur future lue nativement via dxFeed
    #             (gex/futopt.py). Une collecte prend ~90 s par sous-jacent —
    #             hors de question dans la boucle à 60 s : pull_native_options
    #             s'en charge séparément, toutes les 15 min, dans son propre
    #             thread (cf. scheduler.py). pull_all les ignore entièrement.
    # "future"  : le sous-jacent EST un future, suivi en spot seul — aucune
    #             chaîne d'options n'est collectée. Sert aux axes intermarket
    #             (taux, WTI, or, devises). Comme "futopt", la clé ne doit
    #             JAMAIS servir de symbole dxFeed telle quelle (cf.
    #             rtquote._is_future_key) : "ZN", "GC", "CL" sont aussi des
    #             tickers d'actions sans rapport.
    source: str = "cboe"


UNDERLYINGS: dict[str, Underlying] = {
    u.key: u
    for u in [
        # libellés = simples tickers : l'échelle d'affichage (ES/NQ) se choisit
        # dans son propre sélecteur, la mentionner ici ferait doublon
        Underlying("SPX", "_SPX", "SPX", future="ES", family="SP"),
        Underlying("NDX", "_NDX", "NDX", future="NQ", family="ND"),
        # ETF : pas de future associé (le sélecteur Indice/Futures est donc
        # désactivé), options américaines, et sous-jacents versant un dividende
        # — voir la note sur l'approximation q=0 dans les limites du README.
        Underlying("SPY", "SPY", "SPY", family="SP"),
        Underlying("QQQ", "QQQ", "QQQ", family="ND"),

        # Options sur future, lues nativement (gex/futopt.py) plutôt que
        # transposées depuis NDX/SPX : la structure de gamma propre au marché
        # des futures diverge de celle de l'indice cash — confirmé le
        # 2026-07-27, écart de 160 pts sur le Zero Gamma NQ en transposé
        # contre 12 pts en natif face à une source tierce. `cboe_symbol` est
        # un placeholder ignoré : ces deux cibles ne passent jamais par la
        # boucle CBOE (source="futopt").
        Underlying("NQ", "NQ", "NQ", family="ND", source="futopt"),
        Underlying("ES", "ES", "ES", family="SP", source="futopt"),

        # --- Constituants (Blind Spots) -------------------------------------
        # Leurs murs de gamma n'ont d'intérêt que projetés sur l'indice qu'ils
        # composent : un mur sur NVDA pèse sur le NQ parce que le titre pèse
        # ~9 % de l'indice et que ceux qui couvrent ce gamma tradent NVDA.
        # C'est ce lien mécanique qui distingue un constituant d'un actif
        # simplement corrélé (l'or face à l'ES n'a pas cette propriété).
        *[Underlying(k, k, k, family="ND", role="constituent",
                     links=("NDX", "SPX"))
          for k in ("SMH", "NVDA", "AVGO", "AMD", "MU", "TSM")],
        # Méga-capitalisations : présentes dans les deux indices, avec un poids
        # supérieur dans le Nasdaq-100
        *[Underlying(k, k, k, family="ND", role="constituent",
                     links=("NDX", "SPX"))
          for k in ("AAPL", "MSFT", "AMZN", "META", "GOOGL", "TSLA")],
        # Reste du top 30 Nasdaq-100 par capitalisation (ajouté le 2026-09-30 —
        # Micron avait été repéré manquant alors qu'il pèse sur le complexe
        # semis). Tous membres à la fois du Nasdaq-100 et du S&P 500. Liste
        # recoupée avec earnings_calendar.json (source externe rafraîchie
        # chaque matin) plutôt que composée de mémoire.
        *[Underlying(k, k, k, family="ND", role="constituent",
                     links=("NDX", "SPX"))
          for k in ("COST", "NFLX", "PEP", "ADBE", "CSCO", "AMAT", "QCOM",
                    "TXN", "INTU", "ADP", "BKNG", "GILD", "VRTX", "AMGN",
                    "PANW", "ISRG", "CMCSA", "HON", "TMUS", "LIN")],
        # Secteurs absents du Nasdaq-100 : ils n'informent que le S&P
        *[Underlying(k, k, k, family="SP", role="constituent", links=("SPX",))
          for k in ("XLF", "XLE")],

        # Contexte (get_market_context, MCP) : `cboe_symbol` est un
        # placeholder ignoré, VIX ne passe jamais par la boucle CBOE
        # (cf. role="context" et scheduler.pull_vix, qui utilise directement
        # le symbole CBOE "_VIX").
        Underlying("VIX", "VIX", "VIX", family="SP", role="context"),
        # Axes intermarket, en spot seul (aucune chaîne d'options collectée).
        # Résolus en contrat front par resolve_symbols et abonnés au flux dxFeed
        # comme n'importe quel future — c'est la seule source gratuite et
        # temps réel dont nous disposions pour ces marches : la CDN CBOE ne sert
        # que _VIX (tout le reste répond 403, vérifié le 2026-09-22).
        #
        # ⚠️ ZT/ZN cotent un PRIX d'obligation, pas un rendement : prix en
        # hausse = taux en BAISSE. Toute lecture de divergence doit inverser.
        #
        # Le dollar index (DX) n'est pas porté par le courtier (produit ICE) :
        # 6E (EUR/USD) en tient lieu, l'euro pesant ~57 % du panier, en sens
        # inverse.
        Underlying("ZT", "ZT", "2Y T-Note", future="ZT", family="SP",
                   role="context", source="future"),
        Underlying("ZN", "ZN", "10Y T-Note", future="ZN", family="SP",
                   role="context", source="future"),
        Underlying("CL", "CL", "WTI", future="CL", family="SP",
                   role="context", source="future"),
        Underlying("GC", "GC", "Or", future="GC", family="SP",
                   role="context", source="future"),
        Underlying("6E", "6E", "EUR/USD", future="6E", family="SP",
                   role="context", source="future"),
    ]
}


# --- tickers ajoutés depuis l'interface -----------------------------------
# Les cibles du bloc ci-dessus sont statiques ; celles-ci sont saisies dans la
# barre de recherche du dashboard et persistent dans data/tickers.json. Elles
# suivent exactement le même chemin de collecte que SPX/SPY/QQQ (endpoint CBOE
# delayed, pull 60 s), d'où l'insertion directe dans UNDERLYINGS : scheduler,
# échelles et callbacks lisent déjà ce dictionnaire.
USER_TICKERS_FILE = DATA_DIR / "tickers.json"
_TICKERS_LOCK = threading.RLock()
_USER_TICKERS: set[str] = set()
# Constituants déjà collectés pour la confluence, mais explicitement affichés
# comme onglets par l'utilisateur. Aucun doublon de collecte : le scheduler les
# rafraîchit à 60 s et le balayage constituants les ignore.
_WATCHED: set[str] = set()

# Tickers dont l'univers sous-jacent est technologique / Nasdaq. Sert
# uniquement à choisir la famille d'échelle (SP vs ND) pour les transpositions ;
# un ticker inconnu retombe sur SP, qui n'a aucun effet sur son propre GEX.
_ND_TICKERS = {
    "QQQ", "TQQQ", "SQQQ", "SMH", "SOXX", "SOXL", "SOXS", "NVDA", "AMD",
    "AVGO", "MU", "TSM", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "TSLA",
}


def normalize_ticker(raw: str | None) -> str:
    """Normalise un ticker saisi (majuscules, sans « $ ») et le valide.

    Volontairement strict : le ticker part ensuite tel quel dans une URL CBOE.
    Les indices CBOE (`_SPX`) ne sont pas acceptés ici — les cibles existantes
    les couvrent déjà.
    """
    ticker = (raw or "").strip().upper().lstrip("$")
    # Les points sont légitimes (BRK.B, BF.B) : l'endpoint CBOE les accepte
    # tels quels, contrairement à la variante soulignée utilisée ailleurs.
    if not re.fullmatch(r"[A-Z][A-Z0-9.]{0,9}", ticker):
        raise ValueError("invalid ticker")
    return ticker


def _read_user_config() -> tuple[list[str], list[str]]:
    """(cibles ajoutées, constituants surveillés) depuis data/tickers.json.

    L'ancien format était une simple liste (ou {"targets": [...]}) : il reste
    accepté, pour ne pas perdre les tickers déjà ajoutés.
    """
    try:
        raw = json.loads(USER_TICKERS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [], []
    except Exception:  # noqa: BLE001 — un fichier corrompu ne doit pas bloquer
        log.warning("tickers.json unreadable — list ignored", exc_info=True)
        return [], []
    if isinstance(raw, list):
        targets, watched = raw, []
    elif isinstance(raw, dict):
        targets, watched = raw.get("targets", []), raw.get("watched", [])
    else:
        return [], []

    def clean(items) -> list[str]:
        out = []
        if not isinstance(items, list):
            return out
        for item in items:
            try:
                out.append(normalize_ticker(item))
            except (TypeError, ValueError):
                continue
        return out

    return clean(targets), clean(watched)


def _save_user_tickers() -> None:
    """Écriture atomique : le dashboard peut tourner pendant l'ajout."""
    USER_TICKERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = USER_TICKERS_FILE.with_suffix(".json.tmp")
    payload = json.dumps({
        "targets": sorted(_USER_TICKERS),
        "watched": sorted(_WATCHED),
    }, indent=2) + "\n"
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, USER_TICKERS_FILE)


def _guess_family(ticker: str) -> str:
    return "ND" if ticker in _ND_TICKERS else "SP"


def _load_user_tickers() -> None:
    targets, watched = _read_user_config()
    for ticker in targets:
        if ticker in UNDERLYINGS:
            continue
        UNDERLYINGS[ticker] = Underlying(
            ticker, ticker, ticker, family=_guess_family(ticker))
        _USER_TICKERS.add(ticker)
    for ticker in watched:
        u = UNDERLYINGS.get(ticker)
        if u is not None and u.enabled and u.role == "constituent":
            _WATCHED.add(ticker)


def add_target(raw: str) -> tuple[Underlying, bool]:
    """Ajoute un ticker comme cible CBOE. Renvoie (underlying, créé).

    `créé=False` si le ticker existe déjà (cible, constituant ou future) :
    l'appelant décide alors du message à afficher, sans écraser le rôle.
    """
    ticker = normalize_ticker(raw)
    with _TICKERS_LOCK:
        existing = UNDERLYINGS.get(ticker)
        if existing is not None:
            return existing, False
        u = Underlying(ticker, ticker, ticker, family=_guess_family(ticker))
        UNDERLYINGS[ticker] = u
        _USER_TICKERS.add(ticker)
        _save_user_tickers()
        return u, True


def remove_target(ticker: str) -> bool:
    """Retire un ticker AJOUTÉ par l'utilisateur (rollback ou suppression).

    Ne touche jamais aux cibles statiques ni aux constituants.
    """
    ticker = ticker.strip().upper()
    with _TICKERS_LOCK:
        if ticker not in _USER_TICKERS:
            return False
        _USER_TICKERS.discard(ticker)
        UNDERLYINGS.pop(ticker, None)
        _save_user_tickers()
        return True


def watch_constituent(raw: str) -> tuple[Underlying, bool]:
    """Affiche un constituant existant comme onglet, sans le re-collecter.

    Renvoie (underlying, nouvellement_surveillé). Un ticker qui n'est pas un
    constituant n'est pas transformé : l'appelant garde son rôle d'origine.
    """
    ticker = normalize_ticker(raw)
    with _TICKERS_LOCK:
        u = UNDERLYINGS.get(ticker)
        if u is None:
            raise KeyError(ticker)
        if u.role != "constituent":
            return u, False
        if ticker in _WATCHED:
            return u, False
        _WATCHED.add(ticker)
        _save_user_tickers()
        return u, True


def is_watched(ticker: str) -> bool:
    with _TICKERS_LOCK:
        return ticker in _WATCHED


def selectable_underlyings() -> list[Underlying]:
    """Onglets proposés : cibles + constituants explicitement surveillés.

    `targets()` reste volontairement inchangé : un constituant surveillé ne
    devient pas une échelle de transposition. Seul le sélecteur l'accueille.
    """
    with _TICKERS_LOCK:
        out = [u for _, u in UNDERLYINGS.items()
               if u.enabled and u.role == "target"]
        for key in sorted(_WATCHED):
            u = UNDERLYINGS.get(key)
            if u is not None and u.enabled and u.role == "constituent":
                out.append(u)
        return out


_load_user_tickers()


def all_underlyings() -> list[tuple[str, Underlying]]:
    """Copie thread-safe de UNDERLYINGS.

    Un ticker peut être ajouté par un callback pendant que le scheduler
    parcourt le dictionnaire : itérer directement lèverait « dictionary changed
    size during iteration ». Tout parcours doit passer par cette copie.
    """
    with _TICKERS_LOCK:
        return list(UNDERLYINGS.items())


def targets() -> list[Underlying]:
    """Sous-jacents analysés — ceux que l'interface propose."""
    return [u for _, u in all_underlyings() if u.enabled and u.role == "target"]


def constituents(for_target: str | None = None) -> list[Underlying]:
    """Constituants collectés pour les niveaux de confluence.

    `for_target` restreint à ceux qui informent une cible donnée.
    """
    out = [u for _, u in all_underlyings()
           if u.enabled and u.role == "constituent"]
    if for_target:
        out = [u for u in out if for_target in u.links]
    return out


@dataclass
class Settings:
    # Intervalle de pull des flux (secondes). 60 s = résolution max utile
    # (le feed CBOE est délayé 15 min à la source, ceci ne change que la
    # résolution d'échantillonnage, pas le délai).
    flow_interval_s: int = 60
    # Intervalle de persistance d'un snapshot complet de chaîne (secondes).
    snapshot_interval_s: int = 600
    # Cadence de pull des constituants. Bien plus lente que les cibles : leurs
    # murs reposent sur l'open interest, publié une fois par jour. Les puller
    # toutes les 60 s n'apporterait rien et multiplierait par quatre la charge
    # sur le CDN gratuit de CBOE comme le volume d'écriture Parquet.
    constituent_interval_s: int = 600
    # Persistance des snapshots de constituants. Très espacée : leurs murs
    # dépendent de l'open interest, publié une fois par jour — en garder une
    # photo toutes les 10 min ferait ~270 Mo/jour de doublons pour rien.
    constituent_snapshot_interval_s: int = 7200
    # Fenêtre de strikes affichée autour du spot (fraction).
    strike_window: float = 0.10
    # Grille de recherche du zero gamma autour du spot (fraction, pas).
    zg_range: float = 0.08
    zg_steps: int = 161
    # Ne puller que pendant les heures de marché US (ET).
    market_hours_only: bool = True
    # Commit+push automatique du repo git data/ (historique+flux) après la
    # clôture (16:20 ET). Sans effet si data/ n'est pas un repo git avec remote.
    auto_push_data: bool = True
    data_dir: Path = field(default_factory=lambda: DATA_DIR)


SETTINGS = Settings()
