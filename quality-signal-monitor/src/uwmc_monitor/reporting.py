"""Machine-readable outputs, charts, and the HTML/PDF report."""

from __future__ import annotations

import base64
import io
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from jinja2 import Environment, PackageLoader, select_autoescape

from . import __version__, narrative, signals, sources
from .validation import findings_frame

# Chart colors (validated categorical slot 1 and a neutral for the benchmark).
UWMC_COLOR = "#2a78d6"
NATIONAL_COLOR = "#8a8984"
INK, INK_MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def write_tables(result, out_dir: Path) -> dict[str, Path]:
    """Write CSV/JSON results. Returns the paths written."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "benchmark_comparisons": out_dir / "benchmark_comparisons.csv",
        "signals": out_dir / "ranked_signals.csv",
        "data_quality_findings": out_dir / "data_quality_findings.csv",
        "metadata": out_dir / "analysis_metadata.json",
    }
    result.comparison.to_csv(paths["benchmark_comparisons"], index=False)
    result.signals.to_csv(paths["signals"], index=False)
    findings_frame(result.findings).to_csv(paths["data_quality_findings"], index=False)
    if result.trends is not None:
        paths["release_changes"] = out_dir / "release_changes.csv"
        result.trends.to_csv(paths["release_changes"], index=False)
    paths["metadata"].write_text(json.dumps(metadata(result), indent=2, default=str), encoding="utf-8")
    return paths


def metadata(result) -> dict:
    return {
        "tool": "uwmc-quality-signal-monitor",
        "version": __version__,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "synthetic_data": bool(result.current.provenance.get("synthetic")),
        "hospital": result.current.hospital,
        "current_release": result.current.provenance,
        "previous_release": result.previous.provenance if result.previous else None,
        "counts": {
            "measures": int(len(result.comparison)),
            "comparable": int(result.comparison["comparable"].sum()) if len(result.comparison) else 0,
            "ranked_signals": int(len(result.signals)),
            "findings": {s: sum(f.severity == s for f in result.findings)
                         for s in ("failure", "anomaly", "info")},
        },
        "rules": {
            "gap_bands_pp": {label: floor for floor, label in signals.GAP_BANDS},
            "rounding_tolerance_pp": signals.ROUNDING_TOLERANCE_PP,
            "confidence_weights": signals.CONFIDENCE_WEIGHTS,
            "direction_rules": [{"pattern": r.pattern, "direction": r.direction, "meaning": r.meaning}
                                for r in signals.DIRECTION_RULES],
        },
    }


# ---------------------------------------------------------------- charts


def _short_label(row) -> str:
    text = row.hcahps_question or row.hcahps_answer_description or row.hcahps_measure_id
    text = text.replace("Patients who reported that their ", "").replace("Patients who ", "")
    text = text[0].upper() + text[1:] if text else text
    return (text[:52] + "…") if len(text) > 53 else text


def dot_chart(rows: pd.DataFrame, a_col: str, b_col: str, a_label: str, b_label: str,
              title: str, synthetic: bool, a_color: str = UWMC_COLOR,
              b_color: str = NATIONAL_COLOR) -> str | None:
    """Dumbbell chart, one row per measure. Returns a base64 PNG, or None if no rows."""
    if rows.empty:
        return None
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = rows.sort_values(a_col).reset_index(drop=True)
    h = 0.42 * len(rows) + 1.7
    fig, ax = plt.subplots(figsize=(8.2, h), dpi=160)
    y = range(len(rows))
    for i, r in rows.iterrows():
        ax.plot([r[b_col], r[a_col]], [i, i], color=GRID, lw=2, zorder=1, solid_capstyle="round")
    ax.scatter(rows[b_col], y, s=64, color=b_color, zorder=2, label=b_label,
               edgecolors="white", linewidths=1.5)
    ax.scatter(rows[a_col], y, s=64, color=a_color, zorder=3, label=a_label,
               edgecolors="white", linewidths=1.5)
    for i, r in rows.iterrows():
        ax.annotate(f"{r[a_col]:.0f}", (r[a_col], i), xytext=(0, 7), textcoords="offset points",
                    ha="center", fontsize=7.5, color=INK)
    ax.set_yticks(list(y), [f"{_short_label(r)}  ({r.hcahps_measure_id})" for r in rows.itertuples()],
                  fontsize=7.5, color=INK)
    lo = min(rows[a_col].min(), rows[b_col].min())
    ax.set_xlim(max(0, lo - 8), 100)
    ax.set_xlabel("Percent of patients (CMS-reported, adjusted)", fontsize=8, color=INK_MUTED)
    ax.tick_params(axis="x", labelsize=7.5, colors=INK_MUTED)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.legend(loc="upper center", fontsize=7.5, frameon=False, ncol=2,
              bbox_to_anchor=(0.5, -0.5 / h - 0.06))
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_title(("SYNTHETIC TEST DATA - " if synthetic else "") + title,
                 fontsize=9.5, loc="left", color=INK, pad=10)
    if synthetic:
        fig.text(0.5, 0.5, "SYNTHETIC", fontsize=60, color="#e34948", alpha=0.12,
                 ha="center", va="center", rotation=25)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ---------------------------------------------------------------- HTML / PDF


def _env() -> Environment:
    env = Environment(loader=PackageLoader("uwmc_monitor", "templates"),
                      autoescape=select_autoescape(["html", "j2"]))
    env.filters["pp"] = lambda x: "" if pd.isna(x) else narrative.fmt_pp(x)
    env.filters["pct"] = lambda x: "" if pd.isna(x) else f"{x:.0f}%"
    env.filters["num"] = lambda x: "" if pd.isna(x) else f"{x:,.0f}"
    return env


def render_html(result, narrator: narrative.Narrator | None = None) -> str:
    synthetic = bool(result.current.provenance.get("synthetic"))
    facts = narrative.build_facts(result)
    summary = (narrator or narrative.TemplateNarrator()).summarize(facts)
    comp = result.comparison
    top_box = comp[comp["comparable"] & (comp["direction"] == signals.HIGHER)] if len(comp) else comp
    other_comparable = comp[comp["comparable"] & (comp["direction"] != signals.HIGHER)] if len(comp) else comp
    not_comparable = comp[~comp["comparable"]] if len(comp) else comp
    focus = comp[comp["focus_domain"]] if len(comp) else comp
    focus_top = focus[focus["comparable"] & (focus["direction"] == signals.HIGHER)
                      & ~focus["retired_measure"]] if len(focus) else focus

    charts = {"focus": dot_chart(focus_top, "uwmc_percent", "national_percent", "UWMC", "National",
                                 "Discharge & care transitions: UWMC vs national", synthetic),
              "benchmark": dot_chart(top_box, "uwmc_percent", "national_percent",
                                     "UWMC", "National", "Favorable (top-box) responses: "
                                     "UWMC vs national", synthetic)}
    trends_ok = None
    if result.trends is not None:
        trends_ok = result.trends[result.trends["comparable"].fillna(False).astype(bool)]
        tb = trends_ok[trends_ok["direction"] == signals.HIGHER].merge(
            comp[["hcahps_measure_id", "hcahps_question", "hcahps_answer_description"]],
            on="hcahps_measure_id")
        charts["trend"] = dot_chart(tb, "current_percent", "previous_percent",
                                    f"Release {result.current.label}",
                                    f"Release {result.previous.label}",
                                    "UWMC top-box responses: current vs prior release",
                                    synthetic, b_color="#86b6ef")

    datasets = {d["key"]: d for d in result.current.provenance.get("datasets", [])}
    windows = sorted({f"{r.start_date} to {r.end_date}" for r in comp.itertuples()}) if len(comp) else []
    return _env().get_template("report.html.j2").render(
        generated=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        version=__version__,
        synthetic=synthetic,
        provenance=result.current.provenance,
        previous=result.previous.provenance if result.previous else None,
        sources=[(sources.DATASETS[k], datasets.get(k, {})) for k in sources.DATASETS],
        archive_url=sources.ARCHIVE_URL,
        hospital=result.current.hospital,
        windows=windows,
        summary=summary,
        facts=facts,
        signals=result.signals,
        top_box=top_box,
        focus=focus,
        other_comparable=other_comparable,
        not_comparable=not_comparable,
        trends=result.trends,
        trends_ok=trends_ok,
        findings=findings_frame(result.findings),
        charts=charts,
        rules=metadata(result)["rules"],
    )


def write_report(result, out_dir: Path, narrator=None, pdf: bool = False) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / "uwmc_quality_report.html"
    html_path.write_text(render_html(result, narrator), encoding="utf-8")
    written = {"html": html_path}
    if pdf:
        pdf_path = export_pdf(html_path)
        if pdf_path:
            written["pdf"] = pdf_path
    return written


CHROME_NAMES = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable",
                "chrome", "msedge", "microsoft-edge")


def export_pdf(html_path: Path) -> Path | None:
    """Convert to PDF with WeasyPrint or a local headless Chrome/Chromium, if either exists.

    Set UWMC_CHROME to a browser executable path if it is not on PATH.
    """
    pdf_path = html_path.with_suffix(".pdf")
    try:
        from weasyprint import HTML  # type: ignore
        HTML(filename=str(html_path)).write_pdf(str(pdf_path))
        return pdf_path
    except ImportError:
        pass
    candidates = [os.environ.get("UWMC_CHROME", "")] + list(CHROME_NAMES)
    for name in filter(None, candidates):
        exe = shutil.which(name)
        if not exe:
            continue
        cmd = [exe, "--headless", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer",
               f"--print-to-pdf={pdf_path}", html_path.resolve().as_uri()]
        proc = subprocess.run(cmd, capture_output=True, timeout=120)
        if proc.returncode == 0 and pdf_path.exists():
            return pdf_path
    return None
