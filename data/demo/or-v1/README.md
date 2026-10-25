# Synthetic OR fixtures

Every input is SIMULATED. The scarce six-beneficiary/two-product fixture implements
mathematical specification §13.3; AP/RP fixtures are deliberately reduced scopes.
Other fixtures exercise pantry donation, future donor protection, shared handling,
ETA/expiry and zero inventory. No file represents actual inventory or dispatch.

The checkpoint review corrected original on-hand availability from the first
planning date to the snapshot's local date. Original free stock must already exist
at the snapshot. Future confirmed arrivals remain separate. This correction keeps
the supply, targets, policy, capacities and independently expected optima unchanged.

Input/source revision is now `sim-v2-stock-asof`. Each SIMULATED_FIXTURE source
reference hashes the substantive wire input object excluding `source_refs` and
`source_manifest_hash`; the manifest hashes the source-reference collection. These
replace the initial all-zero source-fingerprint placeholders. Full operational
scenario hashes were regenerated after strict validation and freezing.

No stored scenario is rewritten by reading these files. Existing saved bytes keep
their original identities; corrected inputs create new scenarios. Old local test
fixtures with future on-hand declarations are invalid for new planning and must be
reseeded in their isolated synthetic scope. The original forecast/handoff identity
is independent of the operational input hash.
