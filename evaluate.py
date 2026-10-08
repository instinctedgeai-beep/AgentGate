import csv, json, statistics
from pathlib import Path
from engine import inspect

# Synthetic examples only; labels are test expectations, not production ground truth.
CASES = [
 ('Draft a welcome email for new staff','CLOUD'),
 ('Summarize our public product launch','CLOUD'),
 ('List three marketing slogan ideas','CLOUD'),
 ('Explain SQL joins to a beginner','CLOUD'),
 ('Give tips for public speaking','CLOUD'),
 ('Write a weekly planning template','CLOUD'),
 ('Compare electric and gas cars','CLOUD'),
 ('What is the weather usually like in April?','CLOUD'),
 ('Brainstorm a team offsite agenda','CLOUD'),
 ('Make a meeting minutes outline','CLOUD'),
 ('Explain how a GPU works','CLOUD'),
 ('Write a generic customer support response','CLOUD'),
 ('Suggest interview questions for a PM','CLOUD'),
 ('Create a fictional story about a robot','CLOUD'),
 ('Summarize these public release notes','CLOUD'),
 ('Contact person@example.com about the rollout','PRIVATE'),
 ('Call 404-555-0123 to confirm the order','PRIVATE'),
 ('Their SSN is 123-45-6789','PRIVATE'),
 ('Charge card 4111 1111 1111 1111','PRIVATE'),
 ('Customer account number 1234567890 is flagged','PRIVATE'),
 ('Summarize this medical record for a patient','PRIVATE'),
 ('The API_KEY=abc123secret must stay confidential','PRIVATE'),
 ('Please email support@company.test','PRIVATE'),
 ('Patient was diagnosed with asthma yesterday','PRIVATE'),
 ('My password: sampleSecret123','PRIVATE'),
 ('Review this private contract for Acme Corp','PRIVATE'),
 ('Prepare notes for employee John Smith','PRIVATE'),
 ('The meeting involves confidential financial projections','PRIVATE'),
 ('What should we do about an unannounced acquisition?','PRIVATE'),
 ('Please parse the customer ID CUST-88021','PRIVATE'),
 ('Summarize the unreleased quarterly earnings report','PRIVATE'),
 ('Explain how to prepare for a job interview','CLOUD'),
 ('Analyze employee salary information','PRIVATE'),
 ('Draft a public announcement about our new office','CLOUD'),
 ('Review internal merger negotiations','PRIVATE'),
]

def main():
    rows=[]
    for prompt, expected in CASES:
        d=inspect(prompt)
        rows.append({'prompt':prompt,'expected':expected,'actual':d.route,'correct':int(expected==d.route),'inspection_ms':d.inspection_ms,'signals':','.join(d.signals)})
    out=Path(__file__).parent/'results.csv'
    with out.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    tp=sum(r['expected']=='PRIVATE' and r['actual']=='PRIVATE' for r in rows)
    fn=sum(r['expected']=='PRIVATE' and r['actual']=='CLOUD' for r in rows)
    fp=sum(r['expected']=='CLOUD' and r['actual']=='PRIVATE' for r in rows)
    summary={'samples':len(rows),'accuracy':round(sum(r['correct'] for r in rows)/len(rows),3),
             'sensitive_recall':round(tp/(tp+fn),3) if tp+fn else None,
             'false_positive_rate':round(fp/sum(r['expected']=='CLOUD' for r in rows),3),
             'median_inspection_ms':round(statistics.median(r['inspection_ms'] for r in rows),3),
             'false_negative_count':fn,'false_positive_count':fp,'note':'Synthetic offline classifier tests, not live inference benchmarks'}
    (Path(__file__).parent/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))
    print('Saved:',out)

if __name__=='__main__':main()
