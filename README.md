# FakeMedia-MultiChain: Windows PowerShell from setup to shutdown

**Application:** `2.0.2-mining-check` | **MultiChain:** Community 2.3.3 | **Python:** 3.10+

This README is the operating guide for the supplied FakeMedia GitHub submission package. It starts with the exact setup, start, test, and stop commands, then explains the application, security tests, load tests, evidence, and GitHub submission.

## Your folders

| Folder | Path | What belongs here |
|---|---|---|
| Source code | `C:\inetpub\wwwroot\XauZit\Practice\FakeMedia-MultiChain` | `lab.py`, this README, dataset, tests, and documentation |
| MultiChain installation | `C:\Users\BK-PC\Downloads\Programs\multichain-windows-2.3.3` | `multichaind.exe`, `multichain-cli.exe`, `multichain-util.exe` |
| Recommended NEW private workspace | `%LOCALAPPDATA%\FakeMedia-MultiChain\workspace` | Wallets, blockchain data, private RPC configuration, model, and original evidence |
| Existing workspace | The directory already containing your working `lab.json` | Reuse this when only the source-code folder changed |

> **Important for your new `inetpub\wwwroot` path:** this project is a command-line application, not an IIS website. Do not make this repository, its `.git` directory, private logs, or wallets accessible through a website. A path under `wwwroot` may be served by IIS depending on its site mappings. This guide therefore puts NEW blockchain state outside the source tree. `.gitignore` is not web-server access control. See [R4](#references). Nothing in this README changes IIS settings.
>
> **Moving source code does not move the blockchain.** Keep your existing workspace where it is and select it in Section 2A. Do not create a replacement chain just because `lab.py` is in a new folder. `lab.json` stores absolute node paths.

## The commands you asked for

**Run Sections 1 and 2 first to define `$LabFile`, `$MC`, and `$Workspace`.** This table is a command reference, not a block to paste all at once.

| Task | Command | When to use it |
|---|---|---|
| **SETUP** | `python "$LabFile" --workspace "$Workspace" setup --bin-dir "$MC"` | Once, for a deliberately NEW workspace |
| **START** | `python "$LabFile" --workspace "$Workspace" start` | Start or resume the existing five nodes |
| Check readiness | `python "$LabFile" --workspace "$Workspace" doctor` | After setup/start and before tests |
| View status | `python "$LabFile" --workspace "$Workspace" status` | Inspect nodes, miners, streams, and permissions |
| Run application demo | `python "$LabFile" --workspace "$Workspace" demo` | Test the three classroom decision cases |
| Run security tests | `python "$LabFile" --workspace "$Workspace" security-tests` | Test enrollment and access controls; temporarily changes permissions |
| Run 10 requests | `python "$LabFile" --workspace "$Workspace" benchmark --n 10 --workers 2 --timeout 300` | Smoke test before larger loads |
| Run 1,000 requests | `python "$LabFile" --workspace "$Workspace" benchmark --n 1000 --workers 10 --timeout 300` | Ledger burst test |
| Save evidence page | `python "$LabFile" --workspace "$Workspace" capture` | After your actual executions |
| **STOP** | `python "$LabFile" --workspace "$Workspace" stop` | Shut down the five nodes without deleting data |
| Resume unfinished setup | `python "$LabFile" --workspace "$Workspace" repair --bin-dir "$MC"` | Only when setup was incomplete or the binary path needs updating |

**Normal route:** initialize PowerShell -> select workspace -> setup OR start -> doctor -> demo -> security tests -> small benchmark -> large benchmark -> save evidence -> stop.

**Do not execute every optional experiment in this document together.** Read the heading and expected effect before running a command.

## Contents

**Basic: get the project running**

1. [Initialize a PowerShell session](#session)
2. [Choose existing data or a new workspace](#workspace)
3. [First-time SETUP](#setup)
4. [START, status, and readiness](#start)
5. [STOP and restart after a reboot](#stop)
6. [PowerShell basics and prerequisites](#basics)
7. [Unit tests and the automatic demo](#tests)

**Intermediate: understand and operate the application**

8. [Train and query the teaching model](#model)
9. [Manual article workflow](#article)
10. [Security, revocation, and content verification](#security-tests)
11. [Inspect streams, membership, assets, and reputation](#inspect)
12. [Use the native MultiChain CLI correctly](#native)
13. [Ledger benchmarks: 10, 100, and 1,000 requests](#ledger-load)

**Advanced: experiments, evidence, and submission**

14. [Full article-pipeline benchmark](#pipeline-load)
15. [Interpret metrics and reconcile records](#metrics)
16. [Compare concurrency, payloads, and confirmations](#compare)
17. [One-node outage and recovery](#outage)
18. [Separate blockchain-parameter experiment](#parameters)
19. [Evidence collection, export, and screenshots](#evidence)
20. [Publish to GitHub](#github)
21. [Backups, moved folders, and diagnostics](#recovery)
22. [Troubleshooting](#troubleshooting)
23. [Complete application command reference](#commands)
24. [Scope, authorship, and references](#scope)

---

<a id="session"></a>
## 1. Initialize a PowerShell session

**Do this every time you open a new PowerShell window.** Paste this entire block directly into the window, without adding an outer `& { ... }` block. Later sections need these variables to remain available in the same session. PowerShell session/scope rules are described in [R2](#references).

This block checks paths and reads a previously selected workspace path, when one has been saved. It does not create a blockchain, start a node, or grant permission.

```powershell
$ErrorActionPreference = "Stop"

$Project = "C:\inetpub\wwwroot\XauZit\Practice\FakeMedia-MultiChain"
$MC = "C:\Users\BK-PC\Downloads\Programs\multichain-windows-2.3.3"
$LabFile = Join-Path $Project "lab.py"

# Private local files belong outside the repository and web root.
$PrivateRoot = Join-Path $env:LOCALAPPDATA "FakeMedia-MultiChain"
$WorkspaceChoiceFile = Join-Path $PrivateRoot "workspace-path.txt"
$Workspace = Join-Path $PrivateRoot "workspace"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

# Reuse the workspace selected in an earlier session.
if (Test-Path -LiteralPath $WorkspaceChoiceFile -PathType Leaf) {
    $Workspace = (Get-Content -LiteralPath $WorkspaceChoiceFile -Raw -Encoding UTF8).Trim()
    if ([string]::IsNullOrWhiteSpace($Workspace)) {
        throw "The saved workspace path is empty. Select a workspace in Section 2."
    }
}

foreach ($RequiredFile in @(
    $LabFile,
    (Join-Path $Project "demo_news.csv"),
    (Join-Path $MC "multichaind.exe"),
    (Join-Path $MC "multichain-cli.exe"),
    (Join-Path $MC "multichain-util.exe")
)) {
    if (-not (Test-Path -LiteralPath $RequiredFile -PathType Leaf)) {
        throw "Required file not found: $RequiredFile. Check your extracted folder."
    }
}

Set-Location -LiteralPath $Project
New-Item -ItemType Directory -Path $PrivateRoot -Force | Out-Null
$ConfigFile = Join-Path $Workspace "lab.json"

Write-Host "Source folder: $Project"
Write-Host "MultiChain folder: $MC"
Write-Host "Selected workspace: $Workspace"
Write-Host "Workspace config exists: $(Test-Path -LiteralPath $ConfigFile)"

python --version
if ($LASTEXITCODE -ne 0) { throw "Python did not run. Check your Python installation." }

python "$LabFile" --version
if ($LASTEXITCODE -ne 0) { throw "lab.py did not run. Check Python and the source files." }
```

The application should print `2.0.2-mining-check`. A different version needs comparison with its own `--help`; this guide does not assume that unknown revisions have identical options.

The small `workspace-path.txt` file contains only the selected path. It is not a wallet or replacement for `lab.json`. Sections 2A and 3 save it so that future sessions can find the same chain.

<a id="workspace"></a>
## 2. Choose existing data or a new workspace

### 2A. Existing working chain: recommended when only the source folder moved

Your earlier successful run used the course-project workspace below. The NEW source folder can use that OLD private workspace without copying the wallets.

Run this after Section 1 when that existing folder is still present. Paste it directly into the same window, again without an outer `& { ... }` block:

```powershell
# Stop early if Section 1 was skipped or wrapped in & { ... }.
if (-not $LabFile -or -not $WorkspaceChoiceFile -or -not $Utf8NoBom) {
    throw "Section 1 variables are missing. Rerun Section 1 in this window without an outer & { ... } block."
}

$Workspace = "C:\Users\BK-PC\Documents\Study Material\FAST - NUCES\Semester 3\Applications of Blockchain\Mid Term\FakeMedia_MultiChain_Exam_Kit\FakeMedia_Exam_Kit\workspace"
$ConfigFile = Join-Path $Workspace "lab.json"

if (-not (Test-Path -LiteralPath $ConfigFile -PathType Leaf)) {
    throw "Existing lab.json was not found. Locate the real workspace before continuing."
}

# Check the saved paths without displaying credentials.
$Config = Get-Content -LiteralPath $ConfigFile -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($Role in @("authority", "publisher", "validator1", "validator2", "auditor")) {
    $Node = $Config.nodes.$Role
    if ([string]::IsNullOrWhiteSpace([string]$Node.datadir) -or
        [string]::IsNullOrWhiteSpace([string]$Node.conf)) {
        throw "Saved node paths are missing for $Role. Do not create a replacement chain."
    }
    if (-not (Test-Path -LiteralPath $Node.datadir -PathType Container)) {
        throw "Saved data directory missing for $Role. See Section 21 before continuing."
    }
    if (-not (Test-Path -LiteralPath $Node.conf -PathType Leaf)) {
        throw "Saved configuration missing for $Role. See Section 21 before continuing."
    }
}

[System.IO.File]::WriteAllText($WorkspaceChoiceFile, $Workspace, $Utf8NoBom)
Write-Host "Existing workspace selected: $Workspace"
```

**Then skip Section 3 and go to Section 4: START.** The old source-code folder need not be your working directory; only the original data/configuration paths must remain accessible.

To reuse a different existing workspace, replace only the `$Workspace = ...` line above with the directory containing its `lab.json`. Do not select a node's `fakenews` directory in place of the workspace root.

### 2B. A genuinely new lab

Choose this only when you intentionally want a new chain with new wallets and a new history. This does not restore your old evidence.

```powershell
$Workspace = Join-Path $PrivateRoot "workspace"
$ConfigFile = Join-Path $Workspace "lab.json"
Write-Host "New-lab candidate: $Workspace"
Test-Path -LiteralPath $ConfigFile
```

- `True`: this workspace already has configuration; use START or REPAIR, not SETUP.
- `False`: no configuration was found there. Verify that you are not looking in the wrong location before creating a new chain.

If the old lab is still running, a new lab cannot reuse its listening ports. Stop the old lab using its original workspace first, or deliberately use a separate experiment with separate ports. Do not force-kill all `multichaind` processes.

### 2C. A workspace copied into the new source folder

A copy at `C:\inetpub\wwwroot\XauZit\Practice\FakeMedia-MultiChain\workspace` is not automatically portable. Its `lab.json` may still point to the old `datadir` and `conf` locations. A successful command might therefore still be using the old files.

Do not treat the copied folder as a backup you can delete until you understand those references. Do not serve it over IIS. See Section 21; preserving the original workspace is the simplest supported route.

<a id="setup"></a>
## 3. First-time SETUP: create the five-node lab

**Prerequisite:** Section 1 initialized the session and Section 2B selected a deliberately new private workspace. Run this once, not every time you open PowerShell.

```powershell
# Stop early if Section 1 was skipped or wrapped in & { ... }.
if (-not $LabFile -or -not $WorkspaceChoiceFile -or -not $Utf8NoBom) {
    throw "Section 1 variables are missing. Rerun Section 1 in this window without an outer & { ... } block."
}

if (Test-Path -LiteralPath (Join-Path $Workspace "lab.json")) {
    throw "This workspace is already configured. Use start or repair, not setup."
}

python "$LabFile" --workspace "$Workspace" setup --bin-dir "$MC" --chain fakenews --rpc-base 8441 --p2p-base 7441 --block-time 2 --block-size 8388608 --diversity 0.6

if ($LASTEXITCODE -ne 0) {
    throw "Setup did not complete. Read the error and Section 22. Do not delete wallets."
}

[System.IO.File]::WriteAllText($WorkspaceChoiceFile, $Workspace, $Utf8NoBom)
Write-Host "Setup completed. Workspace selection saved for later sessions."
```

The shorter command uses exactly those defaults:

```powershell
# Alternative to the command above, NOT an additional setup to run afterwards.
python "$LabFile" --workspace "$Workspace" setup --bin-dir "$MC"
```

### What SETUP does in this implementation

| Stage | Work performed by `lab.py` |
|---|---|
| Network | Create the authority chain, configure five private node directories, join nodes, grant connection/transaction permissions, and verify identities |
| Mining permissions | Authorize validator1 and validator2 to mine; the authority already has initial privileges |
| Streams | Create seven write-restricted application streams and subscribe the five nodes |
| Signed registration | Record enrollment with a challenge signature and role/address binding |
| Application permissions | Grant each normal writer only its assigned stream permissions |
| Asset | Issue a fixed 1,000-unit `NewsCredit` demonstration asset |
| Teaching model | Train the included small classroom model if missing |
| Validation | Check node readiness, subscriptions, permissions, and a shared block hash |

The setup command already starts the nodes. A separate START is unnecessary immediately afterwards, although START is safe for already-running, correctly identified nodes.

**Expected successful fields:**

```json
{
  "setup_complete": true,
  "all_passed": true,
  "issues": []
}
```

These are expected fields, not a promised result or a benchmark measurement.

### Port conflict during intentionally new setup

First identify whether your existing lab is already using the ports. Do not create another lab merely to hide a wrong-workspace problem.

For an intentionally separate new lab, `--auto-ports` searches for unused ranges:

```powershell
python "$LabFile" --workspace "$Workspace" setup --bin-dir "$MC" --auto-ports
```

Use this only if no `lab.json` was created by the failed attempt. Record the actual assigned ports from the output; do not keep assuming 8441/7441 afterwards.

### Resume interrupted or incomplete setup

When `lab.json` exists but setup is incomplete:

```powershell
python "$LabFile" --workspace "$Workspace" repair --bin-dir "$MC"
if ($LASTEXITCODE -ne 0) { throw "Repair failed. Inspect the reported stage and node logs." }

python "$LabFile" --workspace "$Workspace" doctor
if ($LASTEXITCODE -ne 0) { throw "The lab is not ready yet." }

[System.IO.File]::WriteAllText($WorkspaceChoiceFile, $Workspace, $Utf8NoBom)
```

Repair reuses the saved wallets and parameters. On a completed lab it does not automatically undo deliberate revocations or reissue assets. It can update `bin_dir`; it does not relocate saved node data paths.

<a id="start"></a>
## 4. START, status, and readiness

**Prerequisite:** Section 1, plus an existing selected workspace. This is your normal daily starting point after the first setup.

```powershell
# Stop early if Section 1 was skipped or wrapped in & { ... }.
if (-not $LabFile -or -not $WorkspaceChoiceFile -or -not $Utf8NoBom) {
    throw "Section 1 variables are missing. Rerun Section 1 in this window without an outer & { ... } block."
}

if (-not (Test-Path -LiteralPath (Join-Path $Workspace "lab.json"))) {
    throw "No lab.json at the selected workspace. Recheck Section 2."
}

python "$LabFile" --workspace "$Workspace" start
if ($LASTEXITCODE -ne 0) { throw "Start failed. Stop here and inspect the error." }

python "$LabFile" --workspace "$Workspace" doctor
if ($LASTEXITCODE -ne 0) { throw "Readiness failed. Do not benchmark yet." }
```

View detailed status separately:

```powershell
python "$LabFile" --workspace "$Workspace" status
```

A successful `doctor` result should report all five nodes online, no required stream/permission issues, and `all_passed: true`. Nodes queried sequentially can report slightly different current heights while blocks are advancing. Inspect `shared_height_check.same_hash` and the reported issues rather than only comparing the printed heights.

`start` checks a responding node's chain name, wallet ownership, and saved genesis before reusing the RPC endpoint. It starts missing nodes instead of creating another chain.

### Start one node

```powershell
python "$LabFile" --workspace "$Workspace" start --role validator2
```

Allowed roles: `authority`, `publisher`, `validator1`, `validator2`, `auditor`. A single-node restart is useful during a controlled experiment; it does not replace starting the whole lab when other nodes are offline.

<a id="stop"></a>
## 5. STOP and restart after a reboot

### Stop the whole lab safely

Wait for any current application write or benchmark command to finish first.

```powershell
python "$LabFile" --workspace "$Workspace" stop
if ($LASTEXITCODE -ne 0) { throw "Some nodes did not shut down cleanly. Inspect the output." }
```

Expected result: `all_passed: true`, with `ports_closed: true` for all five roles. Already-stopped nodes may report `already_stopped`. Wallets and chain files are retained.

### Stop just one node

```powershell
python "$LabFile" --workspace "$Workspace" stop --role validator2
```

Do not leave a deliberately stopped node offline before an ordinary demo or benchmark.

### Tomorrow, after a reboot, or after closing PowerShell

Run Section 1 again to restore session variables and read the saved workspace selection. Then:

```powershell
python "$LabFile" --workspace "$Workspace" start
if ($LASTEXITCODE -ne 0) { throw "Start failed." }
python "$LabFile" --workspace "$Workspace" doctor
if ($LASTEXITCODE -ne 0) { throw "Readiness failed." }
```

Do not run SETUP again. Closing the terminal is not the lab's shutdown procedure; use STOP before a planned shutdown or backup.

---

<a id="basics"></a>
## 6. PowerShell basics and prerequisites

### What you need

Use Windows PowerShell 5.1 or PowerShell 7, Python 3.10 or newer, and the supplied MultiChain Community 2.3.3 binaries. Git is needed only for repository publishing. The source and tests use the Python standard library; `requirements.txt` intentionally lists no third-party runtime dependencies. Do not install a similarly named pip package as a substitute for the MultiChain executables.

Check:

```powershell
$PSVersionTable.PSVersion
python --version
Get-Command python
Test-Path -LiteralPath "$MC\multichaind.exe"
Test-Path -LiteralPath "$MC\multichain-cli.exe"
Test-Path -LiteralPath "$MC\multichain-util.exe"
```

The three path checks should return `True`. The README does not require changing the global execution policy, opening firewall ports, or granting broad filesystem permissions.

### Learn these PowerShell commands

| Command | Meaning |
|---|---|
| `Get-Location` | Show the current folder |
| `Set-Location -LiteralPath $Project` | Change to the project folder; `cd` is a common alias |
| `Get-ChildItem -LiteralPath $Project` | List files; `dir` is a common alias |
| `Test-Path -LiteralPath $LabFile` | Check whether a file or folder exists |
| `$Name = "value"` | Store a value in a session variable |
| `Join-Path $Project "lab.py"` | Build a path |
| `& "$MC\multichain-cli.exe"` | Execute a program at a quoted path |
| `$LASTEXITCODE` | Exit code from the most recent native executable |
| `ConvertFrom-Json` | Convert JSON text into a PowerShell object |
| `Select-Object` | Display selected properties |
| `Start-Sleep -Seconds 5` | Pause a script |

Only paste the command lines, never the `PS C:\...>` prompt or the `>>` continuation markers. Use normal straight quotes. To run an executable in the current folder, prefix its filename with `.\`; to run a quoted full executable path, put `&` before the path. See [R1](#references) and [R3](#references).

```powershell
# Example syntax only; help does not start a blockchain.
& "$MC\multichain-cli.exe" -?
```

For a binary in the current directory, the syntax is `.\multichain-cli.exe`. For `lab.py`, invoke the Python interpreter as the examples show.

**`$ErrorActionPreference = "Stop"` does not by itself turn every native program failure into a stopping error in Windows PowerShell 5.1.** Check `$LASTEXITCODE` immediately after Python/Git/CLI calls. Also inspect result fields: `inspect` can return `audit_pass: false` and `verify-file` can return `match: false` with process exit code zero.

### Get built-in application help

```powershell
python "$LabFile" --help
python "$LabFile" setup --help
python "$LabFile" benchmark --help
python "$LabFile" rpc --help
```

The general syntax is:

```text
python <lab.py> --workspace <workspace-root> <command> [command-options]
```

`--workspace` must be BEFORE the subcommand. Putting it after `benchmark`, for example, is not supported by this parser.

<a id="tests"></a>
## 7. Unit tests and the automatic demo

### 7A. Unit tests: no live blockchain required

From the repository root:

```powershell
Set-Location -LiteralPath $Project
python -m unittest -v test_lab test_recovery test_mining_permissions test_submission_tools
if ($LASTEXITCODE -ne 0) { throw "Unit tests failed. Read the failed test before continuing." }
```

The supplied submission package contains 99 tests across those four modules. A result ending in `OK` shows that those local tests passed; it does not prove that your live MultiChain deployment works.

### 7B. Automatic end-to-end classroom demo: writes to the chain

Start the five nodes and pass `doctor` first:

```powershell
python "$LabFile" --workspace "$Workspace" demo
if ($LASTEXITCODE -ne 0) { throw "Demo failed. Do not move on to load testing yet." }
```

| Case | Reviewer votes | Expected decision |
|---|---|---|
| real | REAL + REAL | REAL |
| fake | FAKE + FAKE | FAKE |
| disagreement | REAL + FAKE | REVIEW |

Expected: each case has `audit_pass: true`; the overall output has `all_passed: true`. The demo creates unique IDs on every run, so rerunning creates additional history, not replacements.

Results are stored under `$Workspace\evidence\demo.json` and per-article JSON files. Votes use classroom fixture labels. The demo tests publication, review, decision, and auditing, not independent fact-checking accuracy.

---

<a id="model"></a>
## 8. Train and query the teaching model

Setup already trains the model when it is missing. Retraining is optional and changes the saved model file and its hash, so record the training parameters when comparing runs.

```powershell
python "$LabFile" --workspace "$Workspace" train --dataset "$Project\demo_news.csv" --epochs 250 --seed 42
if ($LASTEXITCODE -ne 0) { throw "Training failed." }

python "$LabFile" --workspace "$Workspace" nlp --text "The library published its opening hours on the official noticeboard." --threshold 0.35
```

`train` and `nlp` operate on local data/model files. `analyze --id ...` is different: it reads an existing article and publishes a prediction transaction to `predictions`.

This implementation uses lexical-count states, TF-IDF evidence, and terminal tabular Q-learning. It is not the paper's deep reinforcement-learning implementation. A threshold or model prediction does not directly choose the final two-reviewer decision, and the small fixture evaluation is not evidence of general real-world accuracy.

<a id="article"></a>
## 9. Manual article workflow: submit -> analyze -> vote -> finalize -> inspect

**Prerequisite:** all five nodes ready; publisher and validators not revoked. Use a NEW article ID for each experiment. Do not paste only the last command before defining `$NewsId`.

### Step 1: publish one article

```powershell
$NewsId = "manual-" + [guid]::NewGuid().ToString("N").Substring(0, 12)
$Text = "The campus library will open at 9 AM according to the published notice."
Write-Host "Keep this article ID: $NewsId"

python "$LabFile" --workspace "$Workspace" submit --id "$NewsId" --text "$Text"
if ($LASTEXITCODE -ne 0) { throw "Article submission failed. Check the ledger before retrying." }
```

Expected fields include `news_id`, `txid`, and `content_sha256`. `submit` waits for an auditor-observed confirmation before returning normally.

### Step 2: publish the teaching-model prediction

```powershell
python "$LabFile" --workspace "$Workspace" analyze --id "$NewsId" --threshold 0.35
if ($LASTEXITCODE -ne 0) { throw "Analysis failed." }
```

The prediction contains an article reference and `model_sha256`. It may be REAL, FAKE, or REVIEW; do not hardcode the expected model label for arbitrary text.

### Step 3: reviewer 1 votes

```powershell
python "$LabFile" --workspace "$Workspace" vote --role validator1 --id "$NewsId" --label REAL --reason "Classroom scenario: reviewer 1 accepts the supplied example."
if ($LASTEXITCODE -ne 0) { throw "Validator 1 vote failed." }
```

### Step 4: reviewer 2 votes

```powershell
python "$LabFile" --workspace "$Workspace" vote --role validator2 --id "$NewsId" --label REAL --reason "Classroom scenario: reviewer 2 accepts the supplied example."
if ($LASTEXITCODE -ne 0) { throw "Validator 2 vote failed." }
```

These are demonstration judgments, not claims that the sample article was independently verified.

### Step 5: finalize once

```powershell
python "$LabFile" --workspace "$Workspace" finalize --id "$NewsId"
if ($LASTEXITCODE -ne 0) { throw "Finalization failed." }
```

For the two matching REAL votes, the application should produce `label: REAL`. Do not finalize prematurely and expect the old decision to be overwritten after adding more votes. Already-finalized IDs are rejected.

### Step 6: inspect the evidence and assert the audit result

```powershell
$AuditLines = python "$LabFile" --workspace "$Workspace" inspect --id "$NewsId"
if ($LASTEXITCODE -ne 0) { throw "The inspection command failed." }
$Audit = ($AuditLines -join [Environment]::NewLine) | ConvertFrom-Json
$Audit | ConvertTo-Json -Depth 30
if (-not $Audit.audit_pass) { throw "Inspection returned audit_pass=false. Read audit_error and the evidence." }
```

An audit checks referenced signed records, content binding, and confirmations. It does not establish real-world truth or reconstruct all historical permission changes.

### More classroom cases

For a fresh article ID, vote FAKE twice to test a FAKE decision. Vote REAL and FAKE to test REVIEW. Missing, duplicate, invalid, or unconfirmed votes can also lead to REVIEW in the decision policy. A validator currently revoked from `votes.write` prevents normal finalization.

The Python gateway rejects duplicate article IDs and repeat votes. Stream keys are not natively unique; bypassing the gateway requires separate validation. The two-reviewer policy is not the blockchain's mining consensus and is not a native 2-of-2 spending multisignature.

<a id="security-tests"></a>
## 10. Security tests, revocation, and content verification

### 10A. Automated security suite

This is a MUTATING test. It signs challenges, deliberately attempts unauthorized writes, temporarily revokes/restores publisher stream access, submits an integrity-test article, and records results. Do not run concurrent work against the same workspace.

```powershell
python "$LabFile" --workspace "$Workspace" security-tests
if ($LASTEXITCODE -ne 0) { throw "Security tests failed. Inspect the individual checks." }
```

Look for `all_passed: true` and each check's `passed` field. A permission-denied error recorded inside a negative test can be the intended result. A connection failure is not evidence that authorization enforcement worked.

### 10B. Manually revoke and restore the publisher

Run this as ONE block. Its `finally` section attempts restoration even if the demonstration fails. Do not interrupt it during the permission changes.

```powershell
python "$LabFile" --workspace "$Workspace" revoke --role publisher
if ($LASTEXITCODE -ne 0) { throw "Revocation failed; inspect before continuing." }

try {
    $BlockedId = "revoked-" + [guid]::NewGuid().ToString("N").Substring(0, 12)
    python "$LabFile" --workspace "$Workspace" submit --id "$BlockedId" --text "This write should be denied."
    $DeniedExit = $LASTEXITCODE
    if ($DeniedExit -eq 0) { throw "Unexpected successful write. Inspect the permissions." }
    Write-Host "Nonzero exit observed. Confirm the message is permission-related, not a transport failure."
}
finally {
    python "$LabFile" --workspace "$Workspace" restore --role publisher
    if ($LASTEXITCODE -ne 0) { throw "Restoration failed. Restore publisher explicitly before other work." }
}

python "$LabFile" --workspace "$Workspace" doctor
if ($LASTEXITCODE -ne 0) { throw "Readiness did not recover after restoration." }
```

For this code, publisher revocation affects `news.write` and `benchmarks.write`. Validator revocation affects `votes.write`; it does not revoke mining, disconnect the node, or remove validator1's prediction-writing role. A stored enrollment record is not the same thing as current permission.

### 10C. Verify an exact local text file, then detect modification

Files below are created in the private directory, not the web-root repository. UTF-8 without a BOM and exact bytes matter: changing a newline also changes the hash.

```powershell
$FileNewsId = "file-" + [guid]::NewGuid().ToString("N").Substring(0, 12)
$OriginalText = "Classroom integrity example: the meeting starts at 10 AM."
$OriginalFile = Join-Path $PrivateRoot ($FileNewsId + "-original.txt")
$ChangedFile = Join-Path $PrivateRoot ($FileNewsId + "-modified.txt")
[System.IO.File]::WriteAllText($OriginalFile, $OriginalText, $Utf8NoBom)
[System.IO.File]::WriteAllText($ChangedFile, ($OriginalText + " Changed."), $Utf8NoBom)

python "$LabFile" --workspace "$Workspace" submit --id "$FileNewsId" --text "$OriginalText"
if ($LASTEXITCODE -ne 0) { throw "Integrity article submission failed." }

$GoodLines = python "$LabFile" --workspace "$Workspace" verify-file --id "$FileNewsId" --file "$OriginalFile"
if ($LASTEXITCODE -ne 0) { throw "Original-file verification command failed." }
$Good = ($GoodLines -join [Environment]::NewLine) | ConvertFrom-Json
$Good | ConvertTo-Json
if (-not $Good.match) { throw "Original bytes did not match." }

$ChangedLines = python "$LabFile" --workspace "$Workspace" verify-file --id "$FileNewsId" --file "$ChangedFile"
if ($LASTEXITCODE -ne 0) { throw "Modified-file verification command failed." }
$Changed = ($ChangedLines -join [Environment]::NewLine) | ConvertFrom-Json
$Changed | ConvertTo-Json
if ($Changed.match) { throw "Unexpected match for modified bytes." }
```

Expected: original `match: true`, modified `match: false`. The test modifies a local copy; it does not rewrite a historical block. `verify-file` reports mismatch in JSON even when process exit is zero.

<a id="inspect"></a>
## 11. Inspect streams, membership, assets, and reputation

### 11A. Read node information with the application's RPC wrapper

```powershell
python "$LabFile" --workspace "$Workspace" rpc --role authority getinfo
python "$LabFile" --workspace "$Workspace" rpc --role authority getpeerinfo
python "$LabFile" --workspace "$Workspace" rpc --role authority liststreams
python "$LabFile" --workspace "$Workspace" rpc --role authority listpermissions
python "$LabFile" --workspace "$Workspace" rpc --role authority listminers --params "[true]"
python "$LabFile" --workspace "$Workspace" rpc --role auditor getblockchaininfo
python "$LabFile" --workspace "$Workspace" rpc --role authority listassets
```

`rpc` uses the selected workspace's saved configuration. It is an operator-level interface, not a restricted end-user API. Only invoke methods you understand.

### 11B. Read JSON parameters from a file to avoid Windows quoting problems

For parameters containing strings/objects, `--params-file` avoids passing embedded JSON quotes through the native command line. The parameter file must contain a JSON ARRAY.

Example: read the first 20 registry items:

```powershell
$ParamsFile = Join-Path $PrivateRoot "rpc-parameters.json"
[System.IO.File]::WriteAllText($ParamsFile, '["registry", false, 20, 0]', $Utf8NoBom)
python "$LabFile" --workspace "$Workspace" rpc --role auditor liststreamitems --params-file "$ParamsFile"
if ($LASTEXITCODE -ne 0) { throw "Registry query failed." }
```

A second example: detailed information about the `news` stream:

```powershell
[System.IO.File]::WriteAllText($ParamsFile, '["news", true]', $Utf8NoBom)
python "$LabFile" --workspace "$Workspace" rpc --role auditor getstreaminfo --params-file "$ParamsFile"
```

Inspect `publishers`, `confirmations`, and `data.json`, not just a label embedded in the data. Increasing `start` and repeating the query reads additional pages; 20 returned items are not necessarily the entire stream.

### 11C. Roles and streams implemented by this package

| Role | Normal responsibility | Mining permission | Default RPC / P2P |
|---|---|---|---|
| authority | Enrollment, administration, final decisions, audit | Yes | 8441 / 7441 |
| publisher | Article submissions and ledger load | No | 8442 / 7442 |
| validator1 | Teaching predictions and first review | Yes | 8443 / 7443 |
| validator2 | Second review | Yes | 8444 / 7444 |
| auditor | Read and inspect recorded evidence | No | 8445 / 7445 |

| Application stream | Normal writer | Data |
|---|---|---|
| registry | authority | Enrollment/challenge evidence |
| news | publisher | Text, article ID, publisher address, content hash |
| predictions | validator1 | Prediction, model hash, and article reference |
| votes | validator1, validator2 | Review and article/hash binding |
| decisions | authority | Final policy outcome and vote references |
| audit | authority | Security and permission events; load-test summary metadata |
| benchmarks | publisher | Ledger burst-test records |

The authority retains administrative privileges beyond the normal writer assignments. Seven application streams plus the default `root` stream can appear as eight total streams. Write restriction is not encryption or read confidentiality.

### 11D. Mining permission versus a miner waiting its turn

`listminers` reports `permitted` separately from `diversitywaitblocks`. An authorized miner can be waiting to mine; do not remove mining diversity just to make a waiting status disappear. The corrected checker uses `listminers.permitted` for authorization. See [R6](#references).

### 11E. Asset demonstration and reputation

```powershell
[System.IO.File]::WriteAllText($ParamsFile, '["NewsCredit", true]', $Utf8NoBom)
python "$LabFile" --workspace "$Workspace" rpc --role authority getassetinfo --params-file "$ParamsFile"

# This creates a real asset transfer on the private classroom chain.
python "$LabFile" --workspace "$Workspace" reward --amount 1
if ($LASTEXITCODE -ne 0) { throw "Reward transfer did not complete. Inspect before retrying." }

python "$LabFile" --workspace "$Workspace" reputation
```

`NewsCredit` is a fixed 1,000-unit classroom token. Each successful reward call transfers additional units; it is not a read-only query. It is not the native mining reward and is not a reputation score.

The separate teaching reputation formula is `clip(50 + 5*REAL - 10*FAKE, 0, 100)` over confirmed authority-issued decisions. It is descriptive and does not dynamically alter mining or publishing permissions.

<a id="native"></a>
## 12. Native MultiChain CLI: the correct data directory every time

### 12A. Read the authority configuration safely

After Section 1 and workspace selection, run this complete block. It queries your existing node; it does not join a new one.

```powershell
$ConfigFile = Join-Path $Workspace "lab.json"
if (-not (Test-Path -LiteralPath $ConfigFile)) { throw "Selected lab.json is missing." }
$Config = Get-Content -LiteralPath $ConfigFile -Raw -Encoding UTF8 | ConvertFrom-Json
$Authority = $Config.nodes.authority

if ([string]::IsNullOrWhiteSpace([string]$Config.chain) -or
    [string]::IsNullOrWhiteSpace([string]$Authority.datadir) -or
    [int]$Authority.rpc_port -lt 1) {
    throw "Required authority fields are missing. Do not send an incomplete CLI command."
}

$CliFile = Join-Path $MC "multichain-cli.exe"
$CliArguments = @(
    [string]$Config.chain
    "-datadir=$($Authority.datadir)"
    "-rpcconnect=127.0.0.1"
    "-rpcport=$($Authority.rpc_port)"
    "-requestout=null"
)

& "$CliFile" @CliArguments getinfo
if ($LASTEXITCODE -ne 0) { throw "Authority getinfo failed. Check whether the lab is started." }
& "$CliFile" @CliArguments getpeerinfo
if ($LASTEXITCODE -ne 0) { throw "Authority getpeerinfo failed." }
```

Then, in the SAME session:

```powershell
& "$CliFile" @CliArguments liststreams
& "$CliFile" @CliArguments listminers true
& "$CliFile" @CliArguments listassets
& "$CliFile" @CliArguments getblockcount
& "$CliFile" @CliArguments listpermissions
& "$CliFile" @CliArguments liststreamitems news false 10 0
& "$CliFile" @CliArguments getassetinfo NewsCredit true
```

To read a transaction, use an ACTUAL txid from your current run:

```powershell
$Txid = (Read-Host "Paste a transaction ID from this workspace").Trim()
if ($Txid -notmatch '^[0-9a-fA-F]{64}$') { throw "A transaction ID should be 64 hexadecimal characters." }
& "$CliFile" @CliArguments getrawtransaction "$Txid" 1
```

### 12B. Why the earlier bare commands failed

| Incorrect approach | Why it fails or selects the wrong node | Correct approach |
|---|---|---|
| `multichaind fakenews -daemon` | Executable may not be on PATH; no saved data directory selected | Use `lab.py ... start` |
| `.\multichaind.exe fakenews -daemon` | Uses default MultiChain data location without `-datadir` | Use saved node data directory |
| `fakenews@8441` | The value after `@` is interpreted as a host, not a port-only specification | A seed uses `chain@host:P2P-port` |
| Use RPC 8441 as a seed | RPC and peer-to-peer services are different | Default authority P2P is 7441 |
| Print/use `$Config` before reading `$ConfigFile` | Variables may be null in a new session | Run Section 1 and this section's complete block |

The correctly formed default seed is `fakenews@127.0.0.1:7441`, but it is for joining another node, not restarting your configured five-node lab. A manual join without the intended data directory can create an extra wallet and ask for enrollment. Leave that extra node unused; do not grant it unnecessary permissions. See [R5](#references) and [R7](#references).

---

<a id="ledger-load"></a>
## 13. Ledger benchmarks: 10 -> 100 -> 1,000 requests

**Prerequisite:** `doctor`, `demo`, and security checks passed. One benchmark at a time. These commands publish records, so the ledger grows.

### 13A. Ten-request smoke test

```powershell
python "$LabFile" --workspace "$Workspace" benchmark --mode ledger --n 10 --workers 2 --payload-bytes 1024 --confirmations 1 --timeout 300
if ($LASTEXITCODE -ne 0) { throw "10-request test did not fully pass. Do not increase load yet." }
```

Expected for a fully successful run: requested=10, successes=10, failures=0, unknown_outcomes=0, confirmed_known_transactions=10, confirmed_complete_requests=10.

### 13B. One hundred requests

```powershell
python "$LabFile" --workspace "$Workspace" benchmark --mode ledger --n 100 --workers 5 --payload-bytes 1024 --confirmations 1 --timeout 300
if ($LASTEXITCODE -ne 0) { throw "100-request test did not fully pass." }
```

### 13C. One thousand requests

```powershell
python "$LabFile" --workspace "$Workspace" benchmark --mode ledger --n 1000 --workers 10 --payload-bytes 1024 --confirmations 1 --timeout 300
if ($LASTEXITCODE -ne 0) { throw "1000-request test did not fully pass. Inspect the saved result." }
```

| Option | Meaning in this implementation |
|---|---|
| `--mode ledger` | Publish directly to `benchmarks`; one measured transaction per successful request |
| `--n 1000` | Create 1,000 logical requests |
| `--workers 10` | At most ten concurrent request workers |
| `--payload-bytes 1024` | 1,024 bytes of generated content; JSON and transaction overhead are additional |
| `--confirmations 1` | Required confirmations observed by the auditor |
| `--timeout 300` | Confirmation-polling budget AFTER submission finishes; not a total runtime limit |

This is a bounded-concurrency burst: requests have logical arrival time t0 and wait for an available worker. It is not 1,000 nodes, 1,000 simultaneous sockets, or a guarantee of 1,000 transactions per second. There is no `--tps` rate-setting option in this version.

<a id="pipeline-load"></a>
## 14. Full article-pipeline benchmark

This exercises article submission, prediction, two fixture votes, and finalization. It requires the trained model and explicit `--fixture-votes` because reviewer judgments come from classroom labels.

Start small:

```powershell
python "$LabFile" --workspace "$Workspace" benchmark --mode pipeline --n 10 --workers 2 --fixture-votes --confirmations 1 --timeout 600
if ($LASTEXITCODE -ne 0) { throw "Small pipeline test failed. Stop here." }
```

Only after the small run passes, run the larger experiment:

```powershell
python "$LabFile" --workspace "$Workspace" benchmark --mode pipeline --n 1000 --workers 10 --fixture-votes --confirmations 1 --timeout 600
if ($LASTEXITCODE -ne 0) { throw "Pipeline benchmark did not fully pass. Read the saved evidence." }
```

For 1,000 fully successful requests, this workload creates **5,000 measured transactions**, plus separate audit-summary metadata excluded from the measured workload. It waits for prerequisite article/vote confirmations within the pipeline, so it is a different workload from direct ledger publishing. Do not compare the two rates as though they performed the same operation.

`--payload-bytes` controls generated ledger content, not the pipeline's dataset articles. The pipeline can take substantially longer than a ledger run; the final `--timeout` does not override all internal prerequisite waits and is not a whole-run deadline.

The benchmark checks completed requests and observed confirmations. It does not call `inspect` for every pipeline article. Audit selected completed article IDs separately using Section 9.

<a id="metrics"></a>
## 15. Interpret metrics and reconcile records

### 15A. Select the exact result to discuss

Every benchmark prints a `run_id` and writes:

```text
<workspace>\evidence\<run_id>\
    summary.json
    requests.csv
    requests.jsonl
    summary_anchor.json
```

Use the actual run ID printed by your command, not a guessed date or an example from another person's output:

```powershell
$RunId = (Read-Host "Paste the run_id printed by your benchmark").Trim()
if ($RunId -notmatch '^(ledger|pipeline)-[A-Za-z0-9_.-]+$') { throw "Invalid run_id format." }
$SummaryFile = Join-Path (Join-Path (Join-Path $Workspace "evidence") $RunId) "summary.json"
$Summary = Get-Content -LiteralPath $SummaryFile -Raw -Encoding UTF8 | ConvertFrom-Json

$Summary | Select-Object run_id, mode, requested, successes, failures, unknown_outcomes, confirmed_complete_requests, confirmed_known_transactions, submission_seconds, confirmation_observation_seconds, confirmed_known_transactions_per_second | Format-List
$Summary.service_latency_success_only | Format-List
```

### 15B. Explain the measurements correctly

| Field | What you can say |
|---|---|
| `successes` | Requests which returned successfully from the measured operation |
| `failures` | Requests with an explicit failure |
| `unknown_outcomes` | Requests with an ambiguous write result; not automatically retried |
| `confirmed_known_transactions` | Known txids meeting the observer's confirmation target |
| `confirmed_complete_requests` | Successful requests whose known workload transactions all meet the target |
| `submission_seconds` | Burst start until submission/processing attempts finish; pipeline processing includes prerequisite waits |
| `confirmation_observation_seconds` | Burst start until final post-submission confirmation polling finishes |
| `service_latency_success_only` | Successful request service time, excluding initial queue wait |
| `burst_response_latency_success_only` | Successful request queue wait plus service time |
| `queue_latency_all_requests` | Delay from t0 until each request begins service |
| `p95_ms` | 95th-percentile latency of the specified sample set, not an average |

The observed batch-confirmation interval includes polling overhead. It is not an exact per-transaction block-confirmation latency. If confirmation times out, do not describe the timeout interval as the time needed to confirm the whole batch.

Useful formulas used by the code:

```text
successful requests/second = successes / submission_seconds
confirmed transactions/second = confirmed_known_transactions / confirmation_observation_seconds
success rate = successes / requested
```

Never call a run with 0 successes and 1,000 failures a fast successful benchmark. Preserve failures, timeout information, hardware/topology, payload, worker count, and the confirmation target in the report. If the summary anchor failed, the workload timing may still exist locally; do not claim the anchor was stored.

### 15C. Reconcile by run ID without resending writes

Ledger run:

```powershell
python "$LabFile" --workspace "$Workspace" reconcile --run-id "$RunId" --stream benchmarks
```

Pipeline run, use this alternative:

```powershell
python "$LabFile" --workspace "$Workspace" reconcile --run-id "$RunId" --stream news
```

Look at `confirmed_items`, `distinct_logical_ids`, `duplicate_ids`, and `invalid_records`. This reconciliation uses at least one confirmation; it does not reproduce an arbitrary higher benchmark target. For `news`, it counts submitted articles, not completed five-stage decisions. An empty result with the wrong stream is not evidence that the original operation failed.

Reconciliation reports data; check it explicitly rather than relying only on exit code. Do not resubmit ambiguous writes until you have determined whether the original transaction was recorded.

<a id="compare"></a>
## 16. Compare workers, payload sizes, and confirmation targets

Change ONE setting per experiment, keep the others constant, and record actual results. Repeated runs on a growing chain are not identical clean-start experiments.

### 16A. Different worker counts

```powershell
foreach ($Workers in @(1, 5, 10, 25)) {
    Write-Host "Testing 1000 requests with $Workers workers"
    python "$LabFile" --workspace "$Workspace" benchmark --mode ledger --n 1000 --workers $Workers --payload-bytes 1024 --confirmations 1 --timeout 600
    if ($LASTEXITCODE -ne 0) { throw "Benchmark failed at workers=$Workers. Inspect before continuing." }
}
```

Each loop iteration waits for the previous process to finish. Do not run separate benchmark processes concurrently against the same workspace; the application uses a writer lock.

### 16B. Larger content

```powershell
python "$LabFile" --workspace "$Workspace" benchmark --mode ledger --n 1000 --workers 10 --payload-bytes 8192 --confirmations 1 --timeout 600
```

### 16C. More confirmations

```powershell
python "$LabFile" --workspace "$Workspace" benchmark --mode ledger --n 1000 --workers 10 --payload-bytes 1024 --confirmations 3 --timeout 600
```

For each, verify the exit code and confirmation counts. Do not infer the effect on your machine before measuring it. Record at least three repeats per condition when time permits, and retain all run IDs rather than only the fastest run.

<a id="outage"></a>
## 17. One-node outage and recovery: advanced optional experiment

This intentionally interrupts one validator. Complete the normal tests first. Five processes on one PC do not demonstrate tolerance of a whole-machine failure.

```powershell
python "$LabFile" --workspace "$Workspace" stop --role validator2
if ($LASTEXITCODE -ne 0) { throw "Could not stop validator2 cleanly." }

try {
    python "$LabFile" --workspace "$Workspace" rpc --role auditor getblockcount
    if ($LASTEXITCODE -ne 0) { throw "Auditor query failed." }
    Start-Sleep -Seconds 10
    python "$LabFile" --workspace "$Workspace" rpc --role auditor getblockcount
    if ($LASTEXITCODE -ne 0) { throw "Auditor query failed." }
}
finally {
    python "$LabFile" --workspace "$Workspace" start --role validator2
    if ($LASTEXITCODE -ne 0) { throw "Validator2 restart failed. Recover it before other tests." }
}

python "$LabFile" --workspace "$Workspace" doctor
if ($LASTEXITCODE -ne 0) { throw "Readiness has not recovered." }
```

Compare the observed block counts and then synchronization after restart. A short sample with no new block does not by itself prove permanent failure. Record the miner states and relevant parameters.

The normal benchmark requires all five roles to pass readiness, so do not use it while validator2 is intentionally offline and label its readiness rejection a throughput result. Chain block production and the two-reviewer article policy are different availability questions. Do not stop all miners during a pending write.

<a id="parameters"></a>
## 18. Separate blockchain-parameter experiment

The supplied setup writes parameters at chain creation. Inspect the current parameters without editing the running chain:

```powershell
python "$LabFile" --workspace "$Workspace" rpc --role authority getblockchainparams
```

Important defaults requested by `setup`:

| Parameter | Value | Role |
|---|---|---|
| `target-block-time` | 2 | Block-time target in seconds, not an exact observed duration |
| `maximum-block-size` | 8388608 | Maximum block size in bytes |
| `mining-diversity` | 0.6 | Mining participation/diversity constraint |
| `mining-turnover` | 0 | Lab's turnover setting |
| `mine-empty-rounds` | -1 | Lab empty-block setting |
| `setup-first-blocks` | 10 | Initial setup period |
| `target-adjust-freq` | -1 | Lab difficulty-adjustment setting |
| `root-stream-open` | false | Root stream not open to everyone |
| `anyone-can-connect/send/receive/create/issue/mine/admin` | false | Explicit permissioning |

These are blockchain parameters, distinct from per-node `rpcport`, `port`, and `datadir`. Do not copy over or edit initialized `params.dat` as an experiment. For a controlled parameter comparison, use a separate fresh chain. See [R5](#references) and [R8](#references).

Example: a separate five-second chain, without changing `$Workspace`:

```powershell
$ExperimentWorkspace = Join-Path $PrivateRoot "experiments\news5s"
if (Test-Path -LiteralPath (Join-Path $ExperimentWorkspace "lab.json")) {
    throw "The experiment already exists. Start it explicitly instead of recreating it."
}

python "$LabFile" --workspace "$ExperimentWorkspace" setup --bin-dir "$MC" --chain news5s --rpc-base 8541 --p2p-base 7541 --block-time 5 --diversity 0.6
if ($LASTEXITCODE -ne 0) { throw "Experiment setup failed. Keep its data and inspect the error." }

try {
    python "$LabFile" --workspace "$ExperimentWorkspace" doctor
    if ($LASTEXITCODE -ne 0) { throw "Experiment readiness failed." }
    python "$LabFile" --workspace "$ExperimentWorkspace" benchmark --mode ledger --n 1000 --workers 10 --timeout 600
    if ($LASTEXITCODE -ne 0) { throw "Experiment benchmark failed." }
}
finally {
    python "$LabFile" --workspace "$ExperimentWorkspace" stop
    if ($LASTEXITCODE -ne 0) { throw "Experiment shutdown did not fully pass." }
}
```

The alternative port ranges must also be free. Two simultaneously running chains compete for the same CPU and storage. For a fair comparison, stop the inactive chain and run the experiments separately. The saved normal workspace selection is unchanged by this block.

<a id="evidence"></a>
## 19. Capture evidence, export it, and take screenshots

### 19A. Capture the current workspace's evidence page

After actual tests, while the normal lab is running:

```powershell
python "$LabFile" --workspace "$Workspace" capture
if ($LASTEXITCODE -ne 0) { throw "Evidence capture failed." }
Start-Process (Join-Path $Workspace "evidence.html")
```

`capture` renders existing JSON evidence and refreshes status. It does not run missing tests or manufacture screenshots. Open the HTML as a local file; do not host the private workspace as a website.

### 19B. Export an allowlisted copy for review

The helper tool is included in the GitHub submission package. Export to a NEW private review directory first:

```powershell
$ExportFolder = Join-Path $PrivateRoot ("exports\" + (Get-Date -Format "yyyyMMdd-HHmmssfff"))
python "$Project\tools\export_evidence.py" --workspace "$Workspace" --out "$ExportFolder"
if ($LASTEXITCODE -ne 0) { throw "Evidence export failed." }
Start-Process "$ExportFolder"
```

The exporter excludes wallet/configuration files and supports selected evidence formats. It is not a complete sensitive-data detector. Review article text, error messages, usernames, paths, and screenshots yourself before copying a reviewed export into the repository for publication.

Original on-chain summary hashes refer to original files. Redacted/reformatted exports have their own hashes recorded in `EXPORT_MANIFEST.json`.

### 19C. Optional automated collection tool

`collect_evidence.py` stores raw logs in the source folder's `local-results`. **Use this helper only after ensuring the repository and its parent directories are not web-served.** Its current version has no output-directory option. The manual commands above keep the application's own evidence in the selected private workspace.

Readiness/status only:

```powershell
python "$Project\tools\collect_evidence.py" --workspace "$Workspace"
```

Explicitly run the demo, permission-changing security tests, and 10-request then 1,000-request benchmarks:

```powershell
python "$Project\tools\collect_evidence.py" --workspace "$Workspace" --run-live-tests --requests 1000 --workers 10 --timeout 300
if ($LASTEXITCODE -ne 0) { throw "Collection stopped at a failed check. Inspect local-results privately." }
```

This tool does not create a chain or start stopped nodes. Start and verify the lab first. Running it after manual tests repeats those tests and creates more records.

### 19D. Screenshots for the report

| Screenshot | What it should demonstrate |
|---|---|
| Version and readiness | Actual installed versions, selected workspace, five online roles |
| Stream and permission queries | Required streams, subscriptions, role separation |
| Signed enrollment record | Role/address binding and recorded signature evidence |
| Article, prediction, and reviews | Matching IDs/hashes and distinct reviewer publishers |
| Final decision and inspect | Expected classroom decision and `audit_pass: true` |
| Negative security test | Permission-related rejection and restored readiness |
| Load test summary | Requested/success/failed/unknown/confirmed counts and timings |
| Safe shutdown | Every relevant node reporting `ports_closed: true` |

Use genuine screenshots of your own terminal. Add captions explaining the meaningful fields. Do not publish private RPC credentials, wallet contents, or raw configuration files. Redacting a username is acceptable when disclosed; changing results or manufacturing a screenshot is not.

<a id="github"></a>
## 20. Publish the source code to GitHub

Run Git commands from `$Project`, not from the private workspace. `.gitignore` helps prevent adding matching untracked files; it does not remove secrets already committed and does not block HTTP access. See [R9](#references).

### 20A. Check the repository and prepare reviewed files

```powershell
Set-Location -LiteralPath $Project
git --version
if ($LASTEXITCODE -ne 0) { throw "Git is not available." }

# Run this only if this source folder is not already inside a Git repository.
if (-not (Test-Path -LiteralPath (Join-Path $Project ".git"))) {
    git rev-parse --show-toplevel
    if ($LASTEXITCODE -eq 0) {
        throw "This folder is inside another Git repository. Verify the intended repository root first."
    }
    git init -b main
    if ($LASTEXITCODE -ne 0) { throw "Git initialization failed." }
}

git status --short
```

An expected error from `git rev-parse` before initialization means no parent repository was found. No network push happens in this block.

Ensure `.gitignore` is present. Do not stage any workspace, wallet, `lab.json`, `multichain.conf`, private key, or RPC credential. Only add reviewed evidence. The supplied paper/report/docs folders belong to the source package; your final assessed report must be completed with your own explanation and actual results.

### 20B. Stage and check

```powershell
git add .
if ($LASTEXITCODE -ne 0) { throw "Git staging failed." }

python .\tools\check_repository.py --staged
if ($LASTEXITCODE -ne 0) { throw "Publication guard failed. Do not commit or push." }

git diff --cached --stat
git diff --cached --name-only
git diff --cached
```

Read the staged diff privately. A guard pass is not proof that every secret or inappropriate file was detected. Do not push until this manual review is complete.

### 20C. Commit and push deliberately

Create an EMPTY repository in your GitHub account and copy its actual remote URL. Do not create a second remote if the correct one already exists. Do not put access tokens in the URL or README.

```powershell
git commit -m "Document and verify FakeMedia MultiChain implementation"
if ($LASTEXITCODE -ne 0) { throw "Commit failed. Check Git identity and staged changes." }

git remote -v
```

For a repository without `origin` yet:

```powershell
$RepositoryUrl = (Read-Host "Paste your actual GitHub repository HTTPS or SSH URL").Trim()
if ([string]::IsNullOrWhiteSpace($RepositoryUrl)) { throw "Repository URL is required." }
git remote add origin "$RepositoryUrl"
if ($LASTEXITCODE -ne 0) { throw "Could not add origin. Inspect existing remotes." }
```

After confirming `origin` is correct:

```powershell
$Branch = (git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($Branch)) { throw "No current branch was found." }
git push -u origin "$Branch"
if ($LASTEXITCODE -ne 0) { throw "Push failed. Read the authentication or remote error; do not force push." }
git rev-parse HEAD
```

Give the teacher the accessible repository link and record the actual commit ID. Never promise successful tests on another PC before that environment runs them. If Git requests author configuration, set your own name/email locally; do not use made-up values or secrets.

<a id="recovery"></a>
## 21. Backups, moved folders, and diagnostic commands

### 21A. Source relocation versus workspace relocation

The new `$Project` path selects code. `$Workspace` selects the data and saved node configuration. They do not have to share a parent directory.

`lab.json` stores `bin_dir`, each node's absolute `datadir`, each node's absolute `conf`, saved addresses, ports, and genesis information. Copying just `lab.py` is fine. Copying `lab.json` without its referenced files is not a restored chain.

If only the MultiChain binary folder changed, the supported update is:

```powershell
python "$LabFile" --workspace "$Workspace" repair --bin-dir "$MC"
```

It does not repair arbitrary moved `datadir`/`conf` paths. The simplest route after moving source is Section 2A: reuse the original workspace. For a real data relocation, first make a clean stopped backup and plan the path changes; do not bulk-edit identity, genesis, or blockchain-parameter fields. This README does not claim a tested workspace-migration command exists in this version.

### 21B. Clean private backup

This stops the normal lab, then copies its complete workspace to a NEW private backup directory. It does not restart automatically.

```powershell
python "$LabFile" --workspace "$Workspace" stop
if ($LASTEXITCODE -ne 0) { throw "Shutdown failed. Do not copy live wallet/database files." }

$BackupParent = Join-Path $PrivateRoot "backups"
New-Item -ItemType Directory -Path $BackupParent -Force | Out-Null
$BackupPath = Join-Path $BackupParent ("workspace-" + (Get-Date -Format "yyyyMMdd-HHmmssfff"))
if (Test-Path -LiteralPath $BackupPath) { throw "Backup destination already exists." }
Copy-Item -LiteralPath $Workspace -Destination $BackupPath -Recurse
Write-Host "Private backup: $BackupPath"
```

The backup contains secrets and absolute original paths. Protect it like the original; do not commit, upload with the report, or web-host it. Copying locally is not encryption, a restore test, or protection from total disk failure. Keep its source-version/commit association and verify restoration separately without overwriting the only good copy.

### 21C. Show saved node paths and ports without printing secrets

```powershell
$ConfigFile = Join-Path $Workspace "lab.json"
$Config = Get-Content -LiteralPath $ConfigFile -Raw -Encoding UTF8 | ConvertFrom-Json
$Config.nodes.PSObject.Properties | ForEach-Object {
    [PSCustomObject]@{
        Role = $_.Name
        DataDirectory = $_.Value.datadir
        RPC = $_.Value.rpc_port
        P2P = $_.Value.p2p_port
        DataExists = Test-Path -LiteralPath $_.Value.datadir
        ConfigExists = Test-Path -LiteralPath $_.Value.conf
    }
} | Format-Table -AutoSize
```

These are local paths, not RPC passwords. Do not print the full `multichain.conf` or paste wallet files into a support chat.

### 21D. Inspect only the relevant listening ports

```powershell
$Ports = @()
foreach ($Property in $Config.nodes.PSObject.Properties) {
    $Ports += [int]$Property.Value.rpc_port
    $Ports += [int]$Property.Value.p2p_port
}
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -in $Ports } |
    Select-Object LocalAddress, LocalPort, OwningProcess
```

A listener is not proof that it belongs to the expected wallet. Let START/readiness identify the endpoint; do not grant permissions or kill a process just because it has a familiar port.

### 21E. Inspect a node's startup log privately

```powershell
$Role = "validator2"
$StartupLog = Join-Path $Config.nodes.$Role.datadir "startup.log"
Get-Content -LiteralPath $StartupLog -Tail 60
```

The launcher replaces `startup.log` on a new launch, so preserve a private copy before restarting if that failure log matters. Redact sensitive details before sharing.

### 21F. Read-only IIS mapping inspection

Because your source folder is under `wwwroot`, inspect existing mappings rather than assuming it is private. This block only lists mappings; it does not stop other XauZit sites or edit server configuration. It may require appropriate local privileges.

```powershell
$AppCmd = Join-Path $env:windir "System32\inetsrv\appcmd.exe"
if (Test-Path -LiteralPath $AppCmd) {
    & "$AppCmd" list vdir
} else {
    Write-Host "appcmd.exe was not found here. This is not a complete check for every possible web server."
}
```

If a site/alias serves this repository or a parent directory, remove that exposure through the appropriate site configuration before collecting private logs here. Do not stop unrelated production sites as a shortcut. Keeping the private workspace outside the web root is necessary but does not automatically protect `.git` or `local-results` under the source folder. See [R4](#references).

<a id="troubleshooting"></a>
## 22. Troubleshooting

| Symptom | Meaning to investigate | Correct next step |
|---|---|---|
| `multichaind is not recognized` | Current folder is not automatically searched for executables | Use a full executable path with `&`; normal operation uses `lab.py start` |
| `Parameter set ... not complete` from a bare daemon command | Wrong/default data directory or incomplete standalone node | Select the saved workspace and run START; do not immediately create another chain |
| `Couldn't connect to seed node 8441` | A port was supplied where a host was expected | Do not join another node to start this lab; seed format is `chain@host:P2P-port` |
| `LiteralPath ... is null` | Session variables were not initialized | Rerun all of Section 1 in that window |
| `Value cannot be null. Parameter name: encoding` from `WriteAllText` | `$Utf8NoBom`/`$WorkspaceChoiceFile` are empty, usually because Section 1 ran inside `& { ... }` and its variables disappeared when the block ended. The workspace choice was NOT saved, even if a success line printed afterwards | Rerun Section 1 directly (no outer `& { ... }`), then rerun Section 2A |
| Python prints `unknown option --workspace` | `$LabFile` is empty, so Windows PowerShell dropped the empty argument and Python read `--workspace` as its own option; `lab.py` never ran | Rerun Section 1 directly (no outer `& { ... }`); check `$LabFile` is not empty before retrying |
| CLI usage screen instead of data | Missing chain name or arguments, often from null configuration | Run all of Section 12A, not only its last line |
| `No lab.json in workspace` | Wrong selection, no setup, or moved data | Check Section 2; do not infer that all original data is lost |
| `Workspace already exists` | SETUP is being rerun | Use START, or REPAIR for incomplete setup |
| Existing node data but no `lab.json` | Partial/misplaced workspace | Preserve it; do not overwrite node folders or delete wallets |
| Port already in use | Existing lab/another program is listening | Inspect Section 21D; stop the intended old lab or deliberately use other ports |
| Transport connection refused | Node offline or wrong endpoint/configuration | START, then DOCTOR; not a successful negative security test |
| Missing registry/news/benchmarks | Incomplete setup or wrong chain | DOCTOR, then REPAIR if setup is incomplete |
| Miner `waiting-mining-diversity` | Authorization and immediate mining eligibility are different | Check `listminers.permitted`; keep the intended diversity setting |
| `permission mismatch: mine` with old code | Earlier checker confused eligibility with authorization | Verify application version is `2.0.2-mining-check`, then inspect actual miner permissions |
| Stream permission denied after an experiment | Writer may still be revoked | Restore that role explicitly, then DOCTOR |
| `Run: python lab.py train` | Model missing in the selected workspace | TRAIN with the included dataset; verify workspace selection |
| Duplicate article ID / validator already voted | Reusing an existing logical record | Read the existing record; use a fresh ID for a new experiment |
| Already finalized | Decisions are append-only in this application | Create a new review/article version, not an overwrite |
| JSON decoding / RPC parameters error | Native Windows quoting or non-array parameters | Use a UTF-8 parameter file containing a JSON array |
| `audit_pass: false` | Audit evidence did not satisfy its checks | Read `audit_error`, referenced IDs, signatures, and confirmations |
| `match: false` | Local file bytes differ from recorded text hash | Check BOM/newlines and actual edits; zero exit alone is not a pass |
| Writer lock exists | Another write process or an interrupted write | Stop issuing writes; investigate that process and uncertain transactions before touching any lock |
| Fast run with 1,000 failures | Failed requests, not successful throughput | Fix underlying readiness/permission errors and rerun a 10-request test |
| Confirmation timeout | Some known txids not observed at the requested depth | Check miners/peers; reconcile before retrying writes |
| `ports_closed: false` | Shutdown incomplete or unexpected listener | Inspect identity/ports; do not copy live data or force-kill every daemon |

If a command fails, stop that sequence and preserve its exact error. Repeating random port numbers, SETUP commands, or broad permission grants makes the state harder to diagnose.

<a id="commands"></a>
## 23. Complete application command reference

All commands below are used after `python "$LabFile" --workspace "$Workspace"` unless help/version is requested. This table documents the inspected source version, not speculative features.

| Command | Options | Main effect |
|---|---|---|
| `setup` | Required `--bin-dir`; optional `--chain`, `--rpc-base`, `--p2p-base`, `--block-time`, `--block-size`, `--diversity`, `--auto-ports` | Create a NEW five-node chain/workspace |
| `repair` | Optional `--bin-dir` | Resume incomplete setup or update binary path |
| `start` | Optional `--role` | Start all or one saved node |
| `stop` | Optional `--role` | Graceful shutdown of all or one saved node |
| `status` | None | Snapshot of nodes, miners, permissions, streams |
| `doctor` | None | Validate full lab readiness |
| `train` | `--dataset`, `--epochs`, `--seed` | Train and save classroom model/evaluation |
| `nlp` | Required `--text`; optional `--threshold` | Local prediction without a ledger write |
| `submit` | Required `--text`; optional `--id` | Publish article and wait for confirmation |
| `analyze` | Required `--id`; optional `--threshold` | Publish prediction for a submitted article |
| `vote` | Required `--role`, `--id`, `--label`, `--reason` | Publish validator review |
| `finalize` | Required `--id` | Publish one authority decision |
| `inspect` | Required `--id` | Check recorded article/decision evidence |
| `demo` | None | Three fixture workflows and audits |
| `security-tests` | None | Live and local security assertions; mutating |
| `revoke` | Required `--role` | Revoke configured application stream access |
| `restore` | Required `--role` | Restore configured application stream access |
| `verify-file` | Required `--id`, `--file` | Compare exact local bytes to article hash |
| `reward` | Optional `--amount` (default 1) | Transfer NewsCredit from authority to publisher |
| `reputation` | None | Derive descriptive teaching score |
| `benchmark` | `--mode`, `--n`, `--workers`, `--payload-bytes`, `--confirmations`, `--timeout`, `--threshold`, `--fixture-votes` | Run measured ledger or pipeline load |
| `reconcile` | Required `--run-id`; optional `--stream` | Query actual ledger records by run ID |
| `capture` | None | Render saved evidence as a local HTML page |
| `rpc` | Positional method; optional `--role`, `--params`, `--params-file` | Operator-level native RPC call |

`start`, `stop`, and `rpc` support all five roles. `vote` supports only validator1 and validator2. `revoke`/`restore` support publisher and the two validators. Labels are uppercase REAL, FAKE, REVIEW.

Additional helper scripts in the submission package:

| Script | Options | Purpose |
|---|---|---|
| `tools\collect_evidence.py` | Required `--workspace`; optional `--run-live-tests`, `--requests`, `--workers`, `--timeout` | Run existing-workspace checks and optional live tests |
| `tools\export_evidence.py` | Required `--workspace`; optional `--out` | Export reviewed-format evidence outside the private workspace |
| `tools\check_repository.py` | `--staged` or its own `--help` | Inspect candidate publication files |

### Exam-day minimum

Run Section 1; verify the selected workspace. START -> DOCTOR -> DEMO -> security tests -> 10 requests -> requested experiment -> inspect results -> CAPTURE -> STOP. Do not change the chain parameters, permissions, model, or source code casually immediately before assessment.

<a id="scope"></a>
## 24. Scope, authorship, and references

### What this implementation claims

This is a MultiChain adaptation of selected identity, publication, review, and audit ideas from **Fake Media Detection Based on Natural Language Processing and Blockchain Approaches**, by Zeinab Shahbazi and Yung-Cheol Byun (2021), DOI `10.1109/ACCESS.2021.3112607`.

It uses real MultiChain RPC, wallets, permissions, streams, and transactions. Python implements the business decision logic outside blockchain consensus. The included model and reviewer votes are classroom substitutions, not a recreation of the original Fabric/Composer deployment, research dataset, or deep reinforcement-learning experiments.

Five local processes share one Windows host and one operator's control. Enrollment proves possession of a key in this prototype, not legal identity verification. Permissioned publishing does not prove news truth. The code is an educational implementation, not a production misinformation-detection or custody system.

The paper's conclusion points toward further work on Proof of Authority and user validation. Explain how this prototype's enrollment and revocation address an aspect of that direction, and acknowledge the remaining limits rather than claiming to have solved all trust problems. Consult the actual [selected paper](paper/Selected_Paper.pdf) and [mapping notes](docs/PAPER_MAPPING.md).

### Source basis and testing limits

Application commands, defaults, behaviors, file locations, and limitations in this README were checked against `lab.py` version `2.0.2-mining-check`, its tests, and the three `tools` scripts in the supplied GitHub submission ZIP. External PowerShell/MultiChain/IIS/Git operating guidance is identified below. These sources are separate: a vendor API capability is not automatically an implemented feature in `lab.py`.

The previously supplied Windows transcript supports a successful readiness/CLI run of an earlier selected workspace. It does not establish results at the new source path or the outcome of a future benchmark. Validate the new run on your own Windows machine and retain genuine evidence. No benchmark times, screenshot results, or marks are guaranteed by this README.

This guide is AI-assisted operational documentation. Your teacher's assessed-report authorship rule still applies. Write your report from your own understanding, disclose assistance as required, and use actual measurements; do not submit this README as a claim of unaided report authorship.

<a id="references"></a>
### References

Repository sources: [lab.py](lab.py), [requirements.txt](requirements.txt), [test_lab.py](test_lab.py), [test_recovery.py](test_recovery.py), [test_mining_permissions.py](test_mining_permissions.py), [test_submission_tools.py](test_submission_tools.py), [collect_evidence.py](tools/collect_evidence.py), [export_evidence.py](tools/export_evidence.py), [publication guard](tools/check_repository.py).

External operating references, checked 2026-10-09:

- **R1:** Microsoft, [PowerShell command precedence](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_command_precedence?view=powershell-5.1).
- **R2:** Microsoft, [PowerShell scopes](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_scopes?view=powershell-5.1).
- **R3:** Microsoft, [PowerShell quoting rules](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_quoting_rules?view=powershell-5.1).
- **R4:** Microsoft, [IIS physical application paths](https://learn.microsoft.com/en-us/iis/web-development-reference/native-code-api-reference/ihttpapplication-getapplicationphysicalpath-method) and [AppCmd inspection](https://learn.microsoft.com/en-us/iis/get-started/getting-started-with-iis/getting-started-with-appcmdexe).
- **R5:** MultiChain, [Runtime parameters and data directories](https://www.multichain.com/developers/runtime-parameters/).
- **R6:** MultiChain, [JSON-RPC API](https://www.multichain.com/developers/json-rpc-api/).
- **R7:** MultiChain, [Creating and connecting to a blockchain](https://www.multichain.com/developers/creating-connecting/).
- **R8:** MultiChain, [Blockchain parameters](https://www.multichain.com/developers/blockchain-parameters/).
- **R9:** GitHub, [Adding local code to GitHub](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github); Git, [git-status](https://git-scm.com/docs/git-status).

**Remember: source code is replaceable; your private workspace is the chain state. Select it deliberately, test one step at a time, and stop cleanly.**
