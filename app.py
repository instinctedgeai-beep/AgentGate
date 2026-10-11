"""AgentGate V8 — refined analytics spacing."""
import csv
import html
import json
from pathlib import Path
from agent_playground import render_agent_playground

import pandas as pd
import streamlit as st
from engine import inspect, execute

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="AgentGate | Control Room", page_icon="⬡", layout="wide", initial_sidebar_state="collapsed")
st.markdown('''<style>
:root {color-scheme: dark;}
[data-testid="stSidebar"], [data-testid="collapsedControl"] {display:none!important}
header[data-testid="stHeader"] {height:0;background:transparent}
#MainMenu,footer {visibility:hidden}
.stApp {background:radial-gradient(ellipse 80% 36% at 65% -15%,rgba(174,211,137,.12),transparent 70%),#0b0e0e;color:#eef2ee}
.block-container {max-width:1370px;padding:1.3rem 3rem 3rem!important}
[data-testid="stVerticalBlock"] {gap:.62rem}
[data-testid="stHorizontalBlock"] {align-items:stretch}
[data-testid="stColumn"] {min-width:0}
[data-baseweb="tab-list"] {gap:1.6rem;border-bottom:1px solid #303632}
[data-baseweb="tab"] {padding:0 .1rem;height:2.5rem;font-weight:550}
[data-testid="stButton"] button {background:#1b211e;color:#e5ece5;border:1px solid #313d34;border-radius:20px;min-height:2.4rem;font-size:.86rem}
[data-testid="stButton"] button:hover {border-color:#b7eb8a;background:#283329}
[data-testid="stFormSubmitButton"] button[kind="primary"] {background:#b7ed86!important;color:#101810!important;border:0!important;border-radius:12px;font-weight:750;min-height:2.9rem}
[data-testid="stForm"] {border:none;padding:0;background:transparent}
[data-testid="stTextArea"] textarea {background:#191f1a;border:1px solid #39443c;border-radius:15px;font-size:.95rem;min-height:116px!important}
[data-testid="stMetric"] {background:rgba(30,37,31,.85);border:0;border-radius:17px;padding:14px 17px;min-height:110px}
[data-testid="stMetricLabel"] {color:#a6b5a6;font-size:.85rem}
[data-testid="stMetricValue"] {font-size:1.72rem;font-weight:700;letter-spacing:-.04em}
[data-testid="stDataFrame"] {border-radius:12px;overflow:hidden}
[data-testid="stAlert"] {border-radius:13px}
[data-testid="stSegmentedControl"] {margin-bottom:.15rem}
.ag-top {display:flex;justify-content:space-between;align-items:center;padding:4px 0 18px;gap:16px}
.ag-brand {display:flex;align-items:center;gap:11px}
.ag-mark {width:40px;height:40px;background:#bded90;border-radius:13px;display:grid;place-items:center;color:#13200f;font-size:26px}
.ag-name {font-size:24px;letter-spacing:-1px;font-weight:800;line-height:1}
.ag-sub {font-size:10px;color:#9cafa1;letter-spacing:1.5px;margin-top:5px}
.ag-env {font-size:11px;color:#cce8b9;border:1px solid #3b503f;border-radius:100px;padding:7px 13px}
.ag-hero {padding:1.1rem 0 1.3rem;min-height:125px}
.ag-overline {text-transform:uppercase;color:#b2d39e;font-size:10px;letter-spacing:1.6px;font-weight:700}
.ag-h1 {font-size:clamp(32px,3.7vw,52px);line-height:1.06;letter-spacing:-2px;font-weight:750;margin:9px 0 8px}
.ag-h1 em {color:#b5e98e;font-style:normal}
.ag-lead {color:#a2b0a3;font-size:14px;line-height:1.5}
.ag-kicker {font-size:11px;letter-spacing:1.25px;font-weight:700;color:#a7bd9f;text-transform:uppercase;padding:6px 0}
.ag-section {font-size:20px;font-weight:680;letter-spacing:-.5px;margin-bottom:6px}
.ag-help {font-size:12px;color:#a8b5a7;line-height:1.5}
.ag-panel-head {height:104px;box-sizing:border-box;padding-top:2px;}
.ag-panel-head .ag-kicker {padding:0 0 8px;margin:0;}
.ag-panel-head .ag-section {margin:0 0 6px;line-height:1.3;}
.ag-panel-head .ag-help {margin:0;max-width:96%;}
.ag-workspace-rule {border-top:1px solid #2a342c;margin:42px 0 24px;}
.ag-analytics-title {margin:0 0 18px;color:#a7bd9f;font-size:11px;letter-spacing:1.25px;font-weight:700;text-transform:uppercase;}
.ag-analytics-gap {height:34px;}
.ag-bottom-heading {min-height:108px;box-sizing:border-box;padding:0 0 22px;}
.ag-bottom-heading .ag-kicker {padding:0 0 9px;}
.ag-bottom-heading .ag-section {margin-bottom:11px;}
.ag-bottom-heading .ag-help {line-height:1.65;}
[data-testid="stForm"] {margin-top:8px;}
.ag-verdict {padding:19px 22px;background:linear-gradient(135deg,#26372b,#1c2924 60%,#1a2420);border-radius:21px;min-height:190px}
.ag-verdict.private {background:linear-gradient(135deg,#3b2d28,#2d2725 65%,#1c211f)}
.ag-vlabel {font-size:10px;letter-spacing:1.4px;text-transform:uppercase;color:#d2e5c8;font-weight:700}
.ag-big {font-size:clamp(24px,2.2vw,34px);font-weight:730;letter-spacing:-1px;line-height:1.12;margin:12px 0}
.ag-meta {font-size:12px;color:#c0cebc;line-height:1.6;overflow-wrap:anywhere}
.ag-output {background:#181e1a;border-radius:16px;padding:14px 17px;color:#d5e0d5;font-size:13px;line-height:1.65;min-height:95px;overflow-wrap:anywhere}
.ag-empty {background:linear-gradient(135deg,#243027,#1d2620);border-radius:21px;padding:23px;min-height:190px}
.ag-line {height:1px;background:#2a342c;margin:9px 0 12px}
.ag-footer {color:#849788;font-size:11px;padding-top:12px}
@media(max-width:900px){.block-container{padding:1rem 1.2rem 2rem!important}.ag-h1{letter-spacing:-1px}.ag-env{display:none}}
</style>''', unsafe_allow_html=True)

