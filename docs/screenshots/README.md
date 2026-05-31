# Screenshots

This folder stores public-safe screenshots used by the GitHub README and portfolio site.

Current captures:

- `market-summary.png`: desktop report view from the fixture-backed second demo run.
- `market-summary-mobile.png`: narrow responsive report view for the same generated HTML report.

Refresh flow:

```bash
jobintel run --config config/verification/companies.fixtures.run1.yaml --run-id portfolio-demo-1
jobintel run --config config/verification/companies.fixtures.run2.yaml --run-id portfolio-demo-2
jobintel history --config config/verification/companies.fixtures.run2.yaml --run-id portfolio-history --limit 10
```

Capture only synthetic fixture output. Do not commit live company data, ignored `reports/`, ignored DuckDB files, or local machine paths.
