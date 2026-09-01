from __future__ import annotations
import json,subprocess,sys
from pathlib import Path
import streamlit as st

APP_DIR=Path(__file__).resolve().parent
GENERATOR=APP_DIR/"scriptmaster_local.py"
EVALUATOR=APP_DIR/"scriptmaster_evaluator.py"
GEN_JSON=APP_DIR/"scriptmaster_local_output.json"
EVAL_JSON=APP_DIR/"streamlit_evaluation.json"

st.set_page_config(page_title="ScriptMaster",page_icon="📝",layout="centered")
st.title("ScriptMaster")
st.caption("Local AI script generation using a learned style profile and Qwen3.")
topic=st.text_area("Enter a topic",height=100,placeholder="Example: Are people less emotional due to use of AI?")

def run(args):
    return subprocess.run(args,cwd=APP_DIR,capture_output=True,text=True)

if st.button("Generate Script",type="primary",use_container_width=True):
    if not topic.strip():
        st.warning("Enter a topic first."); st.stop()

    for p in (GEN_JSON,EVAL_JSON):
        if p.exists():
            try: p.unlink()
            except: pass

    with st.status("Generating script...",expanded=True) as status:
        st.write("Applying the learned style profile...")
        result=run([sys.executable,str(GENERATOR),"--topic",topic.strip()])
        if result.returncode!=0:
            st.error("Generation failed."); st.code(result.stderr or result.stdout); status.update(label="Failed",state="error"); st.stop()
        if not GEN_JSON.exists():
            st.error("No fresh generation file was created."); status.update(label="Failed",state="error"); st.stop()
        data=json.loads(GEN_JSON.read_text(encoding="utf-8"))
        if data.get("topic","").strip()!=topic.strip():
            st.error("The generator returned a stale or mismatched result."); status.update(label="Topic mismatch",state="error"); st.stop()
        script=data.get("script","")
        st.session_state["latest_topic"]=topic.strip()
        st.session_state["latest_script"]=script
        st.session_state["latest_data"]=data
        status.update(label="Script generated",state="complete")

if "latest_script" in st.session_state:
    data=st.session_state.get("latest_data",{})
    st.subheader("Final Script")
    st.write(st.session_state["latest_script"])
    coverage=data.get("topic_keyword_coverage")
    if coverage is not None: st.caption(f"Topic coverage check: {coverage:.0%}")
    if data.get("generation_status")!="pass": st.warning("This output may have drifted from the topic. Regenerate before using it.")
    st.divider()
    if EVALUATOR.exists() and st.button("Evaluate Script",use_container_width=True):
        with st.spinner("Evaluating..."):
            ev=run([sys.executable,str(EVALUATOR),"--topic",st.session_state["latest_topic"],"--output",str(EVAL_JSON)])
        if ev.returncode!=0 or not EVAL_JSON.exists():
            st.error("Evaluation failed."); st.code(ev.stderr or ev.stdout)
        else:
            st.session_state["evaluation"]=json.loads(EVAL_JSON.read_text(encoding="utf-8"))

if "evaluation" in st.session_state:
    e=st.session_state["evaluation"]; scores=e.get("scores",{})
    st.subheader("Evaluation")
    c1,c2=st.columns(2)
    with c1:
        st.metric("Style Match",f"{scores.get('style_match','—')}/10")
        st.metric("Originality",f"{scores.get('originality','—')}/10")
    with c2:
        st.metric("Topic Relevance",f"{scores.get('topic_relevance','—')}/10")
        st.metric("Script Quality",f"{scores.get('script_quality','—')}/10")
    if e.get("overall_score") is not None: st.metric("Overall Score",f"{e['overall_score']}/10")
