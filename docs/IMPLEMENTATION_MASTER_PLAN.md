# Master Implementation Plan — V0 to V8

This document is the build contract for the thesis implementation. Do not add optional features until V8 is stable.

## Fixed research scope

- Python only
- PyPI only
- Input: Python snippets, `.py` files, and small multi-file projects
- Static analysis only
- Ordinary `import` and `from ... import ...`
- Main interface: CLI
- Output: JSON, CSV, readable text
- Two LLMs and approximately 100 prompts, producing approximately 200 outputs
- Primary comparison: B0 vs B1 vs B2 vs PROPOSED

## V0 — Setup

**Code:** repository, `src/`, `data/`, `tests/`, `results/`, `docs/`.

**Data:** mapping file, prompt schema, ground-truth schema, cache directory.

**Exit test:** `pytest -q` passes and CLI accepts a sample file/snippet.

## V1 — Import extraction

**Code:** `src/import_extractor.py`.

Extract `Import` and `ImportFrom` AST nodes, top-level import names, full imported module names, aliases, line/column, and relative level.

**Tests:** ordinary import, aliases, multiple imports, from-import, relative import, syntax failure.

## V2 — Source filters

**Code:** `src/stdlib_checker.py`, relative-import branch in classifier, parse-error handling.

Use the running Python version's `sys.stdlib_module_names` and identify relative imports before registry checking.

**Exit test:** `os`/`json` become `STANDARD_LIBRARY`; relative imports become `RELATIVE_IMPORT`; invalid source becomes `PARSE_ERROR`.

## V3 — Naïve baseline B0

**Code:** `src/pypi_client.py`, B0 branch in `src/classifier.py`.

Normalize the import name and query PyPI directly. Cache successful and 404 responses. Distinguish 404 from network failure.

**Exit test:** B0 produces deterministic `EXACT_PYPI_MATCH` for an existing exact candidate, `NOT_FOUND` for a missing candidate, and `NETWORK_ERROR` on registry failure.

## V4 — Curated mapping B2

**Code:** `data/import_distribution_mappings.json`, B2 branch.

Use only documented, evidence-backed aliases. The initial examples are the roadmap's PIL/Pillow, cv2/opencv-python, sklearn/scikit-learn, bs4/beautifulsoup4, and yaml/PyYAML cases.

**Exit test:** mapped names can resolve to their recorded PyPI distributions and the report includes the mapping reference.

## V5 — Local context

**Code:** `src/local_resolver.py`, proposed-method branch.

Check project-local `.py` files, package directories, and namespace-like directories before registry verification.

**Exit test:** imports satisfied by project files/directories become `LOCAL_MODULE` and are not sent to PyPI.

## V6 — Evidence and ambiguity

**Code:** `src/candidate_resolver.py`, evidence handling in `src/classifier.py`.

Candidate sources: exact normalized name, curated mapping, installed package metadata. Verify candidates on PyPI. Retain evidence, timestamps, candidate list, and confidence. Explicit ambiguity handling is a PROPOSED-method capability: if multiple equally strong candidates remain, PROPOSED returns `AMBIGUOUS`. B2 is the basic mapping baseline and deterministically selects the first candidate among equally strong verified candidates, so the comparison isolates the addition of ambiguity handling. That B2 behavior is a known limitation of the baseline, not a claim of ideal resolver behavior.

**Exit test:** PROPOSED can return `AMBIGUOUS`, preserve reasons, and never equate PyPI presence with package safety; B2 does not claim the explicit ambiguity policy.

## V7 — CLI and reports

**Code:** `src/cli.py`, `src/report_generator.py`.

One command analyses a snippet, file, or small project and produces JSON/CSV/text outputs.

**Exit test:** a clean environment can reproduce the same report structure from fixed input and cached registry data.

## V8 — Evaluation pipeline

**Code:** `src/evaluation.py`, `src/evaluation_cli.py`.

Run B0, B1, B2, and PROPOSED against the same frozen labelled import occurrences. Produce confusion counts, precision, recall, F1, false-positive rate, false-alert reduction, coverage, ambiguity rate, total/average warm-cache runtime, and error tables. The evaluator also produces category-wise full-classification correctness and case-level transitions between adjacent methods, so improvements and regressions can be traced to individual occurrences.

**Exit test:** one command recreates evaluation output from the frozen dataset, mapping file, and ground truth.

## Research-data workflow after the software core

1. Freeze the exact two LLMs and prompt set.
2. Generate all prompt outputs and preserve raw responses.
3. Extract code without silently changing the raw response.
4. Deduplicate according to a written rule.
5. Label every import occurrence using the ground-truth protocol.
6. Re-check at least 20% with a second reviewer where possible.
7. Freeze the dataset and ground truth.
8. Run V8 without changing labels after seeing results.
9. Investigate errors by the thesis taxonomy.
10. Write the results and limitations honestly.

## Explicit non-goals

Do not add OSV, GitHub Actions, web UI, third LLM, complete requirements/lockfile analysis, automatic installation/remediation, package execution, malicious-behaviour detection, dynamic plugin resolution, transitive dependency resolution, or another programming-language ecosystem before the core evaluation is complete.
