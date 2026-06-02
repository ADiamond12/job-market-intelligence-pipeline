# Job Market Intelligence Pipeline Demo Storyboard

Use this storyboard for a short walkthrough of the reporting proof. The demo uses committed fixtures rather than live company data so results remain reproducible.

## 90-Second Reviewer Flow

1. Run `powershell -ExecutionPolicy Bypass -File .\scripts\run_demo.ps1`.
2. Open the first HTML report printed by the script.
3. Show source totals, validation results, and normalized role data.
4. Open the second run report and point out new/removed/changed role evidence.
5. Open the history report to show DuckDB-backed run comparison.
6. Close with the useful workflow: ATS fixtures -> validation -> history -> report artifact.

## Screenshots To Capture

- `docs/screenshots/market-summary-desktop.png`: report landing with metrics and role table visible.
- `docs/screenshots/market-summary-mobile.png`: same report on a narrow viewport.

## What To Say

This is a data-engineering project, not a generic scraper. The value is the repeatable pipeline: source adapters, validation, manifests, historical storage, delta reporting, and reviewer-friendly HTML outputs.
