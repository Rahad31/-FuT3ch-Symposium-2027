"""Q2 workflow run on LongMemEval_S: BM25, dense (BGE-small + HNSW), hybrid (RRF) and the
AgentIR confidence cascade. Retrieval only: measures skip share and evidence recall.

Usage:
  python cascade_s.py --data longmemeval_s_cleaned.json --model model.onnx \
      --tokenizer tokenizer.json --out results_s.json
"""
import argparse, json, time, hashlib, random
import numpy as np
import bm25s, hnswlib, onnxruntime as ort
from tokenizers import Tokenizer

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "  # BGE v1.5 query instruction
TOP_K = 5
TAU = 0.10        # AgentIR cascade threshold
RRF_K = 60        # AgentIR RRF constant


def session_text(turns):
    return "\n".join(f"{t['role']}: {t['content']}" for t in turns)


class BGE:
    def __init__(self, model_path, tok_path, max_len=512, threads=2):
        so = ort.SessionOptions(); so.intra_op_num_threads = threads
        self.sess = ort.InferenceSession(model_path, so, providers=["CPUExecutionProvider"])
        self.tok = Tokenizer.from_file(tok_path)
        self.tok.enable_truncation(max_len)
        self.tok.enable_padding()
        self.inputs = {i.name for i in self.sess.get_inputs()}

    def encode(self, texts, bs=16):
        out = []
        for i in range(0, len(texts), bs):
            enc = self.tok.encode_batch(texts[i:i + bs])
            ids = np.array([e.ids for e in enc], dtype=np.int64)
            mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self.inputs:
                feed["token_type_ids"] = np.zeros_like(ids)
            h = self.sess.run(None, feed)[0][:, 0]          # CLS pooling
            out.append(h / np.linalg.norm(h, axis=1, keepdims=True))
        return np.vstack(out).astype(np.float32)


def rrf(rank_lists, k=RRF_K):
    score = {}
    for ranks in rank_lists:
        for r, d in enumerate(ranks):
            score[d] = score.get(d, 0.0) + 1.0 / (k + r + 1)
    return [d for d, _ in sorted(score.items(), key=lambda x: -x[1])]


def hit(ranked, gold):      # any evidence session in top-k
    return float(bool(set(ranked[:TOP_K]) & gold))


def recall_all(ranked, gold):  # all evidence sessions in top-k
    return float(gold <= set(ranked[:TOP_K]))


