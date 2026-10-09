# 2.0.2-mining-check

Replaces the mining authorization check in setup/repair and doctor with
listminers.permitted. Keeps mining-diversity intact and adds mining-state
readiness diagnostics. See MINING_FIX_README.md for the cause and recovery.
All 88 local tests pass, including 14 new mining regression tests.

## Earlier recovery features retained

# Recovery release 2.0.2

The main application is the full replacement `lab.py`, not a small patch.

- Handles MultiChain -710 (transaction not found) during bounded read-only confirmation polling. Never retries an uncertain write automatically.
- Adds numeric RPC error codes to diagnostics; invalid arguments and permission failures do not get treated as propagation delays.
- Adds `repair` to resume an incomplete saved setup without deleting data, replacing wallets, editing live chain parameters, or reissuing an existing asset.
- Adds `doctor`, checking saved identities, common-height agreement, stream existence, subscriptions, restricted writes, expected permissions, enrollments, the asset, and the teaching model.
- Prevents benchmarks from running on an incomplete or unhealthy setup, rather than quickly returning 1000 failed requests because the stream is absent.
- Preserves deliberate writer revocations when repairing an already-complete setup.
- Adds optional `--auto-ports` selection for NEW workspaces and graceful stop polling for RPC/P2P listener closure.
- Retains native MultiChain calls and the original paper-inspired application workflow, along with the clearly labelled fictional dataset and tabular teaching model.
- Provides a Windows launcher and a recovery guide with the paths from the supplied execution log.
- Includes 88 passing local tests, with explicit limits on what those tests validate.

No real MultiChain throughput figures or Windows execution screenshots are included. Existing failed-run evidence is not rewritten into successful results.
