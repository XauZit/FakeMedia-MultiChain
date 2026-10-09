# Security scope and publication precautions

This is a single-host teaching deployment, not a production news-verification service. All five wallets and RPC endpoints are controlled by the same operating-system user. Separate processes do not create independent administrative trust domains. The supplied peer output reports unencrypted loopback connections; do not describe this run as end-to-end encrypted.

## Implemented controls

The preserved application requests restricted membership, three authorized block miners, per-stream write permissions, signed transactions, a signed enrollment challenge bound to role/address/chain/genesis, a 120-second challenge validity period, local nonce replay tracking, content hashes and reference checking. An application writer lock prevents cooperating lab commands from writing concurrently. MultiChain credentials are generated per node and the RPC client refuses non-loopback endpoints.

The two-reviewer application policy and duplicate-ID checks are Python logic, not network-enforced smart contracts. Authorized raw RPC clients can bypass the wrapper. The authority holds administrator powers. A hash proves equality to the recorded content, not truth. A valid signature proves key control, not a person's real-world identity. The auditor rechecks referenced evidence, not all historical permissions or every omitted/conflicting record.

## Limitations to state in the report

There is no anonymity guarantee, no private on-chain news in Community Edition, no independent human fact checking in fixture runs, no replicated enrollment-nonce database, no CFT/BFT fault-model evaluation, and no full recreation of the paper's predictive model. A transferred NewsCredit is a demonstration asset, not trustworthy reputation or a mining reward.

Never weaken mining diversity, grant all roles admin/mine, disable readiness checks, or delete wallets to make a screenshot look successful. Do not grant the accidentally initialized extra node permission; use the saved workspace.

## Protect publication

Do not publish live `lab.json`, `multichain.conf`, wallet files, credentials or executable binaries. Use allowlisted evidence export, inspect JSON and screenshot contents, then use the staged-file guard before committing. A secret scanner is a partial safeguard, not a guarantee. Keep real-world private data out of this classroom chain.

If credentials were ever committed, treat them as exposed; merely deleting them in the latest commit is not sufficient. For this classroom project, obtain guidance before rotating identities or rebuilding anything that holds evidence.