if 'history' not in st.session_state:
    st.session_state.history = []
if 'prompt_v6' not in st.session_state:
    st.session_state.prompt_v6 = ''
if 'mode_v6' not in st.session_state:
    st.session_state.mode_v6 = 'simulate'
history = st.session_state.history

def sample(text):
    st.session_state.prompt_v6 = text

def activity_chart(rows):
    counts = {'PRIVATE':0, 'CLOUD':0, 'BLOCKED':0}
    data = []
    for i, r in enumerate(reversed(rows), 1):
        counts[r['route']] += 1
        counts['BLOCKED'] += (r['status'] == 'BLOCKED')
        data.append({'Request':i,'Private':counts['PRIVATE'],'Cloud':counts['CLOUD'],'Blocked':counts['BLOCKED']})
    return pd.DataFrame(data).set_index('Request')

st.markdown('''<div class="ag-top"><div class="ag-brand"><div class="ag-mark">⬡</div><div><div class="ag-name">AgentGate</div><div class="ag-sub">POLICY INTELLIGENCE</div></div></div><div class="ag-env">● LOCAL PROTOTYPE</div></div>''', unsafe_allow_html=True)
control, audit, agent = st.tabs([
    'Workspace',
    'Evaluation & audit',
    'AI Agent Playground'
])

