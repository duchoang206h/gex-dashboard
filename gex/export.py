"""Export partageable : n'extrait que les données issues de la source publique
CBOE, en excluant tout ce qui provient d'une source payante.

Pourquoi : les données Databento (et celles d'un flux courtier) sont sous
licence d'**usage personnel, non redistribuable**. Les métriques dérivées de la
source publique CBOE, elles, peuvent être partagées.

Principe de conception — **exclusion par défaut** : seules les lignes portant
explicitement `source == "cboe"` sont exportées. Toute donnée de provenance
inconnue ou absente est écartée. Une migration incomplète ou un schéma
inattendu ne peut donc pas provoquer de fuite : au pire l'export est vide.

Usage :
    python -m gex.export --migrate           # marque la provenance des données existantes
    python -m gex.export --out shared-data   # produit l'export partageable
"""
from __future__ import annotations

import argparse
import logging
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

from .config import SETTINGS

log = logging.getLogger(__name__)

SHAREABLE = "cboe"
PROVENANCE_FILE = "PROVENANCE.md"


# ------------------------------------------------------------------ migration

def migrate(dry_run: bool = False) -> dict[str, int]:
    """Ajoute la colonne `source` aux données déjà collectées.

    Heuristique documentée, appliquée UNE FOIS :
    - historique : une ligne horodatée exactement à 16:00:00 provient du
      backfill Databento (build_day pose la clôture à cette heure pile) ;
      toute autre heure vient d'un pull live CBOE.
    - flux : les fichiers antérieurs à cette migration proviennent tous du
      backfill. Ils sont marqués "databento" — choix volontairement prudent,
      un faux négatif ne coûte qu'une donnée non partagée.
    """
    stats = {"history_cboe": 0, "history_databento": 0, "flow_files": 0}

    hist_path = SETTINGS.data_dir / "history" / "metrics.parquet"
    if hist_path.exists():
        h = pd.read_parquet(hist_path)
        if "source" not in h.columns:
            ts = pd.to_datetime(h["timestamp"])
            is_backfill = ts.dt.time == datetime(2000, 1, 1, 16, 0, 0).time()
            h["source"] = pd.Series(SHAREABLE, index=h.index).mask(is_backfill, "databento")
            stats["history_cboe"] = int((~is_backfill).sum())
            stats["history_databento"] = int(is_backfill.sum())
            if not dry_run:
                h.to_parquet(hist_path, index=False)
        else:
            counts = h["source"].value_counts()
            stats["history_cboe"] = int(counts.get(SHAREABLE, 0))
            stats["history_databento"] = int(counts.get("databento", 0))

    for f in sorted((SETTINGS.data_dir / "flows").rglob("*.parquet")):
        d = pd.read_parquet(f)
        if "source" in d.columns:
            continue
        d["source"] = "databento"
        stats["flow_files"] += 1
        if not dry_run:
            d.to_parquet(f, index=False)

    return stats


# --------------------------------------------------------------------- export

def _filter_shareable(df: pd.DataFrame) -> pd.DataFrame:
    """Ne garde que les lignes explicitement marquées CBOE (exclusion par défaut)."""
    if "source" not in df.columns:
        return df.iloc[0:0]
    return df[df["source"] == SHAREABLE]


