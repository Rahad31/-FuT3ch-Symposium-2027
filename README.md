# Project 2: Agent memory at scale, problem statements

Team: Syed, Rahad.

## Shared question

When does storage start to cost an agent-memory step time, and which retrieval choices change that?

**Not new, do not claim:**
- SSD-resident vector indexes such as DiskANN and SPANN, and their latency on local SSD;
- that the on-disk layout of an agent-memory store changes its retrieval latency on local NVMe [1];
- that the query distribution changes the buffer hit ratio of a vector index at a fixed buffer size [2];
- a phase breakdown of memory systems inside an agent step, without storage [3];
- routing queries inside one out-of-core vector index to cut SSD accesses [4];
- skipping dense retrieval when BM25 is confident, on LongMemEval [6] and LoCoMo [7], at equal accuracy and measured in CPU time [5].

**Open, no source found:**
- Q1: the storage time of an agent-memory step as RAM, the active working set and the number of active agents vary, on local NVMe and on network storage;
- Q2: the storage reads saved by skipping dense retrieval, with BM25 and graph-based dense retrieval measured on disk on the same testbed.

**Not in this project:** write-heavy workloads as a variable, comparisons of vector stores or of faster LLMs, and new routing or fusion methods judged by accuracy alone.

**What counts as a result:** a prediction from a model fitted on configuration A, checked on configuration B. Each question names its A and B. A failed prediction also counts if the measurements explain the failure.

## Shared testbed

- One memory system and one vector store with pinned versions, and a fixed LLM and embedding model. Q2 may run its retrievers outside the memory system, but on the same data and the same device.
- Sweeps run retrieval against a frozen store. Memory writes are not part of them.
- Three quantities are kept apart:
  - cache misses in the store;
  - physical reads at the device;
  - the I/O wait on the critical path of a step.

  A miss in the store's own buffer may be served by another cache level, and several physical reads may run in parallel. So none of these quantities stands in for another.
- Q1 and Q2 count physical reads: the reads that reach the device while the store serves the retrieval requests of one step, or of one query.
- Storage time per step is the measured I/O wait on the critical path of the step. Physical reads times the cost of one read, measured separately at the same request size and I/O concurrency, only predicts that wait, and the prediction is checked against the measurement.
- The RAM available to the store is varied without changing the data.
- Each condition starts with an empty page cache and is measured in steady state after warm-up.
- The LLM stage is the time of all LLM calls in a step, measured on the same testbed.
- Retrievers are compared at the same store size, and accuracy is judged the same way in every arm.
- An arm counts as no worse than another only if the paired confidence interval of the difference stays above an allowed drop fixed in advance. The absence of a significant difference is not enough.
- Local NVMe is required. Network storage (block or a parallel file system) is used only if access is granted, so each question must give a result without it.

## Q1: when storage enters the step

**Question:** at what point does storage time per step reach a set share of the LLM stage, and what sets that point? Is it the total index size relative to RAM, or the part of the index that the active agents actually touch?

**Known:**
- In pgvector on the C4 5M dataset, with a PostgreSQL buffer of 10% of the dataset size, the buffer hit ratio is below 20% with random queries and above 80% with MMLU queries [2]. At a fixed buffer, the queries decide the hit ratio. These are hits in the PostgreSQL buffer, not physical reads.
- With Qwen3-30B, the answer stage alone takes from 0.196 s to 6.232 s across memory systems (Table 3 of the first arXiv version of [8]). The share of storage depends on the system as much as on the storage.
- The working set, the pages a program touches within a time window, is a classic concept of memory management [9]. No agent-memory or vector-search paper uses the working set relative to RAM as an axis.

**Hypothesis:** physical reads per step depend only on the ratio W/R.
- W is the active working set: the bytes of distinct index and data pages that the store touches while serving the agents active in a time window. It counts all page accesses, cache hits included, and is measured in a run with unlimited RAM, because layout and filtering decide which pages a query touches [1].
- R is all the memory that can cache the store's pages, its own buffer and the page cache together, after the store's resident memory.

