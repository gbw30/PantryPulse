"""A skipped process/database test does not satisfy the Linux merge gate."""
import sys
import xml.etree.ElementTree as ET

root = ET.parse(sys.argv[1]).getroot()
cases = root.findall(".//testcase")
assert cases, "No backend test evidence"
assert not root.findall(".//skipped"), "Skipped tests do not satisfy the Linux gate"
assert not root.findall(".//failure") and not root.findall(".//error"), "Backend tests failed"
print(f"{len(cases)} backend tests completed without skips or failures")
