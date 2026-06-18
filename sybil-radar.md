# Sybil / Launch Cluster Radar

Detect coordinated launch behavior, early buyer clusters and sniper patterns on Pump.fun and Raydium launches.

## Detection signals

### 1. Early buyer clustering
- First 10-50 buyers funded from same source wallet
- Timing: multiple buys in same block or consecutive slots
- Wallet age: buyers all < 7 days old → coordinated

### 2. Creator-linked buyers
- Buyer wallets previously received SOL from creator wallet
- Creator wallet = buyer wallet (direct sybil)
- Common intermediary wallet between creator and buyers

### 3. Sniper timing patterns
- Buy transaction in slot 0-2 of pool creation
- Buy size: outsized relative to pool size at launch
- Immediate sell within same epoch → sandwich / sniper

### 4. Holder concentration at launch
- Top 5 wallets hold > 60% at launch → coordinated hold
- Wallets all created within 24h of each other → disposable

## Scoring

| Signal | Weight |
|---|---|
| Funding cluster (3+ wallets, same source) | +30 |
| Sniper timing (slot 0-2) | +25 |
| Creator-linked buyer | +20 |
| All buyers < 7 days old | +15 |
| Concentration > 60% top 5 | +10 |

Risk Index = sum of triggered weights, capped at 100.

## Output

```
Pump.fun Sybil Radar
Early buyer cluster:    Detected (7 wallets, same funder)
Sniper timing:          2 buys in slot 0
Creator relation:       No direct link
Wallet age:             3/10 buyers < 7 days

Grade: D | Risk: 72/100 | Action: Review
Signed: Yes | Rule: koschei-sybil-v1
```
