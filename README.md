# AI Tools Ecosystem — software portfolio

Independent founder-led AI software projects. This public repository contains the source for a static, informational website: **Local Media AI**, **CVLM Platform**, and **LocalAIDevManager**.

## Products and verified maturity

| Product | Stage | Details |
| --- | --- | --- |
| Local Media AI | Prototype under testing; public software release HOLD | [EN](/product/) · [RU](/ru/product/) · [separate information website](https://local-media-ai-community.cheekysloth259.chatgpt.site/en/) |
| CVLM Platform | Concept/design; no publicly verified release | [EN](/cvlm/) · [RU](/ru/cvlm/) |
| LocalAIDevManager | Concept/design; no publicly verified release | [EN](/localaidevmanager/) · [RU](/ru/localaidevmanager/) |

See [/status/](/status/), [/partners/](/partners/) and [/docs/](/docs/). Nine priority website locales: English, Russian, Kazakh, Simplified Chinese, German, French, Arabic, Japanese and Korean. Homepage translations are **draft**, not professionally reviewed. Eight older locale source directories are retained as a reserve but excluded from the audited deployment inventory. Only English and Russian have full product-detail pages; other locales use English detail fallbacks.

## Security and deployment

- Static HTML/CSS with no JavaScript execution, external fonts, client analytics, forms, payments, login or media uploads.
- CSP, a pinned stylesheet SRI hash, a SHA-256 file manifest and offline security tests.
- Production publication remains **manual and protected** through the existing here.now environment; no automatic push to production from PRs.
- Public host URL, HTTPS response headers, live links and analytics have **not** been independently verified in this change.
- `robots.txt` and noindex metadata remain in place until a live host audit and localization review are complete.
- The information site for Local Media AI is not a download or release approval.

No source code rights are granted merely because this repository is public. Program licensing remains subject to separate component review.

Updated 2026-11-23. All changes in this branch should be reviewed and pass CI before merge or production deployment.
