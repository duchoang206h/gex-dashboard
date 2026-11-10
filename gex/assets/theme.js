/* Bascule Light / Dark du dashboard.
 *
 * Le thème est porté par un cookie (lisible côté Flask) et par
 * <html data-theme="...">. Le cookie est indispensable pour que les callbacks
 * Dash régénèrent les figures Plotly avec la bonne palette ; un simple
 * changement de classe CSS ne toucherait pas les couleurs encodées dans les
 * figures. Un rechargement est donc volontaire (rapide, page locale).
 */
(function () {
  "use strict";

  function current() {
    return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
  }

  function syncButton() {
    var b = document.getElementById("theme-toggle");
    if (!b) return;
    var dark = current() === "dark";
    b.textContent = dark ? "☀" : "☾";
    b.title = dark ? "Light mode" : "Dark mode";
    b.setAttribute("aria-label", b.title);
  }

  function boot() {
    var m = document.cookie.match(/(?:^|; )gex_theme=(dark|light)/);
    document.documentElement.dataset.theme = m ? m[1] : "light";
    syncButton();
    // Dash monte le layout après l'exécution des assets : on surveille
    // brièvement l'apparition du bouton plutôt que de dépendre d'un timing.
    var tries = 0;
    var iv = setInterval(function () {
      syncButton();
      if (++tries > 120 || document.getElementById("theme-toggle")) {
        clearInterval(iv);
      }
    }, 250);
  }

  // Couleur calculée depuis les variables CSS, utilisée par les graphiques
  // Lightweight Charts de /scalp (les figures Plotly, elles, sont régénérées
  // côté serveur avec la palette du thème).
  window.gexColor = function (name, fallback) {
    var v = getComputedStyle(document.documentElement)
      .getPropertyValue(name).trim();
    return v || fallback;
  };

  document.addEventListener("click", function (e) {
    var target = e.target;
    var b = target && target.closest ? target.closest("#theme-toggle") : null;
    if (!b) return;
    var next = current() === "dark" ? "light" : "dark";
    document.cookie = "gex_theme=" + next + "; path=/; max-age=31536000; SameSite=Lax";
    document.documentElement.dataset.theme = next;
    window.location.reload();
  }, true);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
