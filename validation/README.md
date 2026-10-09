# Validation scope

The package build ran 99 Python tests successfully: the preserved 88 application/regression tests plus 11 publication-tool tests. See `unit-tests.txt`. Environment: 3.13.5, Linux x86_64. This run did not launch a MultiChain daemon.

The separate supplied Windows log supports network readiness and native CLI queries. It does not certify later live demo/security/benchmark tests. The GitHub Actions workflow has been provided but has not run in the user's repository; its eventual status must be checked after pushing.

`lab.py` is byte-identical to the supplied v2.0.2 implementation. This package adds documentation and tooling without changing its consensus, permissions, pipeline or benchmarks. `PACKAGE_PROVENANCE.json` records the hash.
