# Paper-to-MultiChain mapping

References [1]-[8], [C], [E1], [E2] are defined in the repository's `REFERENCES.md`. Statements labeled [1] describe the authors' paper; statements labeled [C] describe this code.

## What the paper proposes

The paper combines natural language processing, reinforcement learning and a permissioned blockchain to address false news and untrustworthy users. Figure 1 (PDF p.3, printed p.128444) links an off-chain data lake and analysis modules to a blockchain network and participant clients. Section III.A describes preparation, tokenization and feature extraction; Section III.B describes a deep reinforcement-learning approach. Section III.C identifies users, publishers, validators, transactions and news. Section III.C.2 uses Hyperledger Composer for business logic and access rules. Section V and Table 6 report Hyperledger Fabric 1.2, Composer, Docker, Node.js and CouchDB. [1]

The paper presents PoA in its design and conclusion, while Section VI.B discusses PBFT and RAFT and ordering-service evaluation. Preserve those separate statements; the paper does not supply enough deployment detail here to turn them into one fully reproducible consensus configuration. This adaptation does not claim to reproduce any of those evaluation environments. [1]

## Implemented mapping

| Original component / idea [1] | MultiChain adaptation [C] | Justification and boundary |
|---|---|---|
| User identification / enrollment | Authority-approved roles; signed challenge; `registry` stream | Demonstrates key possession and role binding. Does not verify a real person or news organization. |
| Publisher | Dedicated publisher wallet/process; `news.write` | Separates article submission from final-decision authority. |
| Validators | Two configured reviewer wallets; `votes.write` | Requires distinct signed records. Fixture runs are not independent human investigation. |
| News records | `news` JSON: ID, text, SHA-256, publisher and timestamps | Provides attributable content and a reference for later reviews. Full text is on-chain in this lab. |
| NLP and deep RL | English tokenizer, TF-IDF cosine evidence, terminal tabular-Q teaching model | Keeps an off-chain analysis stage but does not replicate DRL, original features or dataset. |
| Smart contract business logic | Python `submit`, `vote`, `finalize`, `inspect` + native stream ACLs | Application rules are not Fabric chaincode and can be bypassed by authorized raw RPC clients. |
| Permissioned blockchain | Five MultiChain processes/wallets on one local computer | Replicated ledger, but not five independent organizations or a multi-host evaluation. |
| PoA-oriented authorization | Three addresses with native `mine` permission; diversity 0.6 | Uses MultiChain's native permissioned mining, not a claimed PoA/PBFT/RAFT reproduction. |
| Credibility / incentives | Descriptive score from decisions; optional `NewsCredit` transfer | Score formula is a teaching choice. Neither score nor token automatically changes permissions. |
| Querying / historical records | Stream indices, `inspect`, `reconcile`, evidence exports | Audits recorded and referenced evidence, not truth or full historical authorization. |
| Transaction history | Native signed transactions, txids, block hashes and confirmations | Confirms ledger inclusion separately from prediction/reviewer correctness. |

## Exact conclusion direction addressed

The conclusion ends by identifying further investigation of the Proof-of-Authority protocol and user validation (PDF p.11, printed p.128452). It does not present a detailed numbered future-work list or promise MultiChain-specific scalability improvements. [1, Section VII]

This lab addresses a bounded part of the **user-validation/authority-management** direction: authority approval, role/address/genesis-bound signed enrollment, expiring one-use challenges, least-privilege stream writers, explicit revocation/restoration and auditable publication. It also exposes miner authorization separately from the diversity waiting rule. The contribution is an implemented classroom control path, not a claim that user identity, fake news or consensus security is solved. [C]

## What has not been reproduced

The original 900,000-record data collection, neural/deep-RL training, original performance plots, demographic/time-series analysis, original REST application, production Fabric/Composer deployment and publisher anonymity are not reproduced. The 32-row teaching corpus is synthetic classroom content; its test labels are not research ground truth. [1, C]

Approval of publication and a block's validation are separate decisions. MultiChain enforces signed transactions and permissions; the Python policy interprets article evidence. Do not label the off-chain Python code as an on-chain Solidity or Fabric smart contract. [C]
