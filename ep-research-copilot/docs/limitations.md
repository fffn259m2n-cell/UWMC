# Limitations

- **Abstract-only.** Extraction never reads full text. Abstracts omit details, may report
  subgroups, and can differ from the paper. Every value needs checking against the article.
- **Rules, not understanding.** Keyword screening misses unusual wording and can flag
  irrelevant mentions (e.g. "stroke" as an outcome is labelled "procedural safety").
  Records are never discarded, so the cost is review time, not lost articles.
- **Query coverage.** Articles not matching the PubMed query are never seen. Check recall
  with an occasional manual search (see validation.md).
- **No appraisal.** Design labels are descriptive. The tool does not assess bias, quality,
  certainty of evidence or clinical significance, and does not compare studies.
- **Registry data.** ClinicalTrials.gov entries are sponsor-maintained and may be outdated.
  A status change is an administrative fact, not a result. The search follows four active
  statuses; trials that leave them are re-read individually.
- **Unmeasured accuracy.** Precision, recall and extraction accuracy are unknown until a
  person completes the review in validation.md.
- **Copyright.** Abstracts and registry text belong to their owners. Do not republish the
  CSV outputs wholesale; share the digest internally and cite the linked sources.
