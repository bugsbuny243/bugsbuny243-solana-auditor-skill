# solana-auditor-skill

> Production-grade Solana security auditing skill for Claude Code and Solana AI Kit.
> Covers token risk, program analysis, wallet behaviour, launch cluster detection and signed verdict generation.

## What this skill does

This skill turns Claude Code into a Solana security expert. It routes audit requests to focused sub-skills covering the full auditor lifecycle — from a quick token safety check to a formal, signed security report.

## Routing table

| Request type | Sub-skill loaded |
|---|---|
| Token risk / rug check | `skills/token-risk.md` |
| Program / smart contract audit | `skills/program-audit.md` |
| Wallet behaviour analysis | `skills/wallet-score.md` |
| Launch cluster / sybil detection | `skills/sybil-radar.md` |
| Claim URL / walletless risk | `skills/claim-shield.md` |
| Full security report | `skills/report-generator.md` |

Load only the sub-skill you need. Do not load all files at once.

## Quick start

```bash
# Install
curl -sSL https://raw.githubusercontent.com/bugsbuny243/solana-auditor-skill/main/install.sh | bash

# Or clone manually
git clone https://github.com/bugsbuny243/solana-auditor-skill
```

Then in Claude Code:

```
/skill solana-auditor-skill
Audit token: EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v
```

## Output format

Every audit produces a **signed verdict**:

```
Grade:      A–F
Risk Index: 0–100
Action:     Monitor | Watch | Review | Avoid | Do not connect
Signed:     Yes (deterministic rule hash)
Source:     Alchemy Solana RPC / on-chain
```

## Sub-skills