At equal W/R, physical reads per step are the same whether the store holds the memories of few stored agents or of many, with the active agents held fixed. Fitted on one store size, the curve of physical reads per step against W/R predicts physical reads per step on a larger store, within a tolerance fixed in advance.

[9] gives the concept of the working set. [2] shows, at one dataset size, that the queries alone change the buffer hit ratio. That physical reads depend only on W/R, so that the store size drops out, is this project's hypothesis.

With network storage, the physical reads per step from the local curve, times the cost of one read measured separately on network storage, predict the I/O wait there. They also predict the W/R at which storage time reaches the set share of the LLM stage. Both predictions are checked against the measured I/O wait.

**Refuted if:**
- at equal W/R, physical reads per step differ between the two store sizes by more than the tolerance;
- changing W at fixed R and store size leaves physical reads per step unchanged within the run-to-run spread;
- with network storage, physical reads per step there differ from the local curve, or the measured I/O wait misses the prediction by more than the tolerance. The two parts are checked separately.

**Experiment:**
1. Vary R, W and the store size independently:
   - W through the number of active agents and, at a fixed number of agents, through which memories the queries target;
   - R through the RAM limit of the store;
   - the store size through the number of stored agents.
2. Measure the cost of one read at each request size and I/O concurrency the sweeps produce. This keeps the queueing caused by more active agents out of the read curve.
3. With network storage access, repeat the sweep there.

**Result:**
- physical reads per step against W/R;
- the measured I/O wait per step on each tier, beside its prediction from reads times the cost of one read;
- the prediction against the measurement on the larger store and, if available, on network storage;
- the W/R at which the measured I/O wait reaches a share of the LLM stage, with the share fixed in advance.

**Provides:** the step harness for Q2: RAM control, page-access counting with unlimited RAM, and physical reads and I/O wait per step.

## Q2: the reads saved by skipping dense retrieval

**Question:** when the dense index does not fit in RAM, how many physical reads does skipping dense retrieval for some queries save, and what does each retriever cost on disk?

**Known:**
- On LongMemEval, an oracle that knows the question type beats the best fixed configuration by 0.012 in LLM-judged accuracy, under each of two judges [5]. Choosing a retriever per question has little room to gain accuracy.
- A cascade that runs dense retrieval only when BM25 is not confident skips 63% of dense queries on LongMemEval [5]. Its accuracy equals that of always-hybrid (both retrievers on every query, results fused) within a paired-bootstrap interval of -0.016 to +0.016. The 19.9 ms against 53.2 ms per query is a mean computed from the latencies of the two paths and the skipped share, so it is proportional to the skipped share by construction. Physical reads from SSD were not measured.
- The skipped share depends on the router and the workload [5]. For the cascade it is 100% on LoCoMo, which leaves no dense reads to save. A question-type classifier skips 24.2% on LongMemEval.

**Hypothesis:** the saving is the physical reads with always-hybrid minus those with the cascade, counting every read in both arms, BM25 included. The simple prediction of the saving is the dense reads of always-hybrid times the skipped share.

On disk, the saving is not always the simple prediction, because skipping shrinks the working set as well as the number of dense queries. All dense queries together touch a working set W. The ones that remain after skipping touch a smaller working set W_r. This gives three cases:
- R below W_r: neither fits in RAM, and the saving is close to the simple prediction.
- R between W_r and W: the remaining queries fit in RAM where all of them did not, so the saving exceeds the simple prediction.
- R above W: everything fits already, and there is nothing to save.

The size of the saving is predicted from the read curve of the dense index, evaluated at W_r/R. The read curve gives physical reads per query against the working set over R. This follows from Q1's hypothesis applied to the dense index. No source has measured it.

