# Q2: datasets and approach (for approval)

**Status:** proposal. No experiments run yet. I start only after the mentor agrees.

## Question

When the dense index does not fit in RAM, how many physical disk reads does skipping dense retrieval save? And what does each retriever (BM25 and dense) cost on disk?

## Datasets

### 1. LongMemEval_S, to reproduce AgentIR

- 500 questions. Each question has its own chat history of about 50 sessions (about 115k tokens).
- This is the setup the AgentIR paper uses: top-5 sessions per question, with the cascade skipping dense for 63% of questions.
- **Purpose:** check that my BM25, dense retrieval and cascade give the same skip share and accuracy as the paper before I measure any disk reads.
- **Limit:** the index is small (500 × about 50 sessions, and sessions repeat across questions). It is too small to stress storage, so it is not used for the disk experiments.

### 2. LongMemEval_M, the main dataset for disk experiments

- The same 500 questions, but each question has about 500 sessions (about 1.5M tokens).
- I put all histories into **one shared store**, removing duplicate sessions. Each question searches only its own history through a filter, like many agents sharing one memory service.
- I index at the **round (turn) level**, which gives far more vectors than session level, so the index is large enough to matter on disk.
- RAM is limited with cgroups, so the index does not have to be bigger than the machine's RAM. I can place the RAM limit below W_r, between W_r and W, and above W.
- **Purpose:** all physical-read measurements and the RAM sweep.

### 3. LoCoMo, as a control only (optional)

- On LoCoMo the cascade skips 100% of dense queries, so the saving is simply all dense reads.
- **Purpose:** a sanity check for the read counting, not a result.

## Retrievers and models

- **BM25:** Lucene through Pyserini, the baseline AgentIR uses. Its index is disk-based, so its reads can be counted.
- **Dense:** BGE-small-en-v1.5 (384-dim, same as AgentIR) with an HNSW index stored on disk and memory-mapped.
- **Cascade rule:** same as AgentIR. Skip dense when (top1 − top2) / top1 ≥ 0.10 on BM25 scores.
- **Arms:** always-hybrid (BM25 + dense, fused with RRF) against the cascade. The question-type router (24% skip) is a possible second check.
- Both indexes sit on the same local NVMe, in separate files, so reads can be split per retriever.
- **Accuracy:** same answer model and same judge in both arms, compared with a paired bootstrap against an allowed drop fixed in advance.

## Order of work (after approval)

1. Reproduce AgentIR on LongMemEval_S: skip share and accuracy.
2. Build the LongMemEval_M store on NVMe.
3. With unlimited RAM, measure W, W_r and the skipped share.
4. Build the dense read curve: reads per query against W/R.
5. Run the RAM sweep and count physical reads, always-hybrid against the cascade.
6. Compare the measured saving with the simple prediction and the read-curve prediction.

## Open questions for the mentor

1. Is LongMemEval_M, pooled into one store with a per-question filter, acceptable as the main dataset?
2. Round-level or session-level indexing for the disk experiments?
3. Is DAMON or page_idle acceptable for counting W including cache hits?
