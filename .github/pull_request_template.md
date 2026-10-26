## What changed and why

## Checks
- [ ] `ruff check .` passes
- [ ] Tests pass for each project I touched (`pytest -q`)
- [ ] Teach-Back: `teachback check-content` and `teachback evaluate-set eval/dev_set.json` show no regression
- [ ] New rules or fixes have tests; no real patient data, credentials or third-party branding added
- [ ] Docs updated if behaviour or numbers changed (I did not tune on `eval/heldout_set.json`)