Here A is a calibration subset of questions, and B is the remaining questions of the same benchmark on the same store.

**Refuted if:**
- where R lies between W_r and W, the measured saving is within a tolerance fixed in advance of the simple prediction;
- the measured saving matches neither the simple prediction nor the prediction from the read curve.

**Experiment:**
1. On the calibration subset, measure W and W_r with unlimited RAM. Also measure the skipped share and the read curve of the dense index, which is the store's graph index.
2. Count all physical reads in each arm, BM25 included, and report the reads per query of each retriever.
3. Fix the allowed accuracy drop in advance. Check it with a paired confidence interval of the difference between the cascade and always-hybrid, as set out in the shared testbed. A saving that costs more than the allowed drop is not a result.
4. Choose values of R on both sides of W_r and of W.

**Result:**
- the saving in physical reads across R, measured, beside both predictions;
- reads per query for BM25 and for the graph-based dense index on the same testbed;
- the accuracy difference against always-hybrid, with its paired confidence interval and the allowed drop.

**Depends on:** Q1's harness, but not on Q1's hypothesis: the dense read curve comes from Q2's own calibration runs.

## References

1. Yang Liu, Zhaokai Luo, Huayi Jin, Ruozhou He, Chenchen Hong, Zhiyong Wang, Yifei Liu, Yunfei Gu, Chentao Wu, Junhao Hu. *Akashic: A Low-Overhead LLM Inference Service with MemAttention.* arXiv preprint, 2026. https://arxiv.org/abs/2607.05708
2. Joobo Shim, Jaewon Oh, Hongchan Roh, Jaeyoung Do, Sang-Won Lee. *Turbocharging Vector Databases using Modern SSDs.* PVLDB 18(11): 4710-4722, 2025. https://www.vldb.org/pvldb/vol18/p4710-do.pdf
3. Yasmine Omri, Ziyu Gan, Zachary Broveak, Robin Geens, Zexue He, Alex Pentland, Marian Verhelst, Tsachy Weissman, Thierry Tambe. *Agent Memory: Characterization and System Implications of Stateful Long-Horizon Workloads.* IISWC 2026. https://arxiv.org/abs/2606.06448
4. Lizheng Chen, Pinhuan Wang, Shaonan Ma, Jie Zhang, Qing Wang, Zhengyi Yang, Heng Zhang, Mingxing Zhang, Fan Yang, Guihai Chen, Chen Tian, Chengying Huan. *Beyond Overlap: Hierarchical Graph Abstraction for Out-of-Core Vector Search.* EuroSys 2027 (accepted). https://arxiv.org/abs/2512.22838
5. Aojie Yuan, Haiyue Zhang, Shahin Nazarian. *AgentIR: A Workload-Adaptive Cascade Retrieval Substrate for Long-Term Conversational Memory.* arXiv preprint, 2026. https://arxiv.org/abs/2605.25092
6. Di Wu, Hongwei Wang, Wenhao Yu, Yuwei Zhang, Kai-Wei Chang, Dong Yu. *LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory.* ICLR 2025. https://arxiv.org/abs/2410.10813
7. Adyasha Maharana, Dong-Ho Lee, Sergey Tulyakov, Mohit Bansal, Francesco Barbieri, Yuwei Fang. *Evaluating Very Long-Term Conversational Memory of LLM Agents.* ACL 2024. https://arxiv.org/abs/2402.17753
8. Han Chen, Zining Zhang, Wenqi Pei, Bingsheng He, Ming Wu, Jason Zeng, Michael Heinrich, Wei Wu, Hongbao Zhang. *MemForest: An Efficient Agent Memory System with Hierarchical Temporal Indexing.* arXiv preprint, 2026. https://arxiv.org/abs/2605.23986
9. Peter J. Denning. *The Working Set Model for Program Behavior.* Communications of the ACM 11(5): 323-333, 1968. https://doi.org/10.1145/363095.363141
