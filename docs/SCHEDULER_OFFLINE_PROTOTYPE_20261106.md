# Scheduler state gate (offline prototype, 2026-11-06)

This isolated module is **not** a live scheduler and never performs HTTP calls, predictions, GitHub Actions scheduling, database writes, or automatic promotion. It implements a fail-closed state transition gate and deterministic replay only. No real JRA race results or model gains are asserted.

Run from repository root: `python -m unittest discover -s tests -p 'test_scheduler_core.py' -v`.

Design references: `docs/OPERATIONS_SCHEDULE_EVENT_TRIGGERS_20261105.md`, `docs/WINNING_CONDITION_DISCOVERY_ENGINE_DESIGN_20261105.md`. All evidence booleans are mockable gate tokens, **not proof that a JRA source was actually checked**. The collector must later supply independently validated receipts. Next: event discovery, durable job journal, cancellation logic, source-terms approval, full-race runner-ID collection, timestamped data, integration tests.

Safety boundaries: diagnostic branch only. No change to main/app.py or Turso. No auto-triggered workflows or cron. No scraping.
