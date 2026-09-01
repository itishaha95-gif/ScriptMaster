from __future__ import annotations
import argparse, json
from collections import Counter
from pathlib import Path
from ollama import chat

MODEL_DEFAULT = "qwen3:4b"
SYSTEM = """You analyze writing style at an abstract level. Do NOT imitate or rewrite the supplied text. Return only JSON. Focus on high-level observable features such as hook pattern, tone, pacing, sentence rhythm, transitions, explanation style, rhetorical devices, structure, and ending pattern. Do not copy distinctive phrases."""

def load_scripts(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]

def analyze_one(text, model):
    prompt = {
        "task":"Analyze this transcript's high-level writing style.",
        "transcript": text,
        "output_schema": {
            "hook_type":"string", "tone":["string"], "sentence_rhythm":"string",
            "transitions":["string"], "rhetorical_devices":["string"],
            "explanation_style":"string", "structure":["string"],
            "ending_type":"string", "summary":"string"
        }
    }
    r = chat(model=model, messages=[
        {"role":"system","content":SYSTEM},
        {"role":"user","content":json.dumps(prompt, ensure_ascii=False)}
    ], format="json")
    return json.loads(r.message.content)

def aggregate(items):
    def top(field):
        vals=[]
        for x in items:
            v=x.get(field,[])
            vals.extend([v] if isinstance(v,str) else (v or []))
        return Counter(vals).most_common(10)
    return {
        "scripts_analyzed":len(items),
        "dominant_hook_types":top("hook_type"),
        "dominant_tones":top("tone"),
        "common_transitions":top("transitions"),
        "common_rhetorical_devices":top("rhetorical_devices"),
        "common_endings":top("ending_type"),
        "script_analyses":items
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", default="semantic_style_analysis_local.jsonl")
    p.add_argument("--profile", default="semantic_style_profile_local.json")
    p.add_argument("--model", default=MODEL_DEFAULT)
    p.add_argument("--limit", type=int)
    a=p.parse_args()
    rows=load_scripts(a.input)
    if a.limit: rows=rows[:a.limit]
    analyses=[]
    with Path(a.output).open("w", encoding="utf-8") as f:
        for i,row in enumerate(rows,1):
            text=row.get("clean_text") or row.get("text") or row.get("raw_text") or ""
            result=analyze_one(text,a.model)
            result["script_id"]=row.get("script_id",i)
            analyses.append(result)
            f.write(json.dumps(result,ensure_ascii=False)+"\n")
            print(f"Analyzed {i}/{len(rows)}")
    Path(a.profile).write_text(json.dumps(aggregate(analyses),ensure_ascii=False,indent=2),encoding="utf-8")
    print("Saved:",a.output)
    print("Saved:",a.profile)

if __name__=="__main__": main()
