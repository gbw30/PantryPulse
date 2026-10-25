# OR v2 fixtures

These are explicitly regenerated from the retained `or-v1` fixtures by
`scripts/or/upgrade_fixtures.py`. They use inclusive DATED expiry and explicit
DATED/NON_EXPIRING/UNKNOWN declarations and have newly computed operational hashes.
Missing dates in old inputs become UNKNOWN, never implicitly NON_EXPIRING.

All data and policy scores are simulated. V1 evidence retains its original expiry
meaning and hashes; it is not evidence for v2 behavior. The new native regression,
independent enumeration, reduction-equivalence and connected stock tests qualify v2.
