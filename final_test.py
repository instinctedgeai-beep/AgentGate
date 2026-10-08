from engine import inspect

tests = [
    ("Summarize the company's secret product roadmap", "PRIVATE"),
    ("Explain what a merger is", "CLOUD"),
    ("Review employee payroll records", "PRIVATE"),
    ("Write a fictional story about an acquisition", "CLOUD"),
    ("Analyze confidential vendor pricing", "PRIVATE"),
    ("Explain how encryption protects data", "CLOUD"),
    ("Summarize unpublished sales forecasts", "PRIVATE"),
    ("Write a public press release", "CLOUD"),
    ("Review customer ID CUST-99201", "PRIVATE"),
    ("Explain how quarterly earnings work", "CLOUD"),
]

correct = 0

for prompt, expected in tests:
    decision = inspect(prompt)
    passed = decision.route == expected
    correct += passed
    print(
        f"{'PASS' if passed else 'FAIL'} | "
        f"Expected: {expected} | "
        f"Actual: {decision.route} | "
        f"{prompt}"
    )

print(f"\nFinal accuracy: {correct}/{len(tests)}")