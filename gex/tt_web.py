"""Connexion tastytrade depuis le dashboard, sans copier-coller.

Remplace la gymnastique de `python -m gex.tt_auth` (ouvrir une URL, atterrir
sur une page d'erreur, recopier le `code=` de la barre d'adresse, puis `setx`)
par deux clics : « Connecter », approuver.

Ce qui rend ça possible : l'URI de redirection enregistrée côté tastytrade est
`http://localhost:8050/oauth/callback`, donc le navigateur revient sur le
dashboard lui-même — qui peut alors lire le code et faire l'échange.

⚠️ Portée. Ces routes ne servent QUE l'autorisation, en scope `read`. Ce
serveur n'écoute qu'en local (cf. gex/api.py) et le projet n'exécute aucun
ordre : un jeton obtenu ici ne peut pas trader, par construction.

Sécurité de l'échange :
- un `state` aléatoire à usage unique est vérifié au retour. Sans lui, une
  page tierce pourrait déclencher notre callback avec SON code
  d'autorisation, et le dashboard enregistrerait le jeton de quelqu'un
  d'autre (« OAuth code injection ») ;
- le `code` et le `client_secret` ne transitent que vers l'API tastytrade ;
- le refresh token obtenu n'est jamais affiché ni journalisé, seulement
  rangé là où `rtquote._env` le lit déjà (cf. tt_auth.store_refresh).
"""
from __future__ import annotations

import logging
import secrets
import threading

from flask import Flask, redirect, request

from . import tt_auth
from .rtquote import credentials_present

log = logging.getLogger(__name__)

# `state` en attente, à usage unique. Un dict plutôt qu'une valeur simple :
# rien n'interdit à l'utilisateur de cliquer deux fois puis de terminer la
# première autorisation. Borné pour ne pas croître indéfiniment si des
# tentatives sont abandonnées.
_PENDING: dict[str, float] = {}
_PENDING_LOCK = threading.Lock()
_MAX_PENDING = 8


def _page(titre: str, message: str, ok: bool) -> str:
    """Page de retour minimale, aux couleurs du thème courant."""
    dark = request.cookies.get("gex_theme") == "dark"
    couleur = "#7fd1a9" if ok and dark else ("#f28b82" if dark else
                                             "#047857" if ok else "#dc2626")
    bg = "#16181d" if dark else "#f2f2f0"
    surface = "#1f2228" if dark else "#f7f7f4"
    ink = "#e8e6e1" if dark else "#111827"
    accent = "#7aa2f7" if dark else "#2563eb"
    shadow = "rgba(0,0,0,.45)" if dark else "rgba(17,24,39,.12)"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>{titre}</title></head>
<body style="background:{bg};color:{ink};font-family:system-ui,sans-serif;
             display:flex;align-items:center;justify-content:center;
             height:100vh;margin:0">
  <div style="max-width:34rem;padding:2rem;border-left:3px solid {couleur};
              background:{surface};border-radius:10px;
              box-shadow:0 12px 40px {shadow}">
    <h1 style="margin:0 0 .6rem;font-size:1.1rem;color:{couleur}">{titre}</h1>
    <p style="margin:0 0 1.2rem;line-height:1.5">{message}</p>
    <a href="/" style="color:{accent}">Back to dashboard</a>
  </div>