def paired_bootstrap(a, b, n=10000, seed=0):
    a, b = np.asarray(a), np.asarray(b)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(a), (n, len(a)))
    d = a[idx].mean(1) - b[idx].mean(1)
    return float((a - b).mean()), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data"); ap.add_argument("--model"); ap.add_argument("--tokenizer")
    ap.add_argument("--out", default="results_s.json"); ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    data = json.load(open(a.data))
    if a.limit:
        data = data[:a.limit]

    # one shared store: unique sessions (dedup by content hash, as sessions repeat across questions)
    key2idx, texts = {}, []
    q_docs = []
    for q in data:
        docs = []
        for sid, turns in zip(q["haystack_session_ids"], q["haystack_sessions"]):
            t = session_text(turns)
            h = hashlib.sha1(t.encode()).hexdigest()
            if h not in key2idx:
                key2idx[h] = len(texts); texts.append(t)
            docs.append((sid, key2idx[h]))
        q_docs.append(docs)
    print(f"questions={len(data)} unique_sessions={len(texts)}", flush=True)

    model = BGE(a.model, a.tokenizer)
    t0 = time.time()
    doc_emb = model.encode(texts)
    embed_docs_s = time.time() - t0
    print(f"embedded {len(texts)} sessions in {embed_docs_s:.0f}s", flush=True)

    index = hnswlib.Index(space="ip", dim=doc_emb.shape[1])
    index.init_index(max_elements=len(texts), ef_construction=200, M=16)
    index.add_items(doc_emb, np.arange(len(texts)))
    index.set_ef(200)

    rows = []
    for q, docs in zip(data, q_docs):
        gold = set(q.get("answer_session_ids") or [])
        sids = [s for s, _ in docs]
        idx2sid = {}
        for s, i in docs:
            idx2sid.setdefault(i, s)

        # BM25 over this question's own history (per-question index, like AgentIR)
        t = time.perf_counter()
        corpus = [texts[i] for _, i in docs]
        retr = bm25s.BM25(k1=1.2, b=0.75)
        retr.index(bm25s.tokenize(corpus, stopwords="en", show_progress=False), show_progress=False)
        res, sc = retr.retrieve(bm25s.tokenize([q["question"]], stopwords="en", show_progress=False),
                                k=len(corpus), show_progress=False)
        bm25_rank = [sids[j] for j in res[0]]
        s1, s2 = float(sc[0][0]), float(sc[0][1]) if len(corpus) > 1 else 0.0
        conf = (s1 - s2) / s1 if s1 > 0 else 0.0
        bm25_ms = (time.perf_counter() - t) * 1e3

        # dense over the shared HNSW store, filtered to this question's sessions
        t = time.perf_counter()
        qv = model.encode([QUERY_PREFIX + q["question"]])
        enc_ms = (time.perf_counter() - t) * 1e3
        allowed = set(i for _, i in docs)
        t = time.perf_counter()
        labels, _ = index.knn_query(qv, k=min(len(allowed), 50), filter=lambda i: i in allowed)
        search_ms = (time.perf_counter() - t) * 1e3
        dense_rank = [idx2sid[int(i)] for i in labels[0]]

        hyb = rrf([bm25_rank, dense_rank])
        skip = conf >= TAU
        casc = bm25_rank if skip else hyb

        rows.append(dict(qid=q["question_id"], qtype=q["question_type"], n_gold=len(gold), conf=conf,
                         skip=skip, bm25_ms=bm25_ms, enc_ms=enc_ms, search_ms=search_ms,
                         **{f"hit_{n}": hit(r, gold) for n, r in
                            [("bm25", bm25_rank), ("dense", dense_rank), ("hybrid", hyb), ("cascade", casc)]},
                         **{f"rall_{n}": recall_all(r, gold) for n, r in
                            [("bm25", bm25_rank), ("dense", dense_rank), ("hybrid", hyb), ("cascade", casc)]}))

    ev = [r for r in rows if r["n_gold"] > 0]
    mean = lambda k, rs=ev: float(np.mean([r[k] for r in rs]))
    summary = dict(
        questions=len(rows), with_evidence=len(ev), unique_sessions=len(texts),
        skip_share=float(np.mean([r["skip"] for r in rows])),
        hit5={n: mean(f"hit_{n}") for n in ["bm25", "dense", "hybrid", "cascade"]},
        recall_all5={n: mean(f"rall_{n}") for n in ["bm25", "dense", "hybrid", "cascade"]},
        cascade_minus_hybrid_hit5=paired_bootstrap([r["hit_cascade"] for r in ev], [r["hit_hybrid"] for r in ev]),
        cascade_minus_hybrid_rall5=paired_bootstrap([r["rall_cascade"] for r in ev], [r["rall_hybrid"] for r in ev]),
        ms_median=dict(bm25=float(np.median([r["bm25_ms"] for r in rows])),
                       query_encode=float(np.median([r["enc_ms"] for r in rows])),
                       hnsw_search=float(np.median([r["search_ms"] for r in rows]))),
        embed_docs_seconds=embed_docs_s,
        skip_share_by_qtype={t: float(np.mean([r["skip"] for r in rows if r["qtype"] == t]))
                             for t in sorted({r["qtype"] for r in rows})},
        conf_median=float(np.median([r["conf"] for r in rows])),
    )
    json.dump(dict(summary=summary, rows=rows), open(a.out, "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
