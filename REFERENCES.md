# References and evidence identifiers

**[1] Selected paper.** Z. Shahbazi and Y.-C. Byun, "Fake Media Detection Based on Natural Language Processing and Blockchain Approaches," IEEE Access, vol. 9, pp. 128442-128453, 2021. DOI 10.1109/ACCESS.2021.3112607. Supplied PDF: `paper/Selected_Paper.pdf`. Relevant locations: Figure 1 (PDF p.3); Section III and Figures 2-6 (pp.4-6); Section V and Table 6 (p.8); Section VI (pp.10-11); Section VII Conclusion (p.11).

**[2] MultiChain, Creating and connecting to a blockchain.**
https://www.multichain.com/developers/creating-connecting/

**[3] MultiChain, Customizing blockchain parameters.**
https://www.multichain.com/developers/blockchain-parameters/

**[4] MultiChain, JSON-RPC API commands.**
https://www.multichain.com/developers/json-rpc-api/

**[5] MultiChain, Permissions management.**
https://www.multichain.com/developers/permissions-management/

**[6] MultiChain, Data streams.**
https://www.multichain.com/developers/data-streams/

**[7] GitHub Docs, Adding locally hosted code to GitHub.**
https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github

**[8] GitHub Docs, Building and testing Python.**
https://docs.github.com/en/actions/tutorials/build-and-test-code/python

**[C] Implementation source.** `lab.py` version 2.0.3-permission-check (2.0.2-mining-check plus the security-test permission-code fix) and `demo_news.csv`. Symbol/line index: `docs/CODE_INDEX.md`. This is the source for claims about this lab, not about the original paper.

**[E1] Supplied execution evidence.** User-supplied `Pasted text(3).txt`, captured timestamp reported as 2026-10-08T19:41:12.916+00:00. Selected path-redacted JSON in `evidence/provided-run/`; provenance records the original log hash. Not independently re-executed by the packager.

**[E2] Local package tests.** `validation/unit-tests.txt`: 99 tests run during packaging; no native MultiChain daemon. These results are separate from E1 and from any later Windows benchmark.

Public documentation checked on 2026-10-09. Pin runtime expectations to the installed MultiChain version and record observed parameters. The paper's terminology and reported results are attributed to the paper; this reference does not silently reconcile its mixed PoA/PBFT/RAFT discussion.
