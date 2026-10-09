# Implementation workflow and command guide

This guide explains the preserved `lab.py` code. Figure IDs refer to `docs/figures/`. `[C]` is the code and `[1]` is the original paper; reference details are in `REFERENCES.md`.

## 1. Prerequisites and workspace selection (F03, F04)

Python 3.10+ uses no external pip packages. Install MultiChain Community 2.3.3 separately. A data directory is not the same as the executable folder. All roles have distinct wallets, configuration files and RPC/P2P ports. Saved metadata selects the correct instances.

For the current student's machine, the working workspace is:

```text
C:\Users\BK-PC\Documents\Study Material\FAST - NUCES\Semester 3\Applications of Blockchain\Mid Term\FakeMedia_MultiChain_Exam_Kit\FakeMedia_Exam_Kit\workspace
```

Use README route A. A new checkout does not require moving this workspace. For a fresh examiner run use route B and record new addresses/genesis and ports. Never create a chain just because a path variable is empty.

## 2. Chain configuration before genesis (F04)

`setup()` creates directories, writes per-node runtime configuration, and calls `multichain-util create` with requested overrides. This is equivalent to setting those values in the newly created `params.dat` before the first daemon start. `config/params-overrides.example.txt` is a documentation snippet, not a complete chain parameter file. [C, 2, 3]

| Parameter | Requested default | Reason / interpretation |
|---|---|---|
| target-block-time | 2 seconds | Classroom confirmation target; not guaranteed actual latency |
| maximum-block-size | 8,388,608 bytes | 8 MiB bound; not a TPS claim |
| mining-diversity | 0.6 | Limits repeated block creation by recent miners |
| mining-turnover | 0 | Low-turnover local benchmark setting |
| mine-empty-rounds | -1 | Continue producing blocks for confirmation tests |
| setup-first-blocks | 10 | Initial bootstrap period; benchmark checks run beyond it |
| root-stream-open | false | Restrict arbitrary root-stream writes |
| anyone-can-connect/send/receive/create/issue/mine/admin | false | Use explicit role permissions |

Do not edit live `params.dat` to change an experiment. Capture observed `getblockchainparams`; create a separate explicit experimental workspace and nonconflicting ports for different creation-time settings. Some MultiChain parameters support upgrades, but this lab guide does not implement an upgrade workflow. [3]

Runtime settings are separate: per-node RPC credentials/ports, loopback RPC/P2P binding, `rpcthreads=16`, `txindex=1`, `autosubscribe=streams,assets` and `maxshowndata=2097152`. Do not publish the live `multichain.conf`. [C]

## 3. Start and join nodes (F03, F04)

`ensure_network()` starts the authority, identifies its administrator address, records genesis, discovers peer addresses, grants connection/transaction permissions and checks that each peer owns its saved identity. The auditor receives connect/receive but not send; the publisher/reviewers receive connect/send/receive. `complete_setup()` grants mining to both reviewers. The authority already holds genesis permissions. [C]

Connection syntax is `chain@host:P2P-port`. Default authority P2P is 7441, not RPC 8441. Protocol version 20013 is not a port. A daemon started without the correct `-datadir` is not necessarily one of the saved lab nodes. [2, C]

## 4. Create and subscribe streams (F02, F04)

| Stream | Intended writer(s) | Content |
|---|---|---|
| registry | authority | ENROLL records with role and signed challenge |
| news | publisher | Candidate article and content fingerprint |
| predictions | validator1 | Teaching-model recommendation and model hash |
| votes | validator1, validator2 | Signed reviewer labels/reasons bound to article |
| decisions | authority | Final application label and referenced votes |
| audit | authority | Permission-change/security/benchmark summaries |
| benchmarks | publisher | Controlled ledger-load records |

These are write-restricted streams, not encrypted/private streams. Every subscribed lab node can see on-chain article data. The authority creates and administers the streams and can grant further permissions; do not present the writer table as protection against a malicious administrator. [C, 4, 6]

## 5. Signed enrollment (F05)

The authority creates a challenge containing domain, chain name, genesis hash, intended role, wallet address, random nonce and issuance/expiry times. The role signs canonical JSON using `signmessage`; the authority validates bindings, expiry, unused nonce and `verifymessage`. Consumed nonces are stored locally, then an ENROLL record is written to `registry` and confirmed. After enrollment, the authority grants intended application writers. [C]

This proves possession of the designated private key, not verified real-world identity. The local nonce database and administrator approval are explicit trust assumptions. `security-tests` checks replay, altered role, expiry and wrong-key cases; save the actual outcomes. [C]

## 6. Submit one article (F06)

