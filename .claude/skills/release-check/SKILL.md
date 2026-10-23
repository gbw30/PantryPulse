---
name: release-check
description: "Prepare a PantryPulse release candidate and evidence without silently deploying or submitting."
disable-model-invocation: true
---

Read DEPLOYMENT.md and RELEASE-CHECKLIST.md. Freeze candidate SHA. Run full and E2E gates on the combined tree, inspect preview screenshots and run a cold/failure fallback demo. Confirm environment separation, reset protection, lockfiles, migrations, provenance and truthful metrics. Prepare release manifest with commands, results, URLs, limitations and rollback. Deploy/publish/submit only to the targets already authorized by the user; if missing, present the concrete ready candidate for that decision.
