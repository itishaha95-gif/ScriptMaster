from __future__ import annotations
import argparse,json,re
from pathlib import Path
from ollama import chat

MODEL_DEFAULT="qwen3:4b"

SYSTEM='''You are ScriptMaster, an ORIGINAL spoken-script generator.

The USER TOPIC is the single most important instruction.
Never drift to another topic.

Use the supplied STYLE PROFILE only for:
- hook style
- pacing
- sentence rhythm
- tone
- rhetorical questions
- transitions
- structure
- ending style

Do NOT use source transcript content, anecdotes, examples, names, facts, or subject matter.

Writing requirements:
- Stay tightly focused on the exact user topic.
- 180–280 words unless the topic clearly needs less.
- Spoken, conversational, engaging.
- Strong hook in the first 1–2 sentences.
- Clear middle progression.
- End with a memorable thought/question.
- Do not invent studies, statistics, dates, or quotations.
- If the premise is uncertain, qualify it.
- Return JSON only with keys: title, hook, script, style_notes.
'''

def load_json(path,default=None):
    p=Path(path)
    if not p.exists(): return default if default is not None else {}
    return json.loads(p.read_text(encoding="utf-8"))

def compact_style_profile(profile):
    if not isinstance(profile,dict): return {}
    preferred=["scripts_analyzed","dominant_hook_types","dominant_tones","common_transitions","common_rhetorical_devices","common_endings","global_style","summary"]
    compact={k:profile[k] for k in preferred if k in profile}
    if compact: return compact
    return {k:v for k,v in profile.items() if k not in {"script_analyses","analyses","items","examples"}}

def keyword_coverage(topic,script):
    stop={"are","is","the","a","an","of","to","use","using","due","because","do","does","people","what","why","how","can","could","should","would","and","or","in","on"}
    terms=[t for t in re.findall(r"[a-zA-Z0-9']+",topic.lower()) if len(t)>2 and t not in stop]
    s=script.lower()
    if not terms: return 1.0
    return sum(1 for t in terms if t in s)/len(terms)

def call_model(topic,style,model,extra=""):
    payload={"USER_TOPIC":topic,"STYLE_PROFILE":style,"IMPORTANT":"Write only about USER_TOPIC. STYLE_PROFILE controls style, never subject matter."}
    r=chat(model=model,messages=[{"role":"system","content":SYSTEM+extra},{"role":"user","content":json.dumps(payload,ensure_ascii=False)}],format="json")
    return json.loads(r.message.content)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--topic",required=True)
    p.add_argument("--style-profile",default="semantic_style_profile_local.json")
    p.add_argument("--model",default=MODEL_DEFAULT)
    p.add_argument("--output",default="scriptmaster_local_output.json")
    a=p.parse_args()

    style=compact_style_profile(load_json(a.style_profile,{}))
    out_path=Path(a.output)
    if out_path.exists(): out_path.unlink()

    out=call_model(a.topic,style,a.model)
    script=out.get("script","")
    coverage=keyword_coverage(a.topic,script)

    if coverage<0.5:
        out=call_model(a.topic,style,a.model,extra=f'\nCRITICAL: The previous attempt drifted off topic. The exact topic is: "{a.topic}". Every paragraph must clearly relate to it.')
        script=out.get("script","")
        coverage=keyword_coverage(a.topic,script)

    out["topic"]=a.topic
    out["topic_keyword_coverage"]=round(coverage,3)
    out["generation_status"]="pass" if coverage>=0.5 else "review"
    out_path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")

    print("\n=== FINAL SCRIPT ===\n")
    print(out.get("script",""))
    print(f"\nTopic coverage: {coverage:.2f}")
    print("Status:",out["generation_status"])

if __name__=="__main__": main()
