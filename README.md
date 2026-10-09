# FakeMedia: paper-inspired MultiChain implementation

**Implementation: `2.0.2-mining-check` | MultiChain Community 2.3.3 | Python 3.10+**

A five-process, one-host permissioned blockchain lab that maps the core news-publication, review, identity and audit ideas of Shahbazi and Byun's paper to MultiChain streams, permissions, signed transactions and an illustrative asset. The executable is the same `lab.py` that passed the supplied Windows network-readiness run; it has not been replaced by a simulator.

**Scope:** this is a simplified paper-inspired adaptation, not a replication of the authors' Hyperledger Fabric/Composer platform, dataset or deep reinforcement-learning model. Python applies the two-reviewer policy; native MultiChain miners do not execute that policy as Fabric chaincode. See [paper mapping](docs/PAPER_MAPPING.md).

## Submission status

The supplied console log demonstrates five-node readiness and native CLI access. It does **not** establish a passing application demo, security-test suite or successful 1,000-request benchmark. Those results must be collected on the student's machine. [Evidence provenance](evidence/README.md).

The teacher requires a student-authored report with no more than 10% AI-generated writing. [Report workbook](report/Implementation_Report_Workbook.docx) and [PDF workbook](report/Implementation_Report_Workbook.pdf) are authoring aids, **not final reports to submit unchanged**. The [technical reference](docs/Technical_Reference.pdf) is AI-assisted supporting documentation, not evidence of student authorship. Write your explanations from your own notes, disclose assistance, and follow the instructor's counting rules.

## What is included

| Item | Location |
|---|---|
| Actual application, dataset and dependency declaration | `lab.py`, `demo_news.csv`, `requirements.txt` |
| Core and regression tests; publication-tool tests | `test_*.py` |
| Selected paper, original uploaded bytes preserved | `paper/Selected_Paper.pdf` |
| Architecture and workflow figures, including editable DOT sources | `docs/figures/` |
| Technical reference, code index and workflow instructions | `docs/` |
| Student authoring workbook, writing prompts and screenshot plan | `report/` |
| Extracted real readiness results from the supplied console log | `evidence/provided-run/` |
| Live evidence collection and allowlisted export utilities | `tools/` |
| Unit-test CI (not live blockchain CI) | `.github/workflows/tests.yml` |
| Final deliverable checklist | `SUBMISSION_CHECKLIST.md` |

## Install prerequisites

Install Python 3.10+ and MultiChain Community **2.3.3** from its official distribution. Do not install a random similarly named pip package. The runtime and tests use only the Python standard library; `requirements.txt` intentionally has no packages. Git is needed only for publishing. Graphviz and Word are optional for editing figures and the report, not for running the chain.

From the folder containing this README:

```powershell
python --version
python .\lab.py --version
python -m unittest -v test_lab test_recovery test_mining_permissions test_submission_tools
```

## A. Bilal: use the already working workspace

Extract this repository into a **new source folder**. Do not move, copy into Git, or delete the existing private workspace. Run this entire block from the folder containing this README:

```powershell
& {
    $ErrorActionPreference = "Stop"
    $Workspace = "C:\Users\BK-PC\Documents\Study Material\FAST - NUCES\Semester 3\Applications of Blockchain\Mid Term\FakeMedia_MultiChain_Exam_Kit\FakeMedia_Exam_Kit\workspace"
    if (-not (Test-Path -LiteralPath "$Workspace\lab.json")) {
        throw "Existing workspace not found. Do not run setup to repair a missing path."
    }
    python .\lab.py --workspace "$Workspace" start
    if ($LASTEXITCODE -ne 0) { throw "Start failed." }
    python .\lab.py --workspace "$Workspace" doctor
    if ($LASTEXITCODE -ne 0) { throw "Doctor failed. Inspect its output." }
}
```

`--workspace` belongs **before** the subcommand. A new PowerShell window does not retain variables from an old one. Each block in this README initializes its own variables.

## B. Examiner: create a fresh independent lab

Use this route only for a new run, not to repair an existing workspace. It creates five local nodes and a new genesis block. Exact addresses, hashes and timings will differ from the supplied evidence.

```powershell
& {
    $ErrorActionPreference = "Stop"
    $MC = "C:\Users\BK-PC\Downloads\Programs\multichain-windows-2.3.3"
    foreach ($Name in @("multichaind.exe", "multichain-cli.exe", "multichain-util.exe")) {
        if (-not (Test-Path -LiteralPath (Join-Path $MC $Name))) { throw "Missing $Name" }
    }
    python .\lab.py --workspace .\workspace setup --bin-dir "$MC" --auto-ports
    if ($LASTEXITCODE -ne 0) { throw "Setup incomplete. Inspect the error before further commands." }
    python .\lab.py --workspace .\workspace doctor
    if ($LASTEXITCODE -ne 0) { throw "Readiness failed." }
}
```

Change `$MC` to the examiner's installation. `--auto-ports` avoids occupied port ranges; record actual ports from the output. On Linux, the equivalent is `python3 lab.py --workspace ./workspace setup --bin-dir /path/to/multichain --auto-ports`. Native Linux execution is not demonstrated by the supplied Windows log.

## Demonstrate and measure

For Bilal's existing chain, the following complete block runs real fixture writes, temporarily revokes/restores the publisher's `news.write` permission, and runs 10 then 1,000 ledger requests. Run it only after `doctor` passes. It stops at the first failed command.

```powershell
& {
    $Workspace = "C:\Users\BK-PC\Documents\Study Material\FAST - NUCES\Semester 3\Applications of Blockchain\Mid Term\FakeMedia_MultiChain_Exam_Kit\FakeMedia_Exam_Kit\workspace"
    python .\tools\collect_evidence.py --workspace "$Workspace" --run-live-tests --requests 1000 --workers 10
    if ($LASTEXITCODE -ne 0) { throw "A live test failed. Review local-results and do not claim a pass." }
    python .\tools\export_evidence.py --workspace "$Workspace"
    if ($LASTEXITCODE -ne 0) { throw "Evidence export failed." }
}
```

For a fresh examiner workspace, use `--workspace .\workspace` for both tools. Without `--run-live-tests`, collection runs `doctor` and `status` only. Logs are private under ignored `local-results/`. Reviewed exports go under `evidence/runs/`.

A `ledger` request is one benchmark-stream transaction. A `pipeline` request is one article passing through submission, prediction, two fixture votes and decision: **five transactions per completed request**. These are different workloads. [Benchmark method](docs/BENCHMARKS.md).

## Report and publishing

1. Complete [live evidence and screenshots](report/SCREENSHOT_PLAN.md).
2. Write the report in [the editable workbook](report/Implementation_Report_Workbook.docx). Replace all prompts with your own explanations and actual measurements. Export the finished document as `submission/Implementation_Report.pdf`.
3. Create an empty GitHub repository and follow [PUBLISH_TO_GITHUB.md](PUBLISH_TO_GITHUB.md). The `.gitignore` excludes runtime secrets, but manually review all staged files and images.
4. Submit the actual repository URL, `paper/Selected_Paper.pdf`, and your finished report PDF. The package does not create a remote repository or invent a URL.

**Do not upload:** `workspace`, `nodes`, `wallet.dat`, `multichain.conf`, `lab.json`, private keys, real credentials, or MultiChain executable binaries. Source code and generated evidence are different deliverables.