`submit()` checks membership, prevents duplicate IDs within the cooperating wrapper, hashes exact UTF-8 text using SHA-256 and writes a JSON item through `publishfrom`. MultiChain enforces the publisher's `news.write` permission when that publication is submitted. The content hash identifies text; a transaction ID identifies the publication transaction. They are not interchangeable. [C]

## 7. Analyze text (F06)

The teaching model removes selected stop words, retains negation, computes TF-IDF cosine evidence, forms lexical-count states, and learns a terminal Q policy with gamma=0. Below the similarity threshold (default 0.35) it returns REVIEW. Validator1 records a recommendation and the model file hash in `predictions`. Neither similarity nor a chain confirmation is a probability that the news is true. [C]

The fixture has 24 training and 8 test rows. Test results describe this tiny corpus only, not the paper's dataset or DRL. [C]

## 8. Record two reviews and finalize (F06, F07)

Each configured reviewer validates the confirmed article and writes a vote with its address, news ID, original article txid, content hash, label and reason. `finalize()` requires the article, no previous finalization, registered reviewers and current writer authorization. A precondition failure raises an error. Valid evidence from two distinct matching reviewers gives REAL/FAKE; otherwise the policy returns REVIEW. [C]

The authority writes the final decision. The Python policy is not executed by native miners. The model does not replace reviewer judgment; the demo and pipeline benchmark deliberately use fixture labels. [C]

### Complete manual fixture block

Run this from the new repository source folder. It defines its own variables and stops on a failed operation. It performs five signed publications and an audit query.

```powershell
& {
    $ErrorActionPreference = "Stop"
    $Workspace = "C:\Users\BK-PC\Documents\Study Material\FAST - NUCES\Semester 3\Applications of Blockchain\Mid Term\FakeMedia_MultiChain_Exam_Kit\FakeMedia_Exam_Kit\workspace"
    $Id = "manual-" + (Get-Date -Format "yyyyMMdd-HHmmssfff")
    python .\lab.py --workspace "$Workspace" doctor
    if ($LASTEXITCODE -ne 0) { throw "Readiness failed." }
    python .\lab.py --workspace "$Workspace" submit --id "$Id" --text "The LabTown library opens at nine in the morning according to the published schedule."
    if ($LASTEXITCODE -ne 0) { throw "Submit failed." }
    python .\lab.py --workspace "$Workspace" analyze --id "$Id"
    if ($LASTEXITCODE -ne 0) { throw "Analysis failed." }
    python .\lab.py --workspace "$Workspace" vote --role validator1 --id "$Id" --label REAL --reason "Classroom fixture label, not independent fact checking."
    if ($LASTEXITCODE -ne 0) { throw "First vote failed." }
    python .\lab.py --workspace "$Workspace" vote --role validator2 --id "$Id" --label REAL --reason "Classroom fixture label, not independent fact checking."
    if ($LASTEXITCODE -ne 0) { throw "Second vote failed." }
    python .\lab.py --workspace "$Workspace" finalize --id "$Id"
    if ($LASTEXITCODE -ne 0) { throw "Finalization failed." }
    python .\lab.py --workspace "$Workspace" inspect --id "$Id"
    if ($LASTEXITCODE -ne 0) { throw "Inspect command failed." }
    Write-Host "Read the audit_pass field; a successful command alone is not a successful audit."
}
```

## 9. Audit and integrity (F06, F09)

`inspect()` reads the auditor's confirmed copy, recomputes text hash and the referenced-vote outcome, checks expected transaction publishers/references and reports `audit_pass`. It does not reconstruct all historical permissions or guarantee that all relevant conflicting records were included. `verify-file` compares exact file bytes with the original text hash; BOM/newline changes count as changes. [C]

## 10. Asset and descriptive credibility

Setup issues a fixed 1,000-unit NewsCredit asset once and subscribes every node. `reward --amount 1` explicitly transfers one unit from authority to publisher. This command does not prove publication correctness or update mining rights. `reputation` derives the teaching score clip(50 + 5*REAL - 10*FAKE, 0, 100) from authority decisions; it is separate from token balances and is not the paper's score formula. [C]

## 11. Security, benchmarks and evidence

Run demo, security tests, 10 requests and then the larger requested load. The collector automates this ordering and stops on failure. Detailed metrics and experiments are in `BENCHMARKS.md`; security flow is F09. An expected rejection is a passed negative test only when the test verifies the intended rejection, not an unrelated transport failure. [C]

## 12. Restart and stop safely

Use `start`, not `setup`, for a completed workspace. `repair` resumes incomplete setup without deleting wallets; completed setups preserve intentional revocations. `stop` waits for node listeners to close. Keep an evidence export and private backups before moving machines. No commands here require grant-all, deleting the ledger, or using a guessed seed address. [C]
