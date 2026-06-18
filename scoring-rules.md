# Scoring Rules — Deterministic A–F Grading

These rules are deterministic and rule-based. No AI scoring — only on-chain signal weights.

## Grade mapping

| Risk Index | Grade | Action |
|---|---|---|
| 0–20 | A | Monitor |
| 21–40 | B | Monitor / Watch |
| 41–60 | C | Watch |
| 61–75 | D | Review |
| 76–100 | F | Avoid / Do not connect |

## Signal weights

### Token signals
| Signal | Risk points |
|---|---|
| Mint authority active | +20 |
| Freeze authority active | +15 |
| Top holder > 30% | +20 |
| Supply anomaly (recent large mint) | +25 |
| Creator wallet < 7 days | +15 |

### Sybil signals
| Signal | Risk points |
|---|---|
| Funding cluster (3+ wallets) | +30 |
| Sniper buy in slot 0-2 | +25 |
| Creator-linked buyer | +20 |
| All early buyers < 7 days | +15 |
| Concentration > 60% top 5 | +10 |

### Program signals
| Signal | Risk points |
|---|---|
| Upgrade authority active | +20 |
| No verifiable build | +15 |
| Known exploit pattern | +40 |
| Proxy with mutable impl | +25 |

## Rule version

`koschei-security-v1` — rule hash included in signed verdict.
