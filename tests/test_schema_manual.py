from src.schema import Finding, Evidence

# this should succeed
good = Finding(
    title="src/parsers/csv.py changed in 14 of last 50 PRs, no test file",
    category="hotspot",
    severity="high",
    evidence=[Evidence(url="https://github.com/pallets/flask/pull/123", reason="file changed here")],
    recommendation="Add unit tests for src/parsers/csv.py",
)
print("good case passed")

# this should fail: invalid category
try:
    bad = Finding(
        title="test",
        category="code_smell",
        severity="high",
        evidence=[Evidence(url="https://github.com/x/y/pull/1", reason="r")],
        recommendation="fix it",
    )
    print("BUG: bad category was accepted")
except Exception as e:
    print("correctly rejected bad category:", type(e).__name__)

# this should fail: empty evidence list
try:
    bad2 = Finding(
        title="test",
        category="hotspot",
        severity="high",
        evidence=[],
        recommendation="fix it",
    )
    print("BUG: empty evidence was accepted")
except Exception as e:
    print("correctly rejected empty evidence:", type(e).__name__)