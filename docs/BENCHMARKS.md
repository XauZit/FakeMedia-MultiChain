# Benchmark protocol and exam variations

This guide describes the actual implementation in `lab.py` (`benchmark`, `Lab.pipeline`, `reconcile`). No successful live timing has been supplied for this package. Do not fill a results table using invented numbers, Python unit-test duration, or the paper's published figures.

## What is measured

| Workload | One logical request | Transactions per fully completed request |
|---|---|---|
| ledger | One fixed-content publication to benchmarks | 1 |
| pipeline | Article + prediction + two fixture votes + decision | 5 |

The total N is not the worker count. All N logical requests have arrival time t0; at most W workers process them. This is a bounded-concurrency burst on one computer, not N physical clients. The ledger payload option controls ASCII content bytes; JSON and transaction overhead are additional. Pipeline mode ignores that content-size option and uses the fixture text. [C]

## Timing definitions

- Queue time: worker service-start minus burst t0.
- Service time: request-finish minus worker service-start. Pipeline service time includes its prerequisite confirmation waits.
- Burst response: request-finish minus burst t0, including queue time.
- Submission seconds: completion of all request attempts minus t0. Thread scheduling and request trace logging affect this batch interval.
- Confirmation observation seconds: end of post-submission auditor polling minus t0. This includes submission and observer overhead; it is an upper-bound batch observation, not exact per-transaction inclusion latency.

Let S be successful requests, B known returned transaction IDs, C confirmed complete requests, K confirmed known transactions, Ts submission seconds and Tc confirmation observation seconds. The code reports S/Ts, B/Ts, C/Tc and K/Tc separately. Percentiles use linear interpolation over the sorted successful-request samples. Failed and unknown request counts must accompany all success-only latency metrics. [C]

## Run conditions to record

Software versions, commit/hash, CPU/RAM/OS, requested and observed chain parameters, five-process single-host topology, worker count, N, payload, confirmation target, mempool state and run ID. Setup/model training are outside the timer. The post-timer audit-summary transaction is excluded. Do not equate this experiment with the paper's Fabric/ordering-service charts. [C,1]

Run a small warm-up, then at least three repetitions for a comparison when time permits. Preserve each run rather than cherry-picking the fastest. Hold other settings constant when comparing one variable. The paper's hardware, data, platform and measurement methods differ. [1,C]

## Exam command variations

In the block below, replace `$Arguments` with ONE of the argument arrays that follow. Every execution should pass doctor first. Do not launch several benchmark commands in parallel against the same workspace.

```powershell
& {
    $Workspace = "C:\Users\BK-PC\Documents\Study Material\FAST - NUCES\Semester 3\Applications of Blockchain\Mid Term\FakeMedia_MultiChain_Exam_Kit\FakeMedia_Exam_Kit\workspace"
    $Arguments = @("--mode", "ledger", "--n", "1000", "--workers", "10", "--payload-bytes", "1024", "--confirmations", "1", "--timeout", "300")
    python .\lab.py --workspace "$Workspace" doctor
    if ($LASTEXITCODE -ne 0) { throw "Readiness failed." }
    python .\lab.py --workspace "$Workspace" benchmark @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Run incomplete or failed; record the outcome and inspect evidence." }
}
```

Suggested variations, not precomputed results:

| Teacher's variation | Change |
|---|---|
| 100 instead of 1,000 requests | `--n 100` |
| Sequential baseline | `--workers 1` |
| More concurrent work | `--workers 25` |
| 4 KiB content | `--payload-bytes 4096` in ledger mode |
| Observe three confirmations | `--confirmations 3` |
| Full article pipeline | `--mode pipeline --n 10 --workers 2 --fixture-votes --timeout 300` first |
| 1,000 article workflows | Same pipeline flags with `--n 1000`; expect 5,000 transactions only if fully successful |

`--timeout` limits the post-submission observation period, not total runtime. Prerequisite waits inside pipeline requests have their own timeouts. Increasing workers is not guaranteed to improve throughput: locks, node RPC threads, disk and block production can dominate. [C]

## Reconcile uncertain writes

A transport error may occur after a transaction was accepted. The client records an unknown outcome and does not resend automatically. Use the actual run ID with `reconcile --run-id ID`. Add `--stream news` for pipeline article reconciliation. Ledger reconciliation checks publisher/hash/run binding, counts and duplicate IDs; pipeline reconciliation counts submitted articles, not completed workflows. Its confirmation threshold is one. [C]

Do not report 100% success merely because a timer finished. Report requested, success, failure, unknown and confirmed-complete counts. If observation times out, label the result incomplete at the deadline rather than inventing a completion time. After a short reorganization, the observer rescans the run range on tip changes; finite confirmations still do not create an absolute finality guarantee. [C]

## Results table to fill using actual summary.json

| Run ID | Mode | N | W | Payload | Confirmations | Success | Failure | Unknown | Confirmed complete | Ts | Tc | p95 service |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| [actual] | [actual] | | | | | | | | | | | |

Do not replace missing measurements with zero. Keep failed runs for diagnosis, labeled as failed. Attach CSV/JSONL traces and a screenshot of the actual command and summary, with secrets removed.