with control:
    st.markdown('''<div class="ag-hero"><div class="ag-overline">AI GOVERNANCE / CONTROL CENTER</div><div class="ag-h1">Every request. <em>Under control.</em></div><div class="ag-lead">Make confident routing decisions for enterprise AI agents — inspect the input, understand the policy, and see the outcome.</div></div>''',unsafe_allow_html=True)
    left,right = st.columns([1.02,.98],gap='large',vertical_alignment='top')
    with left:
        st.markdown('<div class="ag-panel-head"><div class="ag-kicker">01 &nbsp; / &nbsp; REQUEST CONSOLE</div><div class="ag-section">Test a request</div><div class="ag-help">Try an example to see how public and sensitive requests are handled.</div></div>',unsafe_allow_html=True)
        b1,b2,b3=st.columns(3,gap='small')
        b1.button('↗ Public',on_click=sample,args=('Explain how NVIDIA GPUs accelerate AI inference.',),use_container_width=True)
        b2.button('◇ Personal',on_click=sample,args=('Summarize the record for sample.user@example.com.',),use_container_width=True)
        b3.button('⬡ Confidential',on_click=sample,args=('Review confidential merger negotiations.',),use_container_width=True)
        with st.form('request_v6'):
            st.segmented_control('Execution mode',['simulate','live'],key='mode_v6')
            st.text_area('Agent prompt',key='prompt_v6',height=115,placeholder='Enter a request for classification…')
            submit=st.form_submit_button('Inspect & route   ↗',type='primary',use_container_width=True)
        st.markdown('<div class="ag-help">Simulate makes no model calls. Live sends CLOUD requests to hosted Nemotron; PRIVATE requires a separately configured private NIM endpoint.</div>',unsafe_allow_html=True)

    if submit:
        raw=st.session_state.prompt_v6
        if not raw.strip():
            st.warning('Choose a sample or enter a request.')
        else:
            with st.spinner('Inspecting policy…'):
                decision=inspect(raw)
                result=execute(raw,decision,mode=st.session_state.mode_v6)
            history.insert(0,{**decision.__dict__,**result,'execution_mode':st.session_state.mode_v6})

    with right:
        st.markdown('<div class="ag-panel-head"><div class="ag-kicker">02 &nbsp; / &nbsp; POLICY DECISION</div><div class="ag-section">Decision intelligence</div><div class="ag-help">See why a request is routed and whether inference was allowed.</div></div>',unsafe_allow_html=True)
        if history:
            item=history[0]
            private=item['route']=='PRIVATE'
            title='Private route required' if private else 'Approved for cloud inference'
            cls='private' if private else ''
            detail=html.escape(str(item['reason']))
            st.markdown(f'<div class="ag-verdict {cls}"><div class="ag-vlabel">{html.escape(item["route"])} ROUTE &nbsp; / &nbsp; {html.escape(item["status"])}</div><div class="ag-big">{title}</div><div class="ag-meta">{detail}</div><div class="ag-line"></div><div class="ag-meta">{html.escape(item["policy_id"])} &nbsp;·&nbsp; {item["inspection_ms"]:.3f} ms inspection &nbsp;·&nbsp; {html.escape(item.get("execution_mode","simulate"))}</div></div>',unsafe_allow_html=True)
            st.markdown('<div class="ag-kicker" style="margin-top:10px">MODEL RESPONSE / EXECUTION</div>',unsafe_allow_html=True)
            response=html.escape(str(item['response']))
            t=f'{item["inference_ms"]:.1f} ms' if item.get('inference_ms') is not None else 'N/A'
            st.markdown(f'<div class="ag-output">{response}<div class="ag-line"></div><span class="ag-help">Inference {t} &nbsp; · &nbsp; Tokens {item.get("tokens") if item.get("tokens") is not None else "N/A"}</span></div>',unsafe_allow_html=True)
        else:
            st.markdown('<div class="ag-empty"><div class="ag-overline">READY TO INSPECT</div><div class="ag-big">Your policy verdict appears here.</div><div class="ag-meta">Choose an example, keep Simulate selected, then run inspection. The route, policy, and result will appear here.</div></div>',unsafe_allow_html=True)
            st.markdown('<div class="ag-kicker">HOW IT WORKS</div><div class="ag-help">① Classify the prompt &nbsp; → &nbsp; ② Apply routing policy &nbsp; → &nbsp; ③ Record the decision</div>',unsafe_allow_html=True)

    st.markdown('<div class="ag-workspace-rule"></div><div class="ag-analytics-title">03 &nbsp; / &nbsp; SESSION INTELLIGENCE</div>',unsafe_allow_html=True)
    total=len(history)
    private=sum(r['route']=='PRIVATE' for r in history)
    cloud=total-private
    blocked=sum(r['status']=='BLOCKED' for r in history)
    k1,k2,k3,k4=st.columns(4,gap='small')
    k1.metric('Total requests',total)
    k2.metric('Private routed',f'{private/total:.0%}' if total else '—')
    k3.metric('Cloud routed',cloud)
    k4.metric('Blocked in live mode',blocked)

    st.markdown('<div class="ag-analytics-gap"></div>',unsafe_allow_html=True)
    chart_col, log_col=st.columns([1.25,.75],gap='large',vertical_alignment='top')
    with chart_col:
        st.markdown('<div class="ag-bottom-heading"><div class="ag-kicker">TRAFFIC TREND</div><div class="ag-section">Routing activity</div><div class="ag-help">Cumulative routing activity by request sequence.</div></div>',unsafe_allow_html=True)
        if history:
            st.line_chart(activity_chart(history),height=230,color=['#B8E98E','#77B9BD','#E9A377'])
        else:
            st.markdown('<div class="ag-output">Run an example to populate the traffic timeline. The graph uses real session data, not sample metrics.</div>',unsafe_allow_html=True)
    with log_col:
        st.markdown('<div class="ag-bottom-heading"><div class="ag-kicker">RECENT EVENTS</div><div class="ag-section">Decision log</div><div class="ag-help">Latest routing activity in this session.</div></div>',unsafe_allow_html=True)
        if history:
            rows=[{'Time':r['timestamp'][11:19],'Route':r['route'],'Policy':r['policy_id'],'Result':r['status']} for r in history[:5]]
            st.dataframe(rows,hide_index=True,use_container_width=True,height=230)
        else:
            st.markdown('<div class="ag-output">No requests inspected yet.</div>',unsafe_allow_html=True)
    st.markdown('<div style="height:22px"></div>',unsafe_allow_html=True)
    st.markdown('<div class="ag-footer">Prototype · Session-only data · Pattern-based classification is not comprehensive DLP protection.</div>',unsafe_allow_html=True)

