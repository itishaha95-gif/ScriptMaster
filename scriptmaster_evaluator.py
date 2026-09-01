from __future__ import annotations
import argparse, json, re
from pathlib import Path
from ollama import chat

MODEL_DEFAULT = "qwen3:4b"

SYSTEM = """You are evaluating a generated spoken-word script for ScriptMaster.

Score from 0 to 10:
- style_match: alignment with the supplied style summary (hook, pacing, tone, transitions, rhetorical devices, structure, ending)
- topic_relevance: focus and usefulness for the topic
- script_quality: hook strength, flow, clarity, spoken naturalness, ending
- originality: originality and absence of obvious copying

Return ONLY a JSON object using exactly these keys:
{
  "style_match": 0,
  "topic_relevance": 0,
  "script_quality": 0,
  "originality": 0,
  "strengths": [],
  "issues": [],
  "verdict": ""
}
Use numeric values, not strings or percentages."""

def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default if default is not None else {}
    return json.loads(p.read_text(encoding="utf-8"))

def compact_style_profile(profile):
    if not isinstance(profile, dict):
        return {}
    preferred = [
        "scripts_analyzed","dominant_hook_types","dominant_tones","common_transitions",
        "common_rhetorical_devices","common_endings","global_style","summary"
    ]
    compact = {k: profile[k] for k in preferred if k in profile}
    if not compact:
        compact = {k:v for k,v in profile.items() if k not in {"script_analyses","analyses","items","examples"}}
    return compact

def deterministic_metrics(script, source_chunks=None):
    words = re.findall(r"\b[\w'-]+\b", script.lower())
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', script) if s.strip()]
    phrase_matches = set()
    if source_chunks:
        script_norm = " ".join(words)
        for c in source_chunks:
            toks = re.findall(r"\b[\w'-]+\b", c.get("text","").lower())
            for n in (7,8):
                for i in range(max(0, len(toks)-n+1)):
                    phrase = " ".join(toks[i:i+n])
                    if phrase in script_norm:
                        phrase_matches.add(phrase)
    return {
        "word_count": len(words),
        "sentence_count": len(sentences),
        "avg_sentence_words": round(len(words)/max(1,len(sentences)),2),
        "question_count": script.count("?"),
        "first_person_count": len(re.findall(r"\b(i|me|my|mine|we|our|us)\b",script.lower())),
        "second_person_count": len(re.findall(r"\b(you|your|you're|you've|you'll)\b",script.lower())),
        "long_source_phrase_matches": len(phrase_matches),
        "copying_check": "review" if phrase_matches else "pass"
    }

def extract_scores(obj):
    if not isinstance(obj, dict):
        return {}, [], [], ""
    candidates = [obj]
    for key in ("scores","evaluation","ratings","result"):
        if isinstance(obj.get(key), dict):
            candidates.append(obj[key])
    found = {}
    aliases = {
        "style_match":["style_match","style","style_score"],
        "topic_relevance":["topic_relevance","relevance","topic_score"],
        "script_quality":["script_quality","quality","quality_score"],
        "originality":["originality","originality_score"]
    }
    for target, names in aliases.items():
        for c in candidates:
            for n in names:
                if n in c:
                    found[target] = c[n]
                    break
            if target in found:
                break
    strengths = obj.get("strengths", [])
    issues = obj.get("issues", obj.get("weaknesses", []))
    verdict = obj.get("verdict", obj.get("summary", ""))
    return found, strengths, issues, verdict

def to_num(v):
    if isinstance(v,(int,float)):
        return max(0.0,min(10.0,float(v)))
    if isinstance(v,str):
        m = re.search(r"-?\d+(?:\.\d+)?",v)
        if m:
            x=float(m.group())
            if "%" in v: x/=10
            return max(0.0,min(10.0,x))
    return None

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--topic",required=True)
    p.add_argument("--generated",default="scriptmaster_local_output.json")
    p.add_argument("--style-profile",default="semantic_style_profile_local.json")
    p.add_argument("--chunks",default="data/processed/chunks.jsonl")
    p.add_argument("--model",default=MODEL_DEFAULT)
    p.add_argument("--output",default="scriptmaster_evaluation.json")
    a=p.parse_args()

    generated=load_json(a.generated)
    script=generated.get("script","")
    if not script:
        raise SystemExit("No 'script' field found in generated output.")

    profile=compact_style_profile(load_json(a.style_profile,{}))
    chunks=[]
    cp=Path(a.chunks)
    if cp.exists():
        chunks=[json.loads(x) for x in cp.read_text(encoding="utf-8").splitlines() if x.strip()]

    metrics=deterministic_metrics(script,chunks)
    payload={"topic":a.topic,"script":script,"style_summary":profile,"deterministic_metrics":metrics}

    response=chat(
        model=a.model,
        messages=[{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps(payload,ensure_ascii=False)}],
        format="json"
    )
    raw=response.message.content
    try:
        parsed=json.loads(raw)
    except Exception:
        parsed={}

    raw_scores,strengths,issues,verdict=extract_scores(parsed)
    scores={}
    missing=[]
    for key in ("style_match","topic_relevance","script_quality","originality"):
        val=to_num(raw_scores.get(key))
        if val is None:
            missing.append(key)
        scores[key]=val

    if metrics["copying_check"]=="review" and scores.get("originality") is not None:
        scores["originality"]=min(scores["originality"],6.0)

    valid=[v for v in scores.values() if isinstance(v,(int,float))]
    overall=round(sum(valid)/len(valid),2) if len(valid)==4 else None
    result={
        "topic":a.topic,"scores":scores,"overall_score":overall,
        "deterministic_metrics":metrics,"strengths":strengths if isinstance(strengths,list) else [str(strengths)],
        "issues":issues if isinstance(issues,list) else [str(issues)],"verdict":verdict,
        "raw_model_evaluation":parsed,"raw_model_text":raw
    }
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")

    print("\n=== SCRIPTMASTER EVALUATION ===\n")
    labels=[("Style Match","style_match"),("Topic Relevance","topic_relevance"),("Originality","originality"),("Script Quality","script_quality")]
    for label,key in labels:
        v=scores[key]
        print(f"{label:<18} {v:.1f}/10" if v is not None else f"{label:<18} PARSE ERROR")
    print("\nOverall Score:     " + (f"{overall:.2f}/10" if overall is not None else "Not calculated"))
    print("Copying Check:     "+metrics["copying_check"])
    if result["strengths"]:
        print("\nStrengths:")
        for x in result["strengths"]: print("-",x)
    if result["issues"]:
        print("\nIssues:")
        for x in result["issues"]: print("-",x)
    print("\nSaved:",a.output)

if __name__=="__main__":
    main()
