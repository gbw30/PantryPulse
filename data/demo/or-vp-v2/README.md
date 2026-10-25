# Allocation integration test sources

These two fictional source files were copied from `origin/or_pipeline` at
`46ff0cd`, `data/demo/or-v1/six-beneficiary-v1.{input,snapshot}.json`.
They retain their original Draft 1.1 labels and are provenance inputs, not
current executable snapshots. `scripts/allocation_fixture.py` explicitly adapts
them into the VP v2 schema: inclusive expiry, explicit expiry kinds and optional
authenticated test organization. It recomputes a new scenario identity.

Policy coefficients and attributes are simulated fixtures, not production defaults
or research findings. No original branch native-solver evidence is attributed to
the modified v2 behavior; new tests must execute it independently.
