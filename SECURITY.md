# Security Policy

## Scope

Job Market Intelligence Pipeline is currently a local-first CLI and batch workflow. It is designed for controlled runs, offline demos, and portfolio presentation, not as a public multi-tenant scraping platform.

## Security Expectations

- Do not commit API keys, `.env` files, logs, generated reports, or DuckDB history snapshots.
- Treat generated data under `data/`, `reports/`, and `artifacts/` as local run output unless it has been intentionally sanitized.
- Prefer fixture-backed runs for demos and reproducible verification.
- Keep optional AI enrichment explicitly bounded and non-authoritative.

## Reporting

Do not open public issues with secrets, live target details, or sensitive run artifacts. Use a private disclosure path through the hosting platform or contact the maintainer directly.

## Known Limits

- No auth or user management because the project is CLI-first
- No tenant isolation
- No hosted scheduling or orchestration layer
- Optional live ATS and OpenAI paths depend on external services and local credentials
