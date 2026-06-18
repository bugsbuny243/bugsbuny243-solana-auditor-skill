# solana-auditor-skill

A production-grade Solana security auditing skill for [Solana AI Kit](https://github.com/solanabr/solana-ai-kit) and Claude Code.

Built on top of [Koschei Web3 Hub](https://tradepigloball.co) — a live, free Solana security intelligence platform.

## Problem

Solana builders and founders need fast, reliable security signals before interacting with tokens, programs, wallets, or claim pages. Existing tools are fragmented, expensive, or require wallet connection. There is no open, composable AI skill that covers the full auditor lifecycle.

## Solution

`solana-auditor-skill` gives Claude Code a complete Solana security toolkit:

- **Token risk** — mint authority, freeze authority, supply, holder concentration
- **Program audit** — upgrade authority, verifiable build, known exploit patterns
- **Wallet score** — activity posture, funding source, behavioural signals
- **Sybil / launch cluster radar** — early buyer clustering, creator links, sniper timing
- **Claim shield** — walletless URL and program risk before connecting
- **Signed report generator** — A–F grade, risk index 0-100, deterministic rule-based verdict

## Install

```bash
curl -sSL https://raw.githubusercontent.com/bugsbuny243/solana-auditor-skill/main/install.sh | bash
```

Or add as a submodule:

```bash
git submodule add https://github.com/bugsbuny243/solana-auditor-skill .claude/skills/solana-auditor-skill
```

## Usage in Claude Code

```
/skill solana-auditor-skill

# Token audit
Audit this token: So11111111111111111111111111111111111111112

# Program audit  
Check this program for upgrade authority risk: TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA

# Full report
Generate a full security report for: 9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM
```

## Output example

```
KOSCHEI SECURITY VERDICT
Token: EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v

Grade:       A
Risk Index:  12/100
Action:      Monitor
Signed:      Yes
Rule version: koschei-security-v1

Pump.fun Sybil Radar:    Low — no cluster evidence
Raydium Pool Guardian:   Low — authority renounced
Walletless Claim Shield: Low — no unsafe instructions

Source: Alchemy Solana HTTPS RPC
```

## Structure

```
solana-auditor-skill/
├── SKILL.md              ← entry point + routing table
├── README.md
├── install.sh
├── skills/
│   ├── token-risk.md
│   ├── program-audit.md
│   ├── wallet-score.md
│   ├── sybil-radar.md
│   ├── claim-shield.md
│   └── report-generator.md
└── rules/
    └── scoring-rules.md  ← deterministic A-F grading logic
```

## Live product

This skill is extracted from [Koschei Web3 Hub](https://tradepigloball.co) — a free, no-custody Solana security intelligence platform live in production.

GitHub: [bugsbuny243/Koschei-Web3-Hub](https://github.com/bugsbuny243/Koschei-Web3-Hub)

## License

MIT
