# Q2: Reads saved by skipping dense retrieval

**Owner:** Syed Ikramuddin
**Project:** Agent memory at scale (with Rahad, who owns Q1)
**Status:** design done. Waiting for mentor approval of datasets and approach before any experiment.

Datasets and approach for approval: [datasets-and-approach.md](datasets-and-approach.md). Discussion: issue #3.

---

## 1. The question

When the dense index does not fit in RAM, how many **physical disk reads** do we save by skipping dense retrieval for some queries? And what does each retriever (BM25 and dense) cost on disk?

## 2. Background

An agent's memory is searched in two ways:

- **BM25** (keyword search): cheap, with a small index.
- **Dense retrieval** (embeddings with a graph index such as HNSW): better on paraphrased questions, but heavier.

**AgentIR** [5] proposes a cascade. It runs BM25 first, measures how confident BM25 is, and runs dense only when BM25 is not confident.

- Confidence: `c(q) = (s1 - s2) / s1`, where s1 and s2 are the top two BM25 scores.
- Dense is skipped when `c(q) >= 0.10`.

What [5] reports:

| Workload | Dense skipped | Accuracy |
|---|---|---|
| LongMemEval (500 questions) | 63% | 0.302 vs 0.302 for always-hybrid, paired bootstrap interval [-0.016, +0.016] |
| LoCoMo (1,982 questions) | 100% | BM25 alone is the strongest system |
| LongMemEval, question-type router | 24.2% | |

## 3. Why this is still open

[5] never measured storage.

- Its dense cost of 53.2 ms is almost all **query encoding** (about 52 ms for BGE-small). The HNSW search itself is under a millisecond, because the index sits in RAM.
- Its 19.9 ms vs 53.2 ms speedup is **derived** from per-stage times, not measured in a full run. The paper says this in its limitations.
- No physical SSD reads were counted.

So nobody knows what the cascade saves once the dense index lives on disk.

## 4. The hypothesis

**Saving** = physical reads with always-hybrid minus physical reads with the cascade. Every read counts in both arms, BM25 included.

**Simple prediction:** saving = dense reads of always-hybrid × skipped share.

Skipping does two things at once, though. It removes dense queries, and it also **shrinks the working set**:

- **W**: distinct pages that all dense queries touch.
- **W_r**: distinct pages that only the remaining (non-skipped) dense queries touch.
- **R**: RAM available to cache the index pages.

This gives three regimes:

| RAM | What happens | Saving vs simple prediction |
|---|---|---|
| R > W | Everything fits already | Zero, nothing to save |
| W_r < R < W | All queries together do not fit, but the remaining ones do | **Larger** than the simple prediction |
| R < W_r | Even the remaining queries do not fit | About equal to the simple prediction |

**Example (made-up numbers, only to show the idea):** take 1,000 questions, where each dense search does 20 disk reads, for 20,000 reads in total. The cascade leaves 370 dense questions. The simple prediction is 370 × 20 = 7,400 reads left, a 63% saving. In the middle regime, though, those 370 questions' pages now fit in RAM, so maybe each does only 2 reads after warm-up: 740 reads left, a **96% saving**.

The size of the saving is predicted from the **dense read curve** (physical reads per query against working set / R), evaluated at W_r / R.

**Refuted if:** in the middle regime, the measured saving stays within a tolerance fixed in advance of the simple prediction, or it matches neither prediction.

## 5. Datasets

Full reasoning is in [datasets-and-approach.md](datasets-and-approach.md).

| Dataset | Role |
|---|---|
| **LongMemEval_S** (500 questions, ~50 sessions each) | Reproduce [5]: skip share and accuracy. Too small to stress storage. |
| **LongMemEval_M** (500 questions, ~500 sessions each) | Main dataset. All histories pooled in one store, duplicates removed, per-question filter, round-level indexing. |
| **LoCoMo** (optional) | Control only. The cascade skips 100%, so it checks the read counting. |

## 6. Testbed

