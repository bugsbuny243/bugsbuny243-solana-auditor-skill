# Security Report Generator

Generate a full, signed A–F security report combining all Koschei audit modules.

## When to use

Use this when a complete due diligence report is needed — not a quick check.
Loads all sub-skills. Token-efficient: skip modules not relevant to target type.

## Target types

| Input | Modules loaded |
|---|---|
| Token mint address | token-risk + sybil-radar + claim-shield |
| Raydium pool | program-audit + token-risk + sybil-radar |
| Wallet address | wallet-score + sybil-radar |
| Claim URL / program | claim-shield + program-audit |

## Report structure

```
═══════════════════════════════════════
KOSCHEI WEB3 HUB — SECURITY REPORT
═══════════════════════════════════════
Target:       <address or URL>
Target type:  Token / Pool / Wallet / Program
Generated:    <timestamp>
Rule version: koschei-security-v1

FINAL VERDICT
─────────────
Grade:        A–F
Risk Index:   0–100
Action:       Monitor | Watch | Review | Avoid | Do not connect
Signed:       Yes
Source:       Alchemy Solana HTTPS RPC

MODULE RESULTS
──────────────
Token Risk:        Grade X | Risk XX/100
Sybil Radar:       Grade X | Risk XX/100
Program Audit:     Grade X | Risk XX/100
Wallet Score:      Grade X | Risk XX/100

EVIDENCE SUMMARY
────────────────
[Key findings from triggered rules]

RECOMMENDED NEXT STEPS
───────────────────────
[Actionable guidance based on verdict]

DISCLAIMER
──────────
Koschei is an intelligence tool. This report does not constitute
financial or legal advice. Always do your own research.
═══════════════════════════════════════
```

## Final grade logic

Final grade = highest risk module grade (worst-case).
Risk Index = weighted average across modules.
