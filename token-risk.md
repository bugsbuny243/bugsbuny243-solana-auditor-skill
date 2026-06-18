# Token Risk Skill

Assess Solana token safety using on-chain data via Alchemy RPC.

## What to check

### 1. Mint authority
- `mintAuthority: null` → renounced, good signal
- `mintAuthority: <address>` → active, can print unlimited tokens

### 2. Freeze authority
- `freezeAuthority: null` → renounced, good signal
- `freezeAuthority: <address>` → active, can freeze wallets

### 3. Supply
- Total supply vs circulating supply discrepancy → risk signal
- Sudden large mints in recent slots → red flag

### 4. Holder concentration
- Top 10 holders > 50% supply → high risk
- Single wallet > 20% supply → review

### 5. Creator wallet behaviour
- Creator wallet age < 7 days → sniper / disposable wallet risk
- Creator funded from exchange directly before launch → pattern risk

## Verdict mapping

| Condition | Grade | Action |
|---|---|---|
| All clear, authority renounced | A | Monitor |
| Minor signals, authority active | B–C | Watch |
| Concentration risk or young creator | D | Review |
| Active mint + concentrated supply | F | Avoid |

## RPC call pattern

```javascript
// Get mint info
const mintInfo = await connection.getParsedAccountInfo(mintAddress);
const { mintAuthority, freezeAuthority, supply, decimals } = mintInfo.value.data.parsed.info;

// Get top holders
const holders = await connection.getTokenLargestAccounts(mintAddress);
```

## Output

```
Token Risk Assessment
Mint authority:   null (renounced ✓)
Freeze authority: null (renounced ✓)  
Supply:           1,000,000,000
Top holder:       8.2% (acceptable)
Creator age:      142 days (acceptable)

Grade: A | Risk: 14/100 | Action: Monitor
```