- **Device:** local NVMe. Network storage only if access is granted, and the result must stand without it.
- **BM25:** Lucene through Pyserini, on disk.
- **Dense:** BGE-small-en-v1.5 (384-dim) with HNSW stored on disk and memory-mapped.
- **Same data, same device** for both retrievers. Separate index files, so reads can be split per retriever.
- **Frozen store:** no writes during the sweeps.
- **RAM control:** cgroup `memory.max` on the retrieval process. Page cache counts against the limit.
- **Clean start:** every condition starts with an empty page cache, then warm-up, then measurement in steady state.
- **Harness:** RAM control and read counting are shared with Q1. Q2 uses Q1's harness but not Q1's hypothesis, and builds its own dense read curve from its own calibration runs.

## 7. What is measured

Three quantities are kept apart, and none stands in for another:

1. **Cache misses** in the store's own buffer.
2. **Physical reads** at the device: block-layer tracing (eBPF / blktrace), filtered by file to split BM25 and dense.
3. **I/O wait** on the critical path of a query.

Also measured:

- **W and W_r** with unlimited RAM, counting every page touched, cache hits included. Candidate methods: DAMON or idle page tracking (`/sys/kernel/mm/page_idle`).
- **Skipped share** of the cascade on the same data.
- **Accuracy** in each arm, with the same answer model and the same judge.

## 8. Experiment plan

1. **Reproduce [5]** on LongMemEval_S: skip share near 63%, accuracy within the paper's interval.
2. **Build the LongMemEval_M store** on NVMe: BM25 and HNSW indexes.
3. **Unlimited-RAM run:** measure W, W_r, the skipped share, and the pages touched per query.
4. **Dense read curve:** vary R and measure physical reads per dense query against W/R.
5. **Main sweep:** pick R values below W_r, between W_r and W, and above W. Run always-hybrid and the cascade, counting all physical reads.
6. **Compare:** measured saving against the simple prediction and the read-curve prediction.
7. **Second router (check on B):** fit on the cascade, then predict the saving of the question-type router (24% skip) and check it.
8. **Accuracy:** paired bootstrap; the cascade counts as no worse only if the interval stays above an allowed drop fixed in advance.

## 9. Expected outputs

- Measured saving against R, with both predictions on the same plot.
- Physical reads per query for BM25 and for the dense index.
- Accuracy difference with its interval and the allowed drop.
- A short explanation if a prediction fails.

## 10. Not claimed (already known)

- SSD-resident vector indexes such as DiskANN and SPANN.
- That on-disk layout changes retrieval latency on NVMe.
- That the query distribution changes buffer hit ratio at a fixed buffer size ([2]: below 20% with random queries, above 80% with MMLU queries in pgvector).
- Skipping dense retrieval at equal accuracy, measured in CPU time ([5]).

## 11. Risks

| Risk | Fallback |
|---|---|
| W cannot be measured cleanly (cache hits are invisible to block tracing) | Use DAMON or page_idle, or a store that reports its own buffer hits |
| BM25 and dense compete for the same page cache | Decide in advance: one shared limit or separate cgroups, and report which |
| No root or NVMe on the cluster | Start on a local machine with NVMe |
| The middle regime is too narrow to see | Use a finer R grid around W_r and W |
| Cascade skip share differs from [5] | Report it and use the measured share in the predictions |

## 12. Open questions for the mentor

1. Is LongMemEval_M, pooled with a per-question filter, acceptable as the main dataset?
2. Round-level or session-level indexing?
3. Is DAMON / page_idle acceptable for measuring W?
4. Should R be one shared limit or separate limits per retriever?
5. What tolerance and allowed accuracy drop should be fixed in advance?

## References

- [2] Shim et al., *Turbocharging Vector Databases using Modern SSDs*, PVLDB 2025.
- [5] Yuan et al., *AgentIR: A Workload-Adaptive Cascade Retrieval Substrate for Long-Term Conversational Memory*, arXiv:2605.25092.
- Wu et al., *LongMemEval*, ICLR 2025, arXiv:2410.10813.
- Maharana et al., *LoCoMo*, arXiv:2402.17753.
- Linux kernel docs, *DAMON* design.
