# Dossier Schema

`linkedin_profile_dossier` returns deterministic JSON built from raw visible
profile extraction data. It does not call an LLM and does not infer missing
facts.

Top-level fields:

- `person`: object, usually includes `name` when visible.
- `headline`: string or null.
- `location`: string or null.
- `about`: string or null.
- `experience`: list of objects.
- `education`: list of objects.
- `skills`: list of objects.
- `certifications`: list of objects.
- `projects`: list of objects.
- `languages`: list of objects.
- `contact_info`: object or null.
- `posts`: list of objects, only requested when `include_posts=true`.
- `evidence`: list of section-backed snippets.
- `gaps`: missing fields or sections.
- `warnings`: extraction limitations or partial errors.
- `confidence`: per-area numeric confidence from `0.0` to `0.8`.
- `source_url`: profile URL used for extraction.
- `extracted_at`: timestamp from the raw extraction.

## Evidence

Each evidence entry references the field, source section, and a compact raw
snippet:

```json
{
  "field": "headline",
  "section": "top_card",
  "snippet": "Jane Doe Principal Engineer New York"
}
```

## Gaps

If a field is missing, it is added to `gaps`. Missing fields are not guessed.

Example:

```json
{
  "contact_info": null,
  "gaps": ["contact_info"]
}
```

## Confidence

Confidence is deterministic and conservative:

- `0.8` for present scalar/object data.
- `0.75` for present list data.
- `0.0` for missing data.

These values are extraction confidence hints, not truth guarantees.