</body></html>"""


def _remember_state() -> str:
    import time

    state = secrets.token_urlsafe(24)
    with _PENDING_LOCK:
        if len(_PENDING) >= _MAX_PENDING:
            # purge le plus ancien : une tentative abandonnée ne doit pas
            # bloquer les suivantes
            plus_vieux = min(_PENDING, key=_PENDING.get)
            _PENDING.pop(plus_vieux, None)
        _PENDING[state] = time.time()
    return state


def _consume_state(state: str | None) -> bool:
    """Vrai si le state était bien en attente. À usage unique : un même state
    ne peut pas servir deux fois."""
    if not state:
        return False
    with _PENDING_LOCK:
        return _PENDING.pop(state, None) is not None


def connection_status() -> tuple[str, str]:
    """(état, message) de la connexion courtier, pour l'affichage.

    `credentials_present` exige les trois valeurs : sans identifiants d'appli,
    il n'y a même pas de quoi lancer une autorisation — le message doit dire
    laquelle manque plutôt qu'un « non connecté » indifférencié.
    """
    from .rtquote import _env

    cid = _env("TASTYTRADE_CLIENT_ID")
    secret = _env("TASTYTRADE_CLIENT_SECRET")
    refresh = _env("TT_REFRESH")
    if not cid or not secret:
        return "absent", ("Missing application credentials "
                          "(TASTYTRADE_CLIENT_ID / _SECRET).")
    if not refresh:
        return "deconnecte", "Application configured — authorization still required."
    return "connecte", "tastytrade account connected (read-only)."


def register_oauth(app) -> None:
    """`app` : instance Dash (on grimpe à `.server`) ou Flask directement —
    comme `api.register_api`, pour que les tests n'aient pas à monter tout le
    dashboard."""
    server: Flask = app.server if hasattr(app, "server") else app

    @server.route("/oauth/start")
    def _oauth_start():
        from .rtquote import _env

        cid = _env("TASTYTRADE_CLIENT_ID")
        if not cid:
            return _page("Incomplete configuration",
                         "TASTYTRADE_CLIENT_ID is missing. Create an "
                         "OAuth application on tastytrade "
                         "(Manage → My Profile → API), then set "
                         "TASTYTRADE_CLIENT_ID and TASTYTRADE_CLIENT_SECRET.",
                         ok=False), 400
        return redirect(tt_auth.authorize_url(cid, state=_remember_state()))

    @server.route("/oauth/callback")
    def _oauth_callback():
        erreur = request.args.get("error")
        if erreur:
            # refus explicite côté tastytrade : ce n'est pas une panne
            return _page("Authorization denied",
                         f"tastytrade returned: {erreur}. "
                         "Nothing was saved.", ok=False), 400

        if not _consume_state(request.args.get("state")):
            log.warning("OAuth: invalid or expired state, exchange denied")
            return _page("Unrecognized request",
                         "This authorization does not match any request "
                         "started from this dashboard. For safety, nothing was "
                         "saved — restart from the Connect button.",
                         ok=False), 400

        code = request.args.get("code")
        if not code:
            return _page("Missing code",
                         "tastytrade did not return an authorization code.",
                         ok=False), 400

        try:
            cid, secret = tt_auth.credentials()
            data = tt_auth.exchange_code(cid, secret, code)
        except SystemExit as exc:      # tt_auth signale ses échecs ainsi
            log.warning("OAuth: exchange denied (%s)", exc)
            return _page("Exchange denied", str(exc), ok=False), 400
        except Exception:              # noqa: BLE001 — réseau, JSON malformé…
            log.exception("OAuth: code exchange failed")
            return _page("Exchange failed",
                         "Unable to contact tastytrade. "
                         "Check the connection and try again.", ok=False), 502

        refresh = data.get("refresh_token")
        if not refresh:
            return _page("Unexpected response",
                         "No refresh_token in the tastytrade response.",
                         ok=False), 502

        note = tt_auth.store_refresh(refresh)
        # le jeton lui-même n'est JAMAIS journalisé
        log.info("tastytrade OAuth: connection successful. %s", note)
        _demarrer_les_flux()
        return _page("Connected to tastytrade",
                     f"{note} Real-time streams are starting — data "
                     "will appear within a minute.", ok=True)


def _demarrer_les_flux() -> None:
    """Démarre les flux qui refusaient de tourner faute d'identifiants.

    Sans cela, il faudrait redémarrer le dashboard juste après s'être
    connecté — ce qui reviendrait à remplacer un copier-coller par un
    redémarrage. `start()` est idempotent des deux côtés.
    """
    try:
        if credentials_present():
            from .flowtape import TAPE
            from .rtquote import QUOTES
            from .tickcapture import CAPTURE

            QUOTES.start()
            from .capturebus import remote_url
            if remote_url() is None:     # mode séparé : le process capture s'en charge
                TAPE.start()
                CAPTURE.start()
    except Exception:  # noqa: BLE001 — un flux qui refuse de démarrer ne doit
        log.exception("Starting streams after connection")
