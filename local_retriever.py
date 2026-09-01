from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_DEFAULT="sentence-transformers/all-MiniLM-L6-v2"

def load_jsonl(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]

def build(chunks_path,index_path,model_name):
    chunks=load_jsonl(chunks_path)
    model=SentenceTransformer(model_name)
    vecs=model.encode([c["text"] for c in chunks],normalize_embeddings=True,show_progress_bar=True)
    np.savez_compressed(index_path,embeddings=np.asarray(vecs,dtype="float32"))
    print(f"Saved {len(chunks)} embeddings -> {index_path}")

def search(query,chunks_path,index_path,model_name,k):
    chunks=load_jsonl(chunks_path)
    arr=np.load(index_path)["embeddings"]
    model=SentenceTransformer(model_name)
    q=model.encode([query],normalize_embeddings=True)[0].astype("float32")
    scores=arr@q
    order=np.argsort(-scores)
    results=[]; seen=set()
    for idx in order:
        sid=chunks[idx].get("script_id")
        if sid in seen: continue
        seen.add(sid)
        results.append({"score":float(scores[idx]),**chunks[idx]})
        if len(results)>=k: break
    return results

def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="cmd",required=True)
    b=sub.add_parser("build"); b.add_argument("--chunks",required=True); b.add_argument("--index",default="data/processed/local_embeddings.npz"); b.add_argument("--model",default=MODEL_DEFAULT)
    s=sub.add_parser("search"); s.add_argument("--query",required=True); s.add_argument("--chunks",required=True); s.add_argument("--index",default="data/processed/local_embeddings.npz"); s.add_argument("--model",default=MODEL_DEFAULT); s.add_argument("-k",type=int,default=6)
    a=p.parse_args()
    if a.cmd=="build": build(a.chunks,a.index,a.model)
    else:
        for r in search(a.query,a.chunks,a.index,a.model,a.k):
            print(f"\nScore: {r['score']:.3f} | Script {r.get('script_id')} | {r.get('chunk_id')}")
            print(r["text"][:500])

if __name__=="__main__": main()
