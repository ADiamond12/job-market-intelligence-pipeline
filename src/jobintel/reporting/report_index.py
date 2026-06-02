from __future__ import annotations

from html import escape
from typing import Any, Mapping

from jobintel.domain.models import RunManifest


def render_report_index_markdown(manifest: RunManifest, history_payload: Mapping[str, Any]) -> str:
    totals = manifest.totals
    artifacts = manifest.artifacts
    delta = {
        "new": totals.get("new_jobs", 0),
        "removed": totals.get("removed_jobs", 0),
        "changed": totals.get("changed_jobs", 0),
    }
    lines = [
        "# Job Market Intelligence Report Index",
        "",
        f"Run ID: `{manifest.run_id}`",
        f"Status: **{manifest.status}**",
        "",
        "## Open First",
        f"- Market summary HTML: `{artifacts.get('market_summary_html', '')}`",
        f"- History trend report: `{artifacts.get('history_trend_report_markdown', '')}`",
        f"- Run manifest: `{artifacts.get('run_manifest', '')}`",
        "",
        "## What This Run Proves",
        "- Fixture-backed ATS collection can be rerun without live network access.",
        "- Validation, enrichment, data-quality reporting, manifests, and DuckDB history run together.",
        "- The second fixture run produces deltas instead of a single static export.",
        "",
        "## Run Movement",
        f"- Published jobs: {totals.get('published_jobs', 0)}",
        f"- New jobs: {delta['new']}",
        f"- Removed jobs: {delta['removed']}",
        f"- Changed jobs: {delta['changed']}",
        f"- History runs included: {history_payload.get('total_runs', 0)}",
        "",
        "## Artifact Map",
    ]
    for label in (
        "market_summary_html",
        "market_summary",
        "market_summary_data",
        "quality_report",
        "delta_report",
        "history_trend_report_markdown",
        "history_trend_report_json",
        "jobs_csv",
        "jobs_json",
        "run_manifest",
    ):
        value = artifacts.get(label)
        if value:
            lines.append(f"- {label}: `{value}`")
    return "\n".join(lines).strip() + "\n"


def render_report_index_html(manifest: RunManifest, history_payload: Mapping[str, Any]) -> str:
    totals = manifest.totals
    artifacts = manifest.artifacts
    cards = [
        ("Published jobs", totals.get("published_jobs", 0)),
        ("New jobs", totals.get("new_jobs", 0)),
        ("Removed jobs", totals.get("removed_jobs", 0)),
        ("Changed jobs", totals.get("changed_jobs", 0)),
        ("History runs", history_payload.get("total_runs", 0)),
    ]
    artifact_rows = "".join(
        f"<tr><th>{escape(label.replace('_', ' ').title())}</th><td>{escape(str(value))}</td></tr>"
        for label, value in artifacts.items()
        if label
        in {
            "market_summary_html",
            "market_summary",
            "market_summary_data",
            "quality_report",
            "delta_report",
            "history_trend_report_markdown",
            "history_trend_report_json",
            "jobs_csv",
            "jobs_json",
            "run_manifest",
        }
    )
    card_html = "".join(
        f"<article class=\"card\"><span>{escape(label)}</span><strong>{escape(str(value))}</strong></article>"
        for label, value in cards
    )
    open_first = artifacts.get("market_summary_html", "")
    history_path = artifacts.get("history_trend_report_markdown", "")
    manifest_path = artifacts.get("run_manifest", "")
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "  <title>Job Market Intelligence Report Index</title>\n"
        f"  <style>{_styles()}</style>\n"
        "</head>\n"
        "<body>\n"
        "  <main>\n"
        "    <header class=\"hero\">\n"
        "      <p class=\"eyebrow\">Open this first</p>\n"
        "      <h1>Job Market Intelligence Report Index</h1>\n"
        f"      <p class=\"lede\">Run {escape(manifest.run_id)} packages the report, quality checks, deltas, history, and manifest into one reviewer path.</p>\n"
        f"      <p class=\"primary-link\">Market summary: <code>{escape(str(open_first))}</code></p>\n"
        "    </header>\n"
        f"    <section class=\"cards\">{card_html}</section>\n"
        "    <section class=\"panel\">\n"
        "      <h2>Reviewer path</h2>\n"
        "      <ol>\n"
        f"        <li>Open the market summary HTML: <code>{escape(str(open_first))}</code></li>\n"
        f"        <li>Check the history trend report: <code>{escape(str(history_path))}</code></li>\n"
        f"        <li>Inspect the run manifest: <code>{escape(str(manifest_path))}</code></li>\n"
        "      </ol>\n"
        "    </section>\n"
        "    <section class=\"panel\">\n"
        "      <h2>What this run proves</h2>\n"
        "      <ul>\n"
        "        <li>Fixture-backed ATS collection can be rerun without live network access.</li>\n"
        "        <li>Validation, enrichment, data-quality reporting, manifests, and DuckDB history run together.</li>\n"
        "        <li>The second fixture run produces deltas instead of a single static export.</li>\n"
        "      </ul>\n"
        "    </section>\n"
        "    <section class=\"panel\">\n"
        "      <h2>Artifact map</h2>\n"
        f"      <table>{artifact_rows}</table>\n"
        "    </section>\n"
        "  </main>\n"
        "</body>\n"
        "</html>\n"
    )


def _styles() -> str:
    return (
        ":root{color-scheme:light;--bg:#f4f3ef;--panel:#fff;--text:#18212a;--muted:#64707a;"
        "--accent:#0f766e;--border:#d8d4ca}*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,"
        "-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--text);line-height:1.55}"
        "main{width:min(1080px,calc(100vw - 28px));margin:24px auto}.hero,.panel,.card{background:var(--panel);"
        "border:1px solid var(--border);border-radius:14px;box-shadow:0 1px 2px rgba(31,41,55,.08)}.hero{padding:28px;"
        "border-top:6px solid #17212b}.eyebrow{margin:0 0 8px;color:var(--accent);text-transform:uppercase;"
        "font-size:.76rem;font-weight:800;letter-spacing:.08em}h1{margin:0 0 12px;font-size:clamp(1.8rem,4vw,2.8rem);"
        "line-height:1.08}h2{margin:0 0 12px}.lede{max-width:72ch;color:var(--muted)}.primary-link{margin:14px 0 0}"
        "code{white-space:normal;overflow-wrap:anywhere}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));"
        "gap:12px;margin:18px 0}.card{padding:16px}.card span{display:block;color:var(--muted);font-size:.82rem;"
        "text-transform:uppercase;font-weight:700}.card strong{display:block;margin-top:8px;font-size:1.5rem}.panel{padding:20px;"
        "margin:18px 0}li{margin:8px 0}table{width:100%;border-collapse:collapse;table-layout:fixed}th,td{padding:10px;"
        "border-top:1px solid var(--border);text-align:left;overflow-wrap:anywhere}th{width:34%;color:var(--muted)}"
        "@media(max-width:700px){main{width:calc(100vw - 18px);margin:12px auto}.hero,.panel{padding:16px}.cards{grid-template-columns:1fr}}"
    )
