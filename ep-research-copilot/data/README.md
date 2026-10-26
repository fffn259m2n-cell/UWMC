# Data folder

Created by the tool; nothing here is committed except this file.

- `ep_copilot.sqlite`: the research database (articles, trial snapshots, screening,
  extraction, reviewer decisions). Back it up if you rely on month-to-month change tracking.
- `ep_copilot_fixtures.sqlite`: used by `--offline` runs (synthetic data only). The tool
  refuses to mix synthetic and real records in one database.
- Snapshot folders (`snapshot.json`): records captured another way, e.g. with
  `scripts/import_connector_export.py`, then processed with `ep-copilot run --snapshot DIR`.

Abstracts and registry text belong to their publishers and sponsors, so this folder is
git-ignored. Re-create it at any time with `ep-copilot run`.
