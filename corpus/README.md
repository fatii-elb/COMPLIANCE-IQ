# Corpus

Regulatory knowledge base source files, loaded and ingested by the RAG pipeline
(see `docs/RAG.md`).

## Layout

- `frameworks/*.json` — one file per framework document. Each file matches the
  `CorpusDocument` shape: `framework`, `title`, `version`, `language`,
  `jurisdiction`, and a list of `controls` (`control_id`, `title`, `summary`,
  `keywords`, `references`).

## Copyright policy (non-negotiable rule 6)

- **Public sources** (Loi 05-20, DGSSI/DNSSI directives, NIST CSF) may be
  summarised freely; summaries here are original and reference the public text.
- **Copyrighted standards** (ISO/IEC 27001, SOC 2 Trust Services Criteria) are
  represented by **control identifiers + our own plain-language summaries +
  references only**. The verbatim normative text is **never** stored. Consult the
  licensed standard for the authoritative wording.

The domain model has no field for verbatim standard text, so the forbidden data
has nowhere to live — the policy is enforced by shape, not by convention.

## Adding a framework

1. Create `frameworks/<name>.json` following the shape above.
2. Ensure `framework` is one of the values in
   `complianceiq.domain.value_objects.enums.Framework` (add it there if new).
3. Re-ingest: `python -m scripts.ingest_corpus --replace`.