def export(out_dir: Path) -> dict:
    """Écrit dans out_dir la portion partageable des données."""
    out_dir = Path(out_dir)
    report = {"history_rows": 0, "history_excluded": 0,
              "flow_files": 0, "flow_rows": 0, "flow_excluded": 0,
              "days": [], "symbols": set()}

    # --- historique
    hist_path = SETTINGS.data_dir / "history" / "metrics.parquet"
    if hist_path.exists():
        h = pd.read_parquet(hist_path)
        keep = _filter_shareable(h)
        report["history_rows"] = len(keep)
        report["history_excluded"] = len(h) - len(keep)
        if len(keep):
            dest = out_dir / "history" / "metrics.parquet"
            dest.parent.mkdir(parents=True, exist_ok=True)
            keep.to_parquet(dest, index=False)
            report["symbols"] |= set(keep["symbol"].unique())

    # --- flux (un fichier par jour et par sous-jacent)
    for f in sorted((SETTINGS.data_dir / "flows").rglob("*.parquet")):
        d = pd.read_parquet(f)
        keep = _filter_shareable(d)
        report["flow_excluded"] += len(d) - len(keep)
        if keep.empty:
            continue
        dest = out_dir / "flows" / f.parent.name / f.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        keep.to_parquet(dest, index=False)
        report["flow_files"] += 1
        report["flow_rows"] += len(keep)
        report["days"].append(f.stem)
        report["symbols"].add(f.parent.name)

    report["days"] = sorted(set(report["days"]))
    report["symbols"] = sorted(report["symbols"])
    if report["history_rows"] or report["flow_files"]:
        _write_provenance(out_dir, report)
    return report


def _write_provenance(out_dir: Path, report: dict) -> None:
    """Note de provenance jointe à l'export — indispensable pour que le
    destinataire sache ce qu'il reçoit et à quelles conditions."""
    days = report["days"]
    span = f"{days[0]} → {days[-1]}" if days else "—"
    (out_dir / PROVENANCE_FILE).write_text(f"""# Data provenance

Export generated on {datetime.now():%Y-%m-%d %H:%M} by
[gex-dashboard](https://github.com/Darthreign/gex-dashboard)
(`python -m gex.export`).

## What this export contains

- **Single source: the public *delayed* CBOE endpoint**, free and
  accessible without an account.
- These are not raw quotes but **derived metrics** computed
  locally: net GEX, Gamma Flip, put/call ratios, delta flow aggregates.
- Underlyings: {', '.join(report['symbols']) or '—'}
- History: {report['history_rows']} rows
- Flows: {report['flow_files']} day files, {report['flow_rows']} bars ({span})

## What it does not contain

Any data from a **paid source** (Databento, broker feed) is
excluded by construction: only rows explicitly marked
`source = "cboe"` are exported. Those sources are subject to a
personal-use, non-redistributable license.

Rows excluded on that basis: {report['history_excluded']} in history,
{report['flow_excluded']} in flows.

## Usage

Copy `history/` and `flows/` into the `data/` folder of your own
instance. Your subsequent collections will be added there normally.

Provided **without warranty**, for informational purposes only, and not constituting investment
advice — see the [disclaimer](https://github.com/Darthreign/gex-dashboard/blob/main/DISCLAIMER.md).
""", encoding="utf-8")


# ----------------------------------------------------------------------- main

def main() -> None:
    from .logsetup import setup_logging
    setup_logging()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--migrate", action="store_true",
                    help="mark the provenance of already-collected data")
    ap.add_argument("--out", type=Path, default=None,
                    help="destination folder for the export")
    ap.add_argument("--force", action="store_true",
                    help="overwrite the destination folder if it exists")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.migrate:
        s = migrate(dry_run=a.dry_run)
        log.info("Migration%s — history: %d CBOE / %d Databento; "
                 "%d flow files marked",
                 " (dry run)" if a.dry_run else "",
                 s["history_cboe"], s["history_databento"], s["flow_files"])

    if a.out:
        if a.out.exists():
            if not a.force:
                raise SystemExit(f"{a.out} already exists — use --force to overwrite it.")
            shutil.rmtree(a.out)
        r = export(a.out)
        if not r["history_rows"] and not r["flow_files"]:
            log.warning("Export EMPTY: no data marked '%s'. "
                        "Run --migrate first, or collect live.", SHAREABLE)
            return
        log.info("Export to %s", a.out)
        log.info("  history : %d rows (%d excluded)",
                 r["history_rows"], r["history_excluded"])
        log.info("  flows   : %d files, %d bars (%d excluded)",
                 r["flow_files"], r["flow_rows"], r["flow_excluded"])
        log.info("  %s attached", PROVENANCE_FILE)

    if not a.migrate and not a.out:
        ap.print_help()


if __name__ == "__main__":
    main()
