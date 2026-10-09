# Genuine screenshot and observation plan

Capture screenshots on the actual Windows machine after running each command. Use Windows+Shift+S or your usual screenshot tool. Include the command and relevant output; never display a password, wallet backup or the full configuration file. Save reviewed images in `docs/screenshots/`. Do not generate or reconstruct a terminal screen and call it a screenshot.

| ID / suggested filename | What to capture | Explain below the screenshot |
|---|---|---|
| S01-prerequisites.png | Python version, lab version, three executable Test-Path checks | Software actually installed |
| S02-network-ready.png | `doctor`: all five roles, all_passed, shared hash/height lag | Readiness vs performance |
| S03-ports-peers.png | `rpc getinfo` and `rpc getpeerinfo` | RPC port vs P2P port; five processes on one host |
| S04-parameters.png | `rpc getblockchainparams` selected fields | 2 s target, 8 MiB maximum, diversity 0.6 as observed |
| S05-streams.png | `rpc liststreams` and selected write restrictions | Seven app streams plus root; write ACL is not privacy |
| S06-enrollment.png | A `registry` ENROLL item; no private keys | Signed challenge, role/address binding, expiry |
| S07-news.png | One submitted article record and SHA-256 | Content fingerprint and transaction ID differ |
| S08-prediction.png | NLP output and corresponding prediction record | Teaching recommendation, not fact verification |
| S09-votes-decision.png | Two distinct votes and final decision | Application policy vs block consensus |
| S10-auditor.png | `inspect`: audit_pass and exact referenced txids | What was recomputed, and what was not checked |
| S11-security.png | Actual `security-tests` overall result and chosen checks | Expected denial is a passed negative test |
| S12-asset.png | `rpc listassets`; optional `reward --amount 1` output | 1,000 initial units; transfer is not reputation |
| S13-load-10.png | 10-request benchmark counts and times | Verify small workload before larger one |
| S14-load-1000.png | 1,000-request summary and run ID | Success/failure/unknown, confirmation count and timing |
| S15-repository.png | GitHub file tree and a real commit | Repository location and examiner accessibility |

Screenshots for setup, paper/model interpretation, security, and load tests require different explanations. Do not reuse one green readiness screenshot to claim all stages passed. For commands with IDs or RPC arguments, use the manual workflow guide; do not paste wallet/configuration contents.

Suggested caption pattern: "Screenshot S07. Article [id] submitted from the publisher node in run [id/date]; [specific observed field] demonstrates [bounded claim]." Replace the bracketed text with your own words and actual values.
