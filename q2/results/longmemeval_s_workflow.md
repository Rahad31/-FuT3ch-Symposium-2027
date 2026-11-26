# Q2 workflow run on LongMemEval_S

**Purpose:** learn the end-to-end workflow on a small dataset (agreed with Kirill). LongMemEval_S is too small to load the disk, so **no storage measurements were made here**. This run only checks that BM25, dense retrieval, the hybrid and the cascade work, and how the cascade behaves.

Code: [`../code/cascade_s.py`](../code/cascade_s.py). Raw per-question results: [`results_s.json`](results_s.json).

## Setup

| Part | Choice |
|---|---|
| Data | `longmemeval_s_cleaned.json`: 500 questions, ~50 sessions each |
| Store | One shared store with duplicate sessions removed: **18,464 unique sessions** |
| Retrieval unit | Session (all turns joined), top-5, as in AgentIR |
| BM25 | `bm25s`, k1 = 1.2, b = 0.75, English stopwords, one index per question history |
| Dense | BGE-small-en-v1.5 (ONNX, CLS pooling, 512-token truncation, query instruction prefix) + HNSW (`hnswlib`, M = 16, ef = 200) over the shared store, filtered to the question's own sessions |
| Hybrid | RRF, k = 60 |
| Cascade | Skip dense if (s1 − s2) / s1 ≥ 0.10 on BM25 scores (AgentIR rule) |
| Metric | Retrieval against the gold evidence sessions: **Hit@5** (any evidence session in the top 5) and **Recall-all@5** (all evidence sessions in the top 5) |
| Machine | Cloud VM, 2 CPU cores, 7 GB RAM, CPU only |

## Results

| | BM25 | Dense | Hybrid | Cascade |
|---|---|---|---|---|
| Hit@5 | 0.966 | 0.920 | 0.972 | **0.972** |
| Recall-all@5 | 0.816 | 0.796 | 0.858 | **0.840** |

- **Skip share: 76.4%** of questions skip dense retrieval (AgentIR reports 63%).
- **Cascade vs hybrid, Hit@5:** +0.000, 95% paired-bootstrap interval [−0.012, +0.012].
- **Cascade vs hybrid, Recall-all@5:** −0.018, interval [−0.040, +0.002].
- Median BM25 confidence: 0.22 (AgentIR: 0.16).

By question type:

| Type | n | Skip | Hit@5 hybrid / cascade | Recall-all@5 hybrid / cascade |
|---|---|---|---|---|
| knowledge-update | 78 | 0.69 | 1.000 / 1.000 | 0.974 / 0.962 |
| multi-session | 133 | 0.68 | 0.985 / 0.977 | 0.752 / 0.699 |
| single-session-assistant | 56 | 1.00 | 1.000 / 1.000 | 1.000 / 1.000 |
| single-session-preference | 30 | 0.67 | 0.867 / 0.867 | 0.867 / 0.867 |
| single-session-user | 70 | 0.96 | 0.971 / 0.986 | 0.971 / 0.986 |
| temporal-reasoning | 133 | 0.71 | 0.955 / 0.955 | 0.774 / 0.759 |

Median time per query: BM25 25.7 ms, query encoding 11.7 ms, HNSW search 12.4 ms. Embedding all 18,464 sessions took 54 minutes.

## What this tells us

1. **The pipeline works end to end** and reproduces AgentIR's main finding: the cascade skips most dense queries and matches the hybrid on Hit@5.
2. **The skip share is higher than AgentIR's (76% vs 63%).** The likely cause is a different BM25 implementation: AgentIR uses its own engine and Lucene, while this run uses `bm25s` with stopword removal. Removing stopwords spreads the scores, so confidence goes up (median 0.22 vs 0.16). For the disk experiments I will switch to Lucene (Pyserini) and report the skip share I measure, since Q2's predictions depend on it.
3. **Skipping has a small cost on multi-evidence questions.** Recall-all@5 drops by 0.018 overall and by 0.053 on multi-session questions. That's where BM25 finds one evidence session confidently but misses the others. Hit@5 does not show it.
4. **The index is tiny:** 18,464 × 384 floats ≈ 28 MB of vectors. It fits in RAM easily, which confirms Kirill's point that S cannot load the disk. The 12 ms HNSW time comes from the Python filter callback, not from storage.

## Limits

- **Retrieval metrics only.** AgentIR reports LLM-judged answer accuracy (gpt-4o-mini). This run has no LLM, so Hit@5 and Recall-all@5 stand in for accuracy.
- The tokenizer was rebuilt from the BERT-uncased WordPiece vocabulary and checked block by block against BGE's `tokenizer.json` (all 30,522 tokens match).
- Timings are from a 2-core VM and are not storage results.

## Next

1. Switch BM25 to Lucene (Pyserini) and re-measure the skip share.
2. Ask Kirill to confirm LongMemEval_M for the disk experiments.
3. Build the round-level store on M, measure W and W_r with unlimited RAM, then start the RAM sweep with physical-read counting.