with audit:
    st.markdown('### Evaluation & audit')
    st.caption('Synthetic development tests, not independently validated production security results.')
    sf=ROOT/'summary.json'
    rf=ROOT/'results.csv'
    if sf.exists():
        data=json.loads(sf.read_text())
        a,b,c=st.columns(3)
        a.metric('Development accuracy',f'{data["accuracy"]:.1%}')
        b.metric('Sensitive recall',f'{data["sensitive_recall"]:.1%}')
        c.metric('Median inspection',f'{data["median_inspection_ms"]} ms')
    else:
        st.info('Run python evaluate.py to generate evaluation metrics.')
    if rf.exists():
        with st.expander('View evaluation cases'):
            with rf.open(newline='') as fp:
                st.dataframe(list(csv.DictReader(fp)),hide_index=True,use_container_width=True)
    st.divider()
    st.subheader('Audit trail')
    st.caption('Decision metadata only; no raw prompts are retained in the audit trail.')
    if history:
        fields=['timestamp','request_id','route','policy_id','signals','reason','inspection_ms','execution_mode','status','inference_ms','tokens','cost_usd']
        log=[{k:r.get(k) for k in fields} for r in history]
        st.dataframe(log,hide_index=True,use_container_width=True)
        st.download_button('Export audit JSON',data=json.dumps(log,indent=2),file_name='agentgate-audit.json',mime='application/json')
    else:
        st.info('No audit events in this session.')

with agent:
    render_agent_playground()