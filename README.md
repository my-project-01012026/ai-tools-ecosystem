# AI Tools Ecosystem

Official prelaunch website source (v0.12.0). **Information only — no Solana token, sales, active trading pool, or released Windows application.**

## Website

The repository root is the static site. Start at [index.html](./index.html); Russian version: [ru/index.html](./ru/index.html). The project has sections for AI programs, community, proposed Solana tokenomics and funding, security, development status, and documentation.

The planned token supply is 1,000,000,000 with seven *draft* reserves. The monthly burn is a **simulation**, not real blockchain transactions or a promise of returns. Community 1.0 software is still in development, and access does not depend on buying a token.

The site is deliberately marked PRELAUNCH and noindex. Translations have not received all necessary native-speaker/legal review. There is **no confirmed deployment to here.now** at the time of this commit.

## Security and integrity

- Static HTML/CSS/JavaScript; no wallet connectors or payments.
- No network API in local `assets/app.js`. It calculates display-only burn estimates.
- CSP in HTML and SRI hashes for linked assets; production HTTP response headers require separate verification.
- Source package scanned locally: 32 files, 23 HTML documents, 46/46 script/style SRI validations, no missing local file links, no external URLs, no embedded scripts, and no detected private keys.
- This is **static source verification**, not a full independent vulnerability assessment or production host audit.

## Licenses and trademarks

No blanket open-source license is granted to the website code, branding, images, or token material merely by making this repository public. Component licenses and future software distribution are separately reviewed. Do not treat the proposed token as issued or offered.

Last source snapshot: 2026-11-08. Mainnet, token issuance/sales, deployment, and software release remain separate gates.
