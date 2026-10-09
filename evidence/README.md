# Evidence provenance and limits

`provided-run/` contains selected JSON outputs extracted from the student's supplied `Pasted text(3).txt`. Its provenance file records the source hash and path redaction. These are real supplied log excerpts, **not screenshots and not independent executions by the package author**.

Supported observations: application version 2.0.2; setup_complete and all_passed true; five online roles; shared block 552 hash agreement; doctor height_lag 1; authority getinfo block 554, four connections, one asset, eight total streams and empty errors string. The status output includes three confirmed decision records and zero benchmark items at that snapshot. A decision-record count alone does not establish decision validity. Eight total streams includes the default root plus seven application streams; the status list is the evidence to inspect.

Not established by this transcript: application demo overall pass; live security tests overall pass; a successful 1,000-request benchmark; paper-equivalent model accuracy; multi-host resilience. Empty benchmark evidence is not a zero-latency measurement. No such results are invented here.

`validation/` at repository root contains fresh local Python test output. Those tests do not run MultiChain daemons. Future live exports belong in `evidence/runs/`, with their actual run IDs and provenance. Do not relabel local mock tests as Windows integration tests.

Use `tools/export_evidence.py --workspace PATH` for reviewed public copies. It copies only known evidence names, excludes private node state, redacts paths and records original/exported hashes. It does not copy summary anchors because anchors refer to the exact original bytes, not a reformatted export. Preserve originals privately for audit.
