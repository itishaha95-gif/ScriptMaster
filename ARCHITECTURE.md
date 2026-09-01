# ScriptMaster Architecture

## Goal

The user experience is intentionally simple:

```text
Topic → Script
```

The backend handles style learning, generation, and evaluation.

## 1. Corpus layer

The corpus contains 100 scripts.

Preprocessing includes:
- script boundary detection
- transcript marker cleanup
- whitespace normalization
- sentence-aware chunking
- metadata generation

This produced 271 semantic chunks.

## 2. Deterministic style analysis

Python measures:
- word count
- sentence length
- question frequency
- first-person usage
- second-person usage
- recurring discourse markers
- recurring transitions

## 3. Semantic style analysis

Qwen3 through Ollama infers:
- hook type
- tone
- pacing
- rhetorical devices
- explanation style
- structural stages
- ending type

The aggregate profile is stored as:

```text
semantic_style_profile_local.json
```

## 4. Semantic retrieval

MiniLM converts transcript chunks into embeddings.

Model:

```text
sentence-transformers/all-MiniLM-L6-v2
```

The retrieval module can compare a new topic with the 271 chunks using vector similarity.

## 5. Why raw retrieval was removed from production generation

Testing revealed topic drift.

Example:

```text
Requested:
Are people less emotional due to use of AI?

Bad generated output:
Career uncertainty? Try a one-week experiment...
```

The retrieved source content had become more influential than the user topic.

The final generator therefore uses:

```text
User Topic + Compact Style Profile → Qwen3
```

instead of:

```text
User Topic + Raw Retrieved Transcripts → Qwen3
```

## 6. Topic-drift protection

The current generator includes:
1. explicit topic priority
2. compact style profile
3. stale-output deletion
4. output-topic verification
5. keyword coverage checking
6. one automatic retry on poor topic coverage

## 7. Evaluation

Deterministic checks:
- word count
- sentence count
- average sentence length
- question count
- pronoun usage
- long phrase overlap

Local Qwen evaluation:
- style match
- topic relevance
- originality
- script quality

## 8. UI

Streamlit provides the interface.

Generation and evaluation are separate buttons so users can see the script before waiting for a second local LLM call.

## 9. Deployment

Current deployment is fully local:

```text
Windows
├── Python
├── Ollama
├── Qwen3
├── MiniLM
└── Streamlit
```

No paid API is required for normal operation.
