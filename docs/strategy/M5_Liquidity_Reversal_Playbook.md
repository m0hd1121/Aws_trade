# THE M5 LIQUIDITY REVERSAL PLAYBOOK
## A Mechanical Price-Action Day Trading System for EUR/USD & XAU/USD
### London & New York Kill Zones — Zero Indicators, Zero Discretion

---

**Document status:** Complete rulebook, v1.0
**Instruments:** EUR/USD (EU), XAU/USD (XAU)
**Execution timeframe:** M5 | Context timeframes: H4, H1
**Model type:** Liquidity sweep → structural reversal → point-of-interest entry
**Honest performance profile:** 35–45% win rate, blended average winner ≈ 2.2–2.6R, expectancy target +0.25R to +0.45R per trade after costs. See Section 12 before trading.

---

# SECTION 0 — CORE LOGIC (READ ONCE, THEN TRADE THE RULES)

The system trades one repeatable event: **engineered liquidity gets swept at a session extreme, smart money reverses price, and structure confirms the reversal.** Everything else in this document is filtration and risk control around that single event.

The causal chain, in order:

1. Overnight/prior-session price builds an obvious pool of resting stops (Asia high/low, previous day high/low, equal highs/lows).
2. During a Kill Zone, price runs through that pool (the **sweep**) — filling institutional orders against retail stops.
3. Price then breaks M5 structure in the opposite direction (the **CHoCH**) with displacement, leaving an imbalance (FVG) and an origin order block (OB).
4. Price retraces into that origin zone (the **POI**).
5. We enter at the POI, stop beyond the sweep extreme, target the opposing liquidity pool.

You are not predicting direction. You are waiting for the market to show the sweep-and-reverse sequence, scoring its quality objectively, and executing only when the score clears the bar.

---

# SECTION 1 — DEFINITIONS (OBJECTIVE, NON-NEGOTIABLE)

Every term below has exactly one meaning in this system. If a chart situation doesn't meet the definition, the answer is "no."

**1.1 Swing High (M5):** A candle whose high is higher than the highs of the 2 candles immediately before it AND the 2 candles immediately after it (3-candle fractal extended to 5-candle for M5 noise control). Confirmed only after the 2nd subsequent candle closes.

**1.2 Swing Low (M5):** Mirror of 1.1.

**1.3 BOS (Break of Structure):** An M5 candle **body close** beyond the most recent confirmed swing high (bullish BOS) or swing low (bearish BOS) in the direction of the prevailing structure. Wicks do not count.

**1.4 CHoCH (Change of Character):** An M5 candle **body close** beyond the most recent confirmed swing point *against* the prevailing structure. Bullish CHoCH = body close above the last lower high. Bearish CHoCH = body close below the last higher low.

**1.5 Liquidity Pool (qualified):** One of the following only:
- Asia session high or low (00:00–06:00 GMT range)
- Previous day high (PDH) or low (PDL), measured 00:00–00:00 GMT
- Previous week high/low
- London session high/low (07:00–12:00 GMT) — valid target/sweep source for the NY session
- Equal highs or equal lows: 2+ swing points within a tolerance of **1.5 pips (EU)** / **$0.50 (XAU)** of each other, at least 8 M5 candles apart

**1.6 Sweep:** Price trades through a qualified liquidity pool by any amount, AND within the sweeping candle or the next 3 M5 candles, a candle **body closes back on the original side** of the pool. If no close back within 3 candles → it is a breakout, not a sweep. No trade.

**1.7 Displacement:** An M5 candle within the CHoCH leg whose **body** (|close − open|) is larger than the body of **each** of the 6 preceding M5 candles, AND the leg leaves at least one FVG (1.8).

**1.8 FVG (Fair Value Gap):** A 3-candle sequence where candle 1's high is below candle 3's low (bullish FVG) or candle 1's low is above candle 3's high (bearish FVG). The gap between them is the FVG. Its midpoint = **CE (consequent encroachment)**.

**1.9 Order Block (OB):** The last opposite-direction candle (full range, wick to wick) immediately before the displacement move that produced the CHoCH. For a long: the last bearish candle before the up-displacement. Must be **unmitigated** — price has not traded back into its range since the displacement.

**1.10 POI (Point of Interest):** The FVG or OB formed by the CHoCH displacement leg. If both exist and overlap, the POI zone = the overlap. If both exist separately, the FVG is primary.

**1.11 Dealing Range:** The range from the sweep extreme (0%) to the CHoCH confirmation candle's close-side extreme (100%). **Discount** = lower 50% (longs must enter here). **Premium** = upper 50% (shorts must enter here, mirrored).

**1.12 Inducement:** At least one confirmed M5 swing point formed *after* the CHoCH, sitting between current price and the POI, whose stops will be run when price returns to the POI.

**1.13 Asia Range:** High minus low of 00:00–06:00 GMT.

**1.14 Chop Condition:** Within the last 24 M5 candles, there have been ≥2 bullish CHoCHs AND ≥2 bearish CHoCHs (structure flipping both ways), OR the total range of the last 12 M5 candles is smaller than 1.5× your planned stop distance. Either condition = chop = no trade.

**1.15 SMT Divergence:** At the moment instrument A sweeps its qualified pool, the correlated reference instrument fails to breach its equivalent level. References: EUR/USD ↔ GBP/USD; XAU/USD ↔ XAG/USD (or DXY inverse). Binary check at sweep time; no interpretation.

---

# SECTION 2 — SESSIONS & TRADEABLE WINDOWS

**2.1 London Kill Zone (LKZ): 07:00–10:00 GMT.** Entries permitted only in this window. Model: sweep of Asia high/low (or PDH/PDL if within 10 pips / $3 of the Asia extreme).

**2.2 New York Kill Zone (NYKZ): 12:00–15:00 GMT.** Entries permitted only in this window. Model: sweep of London session high/low, PDH/PDL, or the LKZ extreme.

**2.3 Order validity:** Pending limit orders may rest until 30 minutes after KZ close (10:30 / 15:30 GMT). Unfilled orders are cancelled at that time without exception.

**2.4 Hard flat time:** All positions closed by **19:30 GMT**, regardless of P&L or open runners. No overnight or weekend exposure, ever.

**2.5 Session disqualifiers — the entire session is untradeable if ANY apply:**

| # | Disqualifier | Objective test |
|---|---|---|
| D1 | Red-folder news for the instrument's currencies (USD, EUR for EU; USD for XAU) scheduled inside the KZ | No entries from 60 min before to 30 min after the release. If the blackout covers >50% of the KZ, skip the KZ entirely. Post-release entries allowed only if a fresh sweep + CHoCH forms entirely after the release. |
| D2 | FOMC decision day / NFP day / CPI day | NFP & CPI (12:30 GMT): LKZ tradeable, NYKZ tradeable only from 13:30 GMT onward with a fully post-news setup. FOMC day: no NYKZ trades at all (positioning distortion all afternoon). |
| D3 | Low-range Asia | EU: Asia range < 15 pips. XAU: Asia range < $5.00. (No pool worth sweeping; opens are random.) |
| D4 | Blown-out Asia | EU: Asia range > 70 pips. XAU: Asia range > $28.00. (News-driven overnight; the map is already invalid.) |
| D5 | Holiday liquidity | UK or US bank holiday, Dec 20–Jan 3 inclusive, Thursday–Friday of Thanksgiving week, Good Friday week Thu–Fri. |
| D6 | Friday NYKZ after 15:00 GMT | Already outside the window — stated for completeness. No new Friday risk after 15:00 GMT. |
| D7 | Spread condition | EU spread > 1.2 pips or XAU spread > $0.35 at intended execution → no entry until it normalizes. |

Recalibrate D3/D4 thresholds quarterly: recompute as the 20th and 95th percentile of the last 60 Asia ranges. This is a statistic computed off-chart, not an indicator.

---

# SECTION 3 — THE SCORING MODEL

Three **mandatory gates** sit outside the score. Fail any gate → no trade, even at 12/12.

**Gates (binary, all must be YES):**
- **G1:** Current time inside LKZ or NYKZ, and no session disqualifier (Section 2.5) active.
- **G2:** Planned stop distance inside the permitted band (Section 5.3).
- **G3:** Account risk limits not breached (Section 8) — daily loss, weekly loss, consecutive-loss breaker, trade-count caps.

**Scored factors (12 points available). Minimum to trade: ≥9/12, AND F1+F2+F3 must all score full marks (they are the structural spine — a 9 built without them is a different trade, not this system's trade).**

| # | Factor | Pts | Objective YES definition |
|---|---|---|---|
| F1 | HTF bias alignment | 2 | The most recent confirmed H1 structure break (body close beyond an H1 5-candle-fractal swing) is in the direction of the intended trade. |
| F2 | Qualified sweep | 2 | A pool from Definition 1.5 was swept per Definition 1.6 within the current KZ or the 60 minutes preceding it. |
| F3 | M5 CHoCH | 2 | Per Definition 1.4, confirmed within 12 M5 candles (60 min) of the sweep extreme. |
| F4 | Displacement + FVG | 1 | The CHoCH leg meets Definition 1.7. |
| F5 | Valid POI in correct zone | 1 | Unmitigated POI (1.10) whose entry price sits in discount (longs) / premium (shorts) of the dealing range (1.11). |
| F6 | Inducement present | 1 | Per Definition 1.12. |
| F7 | Target quality ≥ 2R | 1 | Distance from planned entry to the nearest qualified opposing liquidity pool ≥ 2.0× planned stop distance. Measured before entry, using exact prices. |
| F8 | Pool seniority | 1 | The swept pool is the Asia extreme, PDH/PDL, PWH/PWL, or equal highs/lows whose oldest touch is ≥ 4 hours old. |
| F9 | SMT divergence | 1 | Per Definition 1.15 at sweep time. |
| F10 | Session narrative match | 1 | LKZ trade sweeps the Asia extreme; NYKZ trade sweeps the London extreme, LKZ extreme, or PDH/PDL. |

**Decision rule:** Score ≥ 9 AND F1=2, F2=2, F3=2 AND all gates pass → trade is authorized. Anything else → stand down. There is no override in either direction.

---

# SECTION 4 — ENTRY RULES

**4.1 Primary execution — resting limit order:**
1. The moment the CHoCH candle closes (F3 confirmed), score the setup. If authorized, define the POI per 1.10.
2. Place a limit order at:
   - the **CE (midpoint) of the FVG**, if an FVG exists in the leg;
   - otherwise the **50% level of the OB** (midpoint of its full wick-to-wick range).
3. Stop loss and TP1 are placed simultaneously with the limit order (bracket order). No naked entries, ever.
4. Order validity: cancelled at KZ close + 30 min if unfilled (2.3).

**4.2 Pre-fill cancellation rules — cancel the pending order immediately if ANY occur:**
- An M5 candle **body closes** beyond the far edge of the POI (POI violated before fill).
- An opposing M5 CHoCH prints (structure flipped back).
- Price reaches 25% of the distance from the POI to TP1 without filling you (the move is leaving; chasing converts a positive-expectancy entry into a random one).
- A news blackout (D1) begins.

**4.3 Alternate execution — confirmation market entry (use ONLY if the limit could not be placed before price returned to the POI):**
- Price must be trading inside the POI zone, AND
- An M5 candle closes in the trade direction with its body ≥ 50% of its total range (rejection close), closing inside or beyond the POI toward the target.
- Enter at market on the open of the next candle. Stop placement unchanged (Section 5). If the resulting stop distance now violates the G2 band or drops F7 below 2R → the trade is void. Skip it.

**4.4 One attempt per setup.** If stopped out, the same sweep/POI may not be re-entered. A new trade requires a completely new sweep (F2) and new CHoCH (F3).

---

# SECTION 5 — STOP LOSS (DEFINED BEFORE ENTRY, ALWAYS)

**5.1 Structural placement:**
- Long: below the **sweep extreme low** (the lowest traded price of the liquidity grab — not the OB low, not the FVG edge).
- Short: above the **sweep extreme high**.
- Rationale: if price trades back through the sweep extreme, the reversal thesis is factually dead. Any tighter stop is inside noise; any wider stop is renting hope.

**5.2 Buffer sizing (no ATR — uses the trade's own structure):**
> Buffer = current spread + 15% of the sweep candle's total range (high−low),
> bounded by: EU floor 1.5 pips / cap 4.0 pips; XAU floor $0.40 / cap $1.50.

Final stop = sweep extreme ± buffer.

**5.3 Stop-distance band (Gate G2):** Total stop distance (entry to stop) must fall inside:
- EU: **5.0–15.0 pips**
- XAU: **$2.50–$9.00**

Below the floor → the setup is too compressed; spread and slippage consume the edge. Above the cap → the dealing range is too large for M5 execution; the same setup belongs on M15, which this system does not trade. Either way: no trade. Recalibrate the XAU band quarterly against the 60-day median NY-session range (off-chart statistic).

**5.4 The stop is never widened.** Under any circumstance, for any reason, ever. It may only move toward profit per Sections 6–7.

---
# SECTION 6 — EXITS

**6.1 TP1 — the expectancy anchor:**
- TP1 = **+2.0R** (exactly 2× stop distance from entry), OR the nearest qualified opposing liquidity pool if that pool sits between +2.0R and +2.5R — in which case TP1 is placed **2 pips (EU) / $0.60 (XAU) in front of** the pool, never at or beyond it (pools get front-run; orders resting at the pool itself often go unfilled by fractions).
- At TP1: close **50%** of the position.

**6.2 Break-even rule:**
- Stop moves to **entry + costs** (entry price + spread + commission-equivalent) **only after TP1 has filled.** Not at +1R, not "when it looks strong."
- Why: in this model, price routinely retests the POI after entry before running. A BE trigger at +1R converts a large share of eventual +2R/+4R winners into scratches. Backtest reality across sweep-reversal systems: early BE typically raises "not-a-loss" rate by ~10–15 points while cutting expectancy by 30–50%, because it amputates exactly the trades that pay for the strategy. BE after TP1 costs almost nothing (the trade has already banked +1R net) and removes tail risk on the runner.

**6.3 Runner (remaining 50%):**
- Final target: the **draw on liquidity** — the next qualified pool beyond TP1 (typically PDH/PDL, the opposing session extreme, or H1 equal highs/lows), again placed 2 pips / $0.60 in front.
- Structural trail: after each new **M5 BOS in the trade's direction** (body close beyond a confirmed swing), move the stop to just beyond the most recent confirmed M5 swing (± the Section 5.2 buffer). The stop only steps forward; it never waits at BE while structure advances.
- If the runner's final target is reached → flat. If trailed out → flat. If 19:30 GMT arrives → flat at market.

**6.4 Fixed-R vs. structural targets — why this hybrid:**
- Pure fixed-R ignores where liquidity actually sits; you routinely watch price tag the obvious pool 3 pips past your TP2 and reverse. Pure structural targets create unbounded variance and paralysis. The hybrid — fixed 2R floor for the first half, liquidity-based target for the second — captures the fat right tail (the 4R–6R sweeps that make the year) while guaranteeing that every winner banks something concrete.
- Effect on expectancy: the 50% partial lowers the average winner slightly (≈2.6R full-hold → ≈2.2–2.4R blended) but cuts equity-curve variance roughly in half and makes the daily-loss limits (Section 8) survivable psychology rather than theory. Consistency of execution is itself an expectancy input: a system you abandon in drawdown has an expectancy of zero.

**6.5 Hold vs. cut summary:**
- Between entry and TP1: HOLD. No manual exits (one exception: Section 7.3).
- After TP1: the trail rules decide. You do not.
- At 19:30 GMT: CUT, always.

---

# SECTION 7 — TRADE MANAGEMENT (POST-ENTRY)

**7.1 The never-intervene zone.** From fill until TP1, you may not touch the trade. Not to trim, not to add, not to "lock in a few pips." Every discretionary action inside this zone is a data-destroying event: it makes your live results untrackable against the ruleset.

**7.2 Mid-flight invalidation (mechanical, pre-TP1) — the stop is the invalidation.** The stop sits beyond the sweep extreme; there is no price-based reason to exit earlier, because no M5 close can occur beyond the sweep extreme without hitting the stop first. This is deliberate: the stop placement and the invalidation condition are the same object.

**7.3 The single manual-exit exception:** an **unscheduled** red-folder event (flash headline, central-bank surprise, geopolitical shock) breaks during an open trade → flatten everything at market immediately. Scheduled news never qualifies — it was either filtered (D1) or accepted pre-entry.

**7.4 No adding, no pyramiding, no averaging.** One position per setup, sized once, per Section 8.

**7.5 Post-trade logging (mandatory, same day):** instrument, session, direction, score sheet (all 10 factors + 3 gates), entry/stop/TP prices, R result, screenshot at entry and exit, and rule-compliance flag (YES only if zero deviations). Fewer than 100% logged trades = you are not trading this system.

---

# SECTION 8 — RISK & MONEY MANAGEMENT

**8.1 Position sizing formula:**

> Position size = (Account equity × Risk%) ÷ (Stop distance × value per pip/point per lot)

- EU example: equity $10,000, risk 1%, stop 8.0 pips → $100 ÷ (8 × $10/pip per standard lot) = **1.25 mini lots (0.125 std)**.
- XAU example: equity $10,000, risk 1%, stop $4.00 → $100 ÷ ($4.00 × $100 per 1-lot per $1) = **0.25 lots**.
- Round DOWN to the broker's step. Never up.

**8.2 Risk per trade:** 1.0% of current equity. During the first 40 live trades of the system (evaluation phase) and after any circuit-breaker event: **0.5%**.

**8.3 Loss limits (hard stops on YOU):**

| Limit | Threshold | Action |
|---|---|---|
| Max daily loss | −2.0% (2 full losses) | Flat, platform closed until next trading day |
| Max weekly loss | −4.0% | Flat, no trading until Monday |
| Consecutive losses, same session | 2 | Session over |
| Consecutive losses, running | 3 | Next session skipped entirely; resume at 0.5% risk until the next winner, then restore 1.0% |
| Max trades per Kill Zone | 2 | — |
| Max trades per day | 3 | — |
| Max concurrent positions | 2 total, max 1 per instrument | EU and XAU may be open simultaneously ONLY if their combined open risk ≤ 1.5% |

**8.4 Monthly drawdown brake:** if equity closes a month −6% or worse from its high-water mark, halt live trading; re-qualify with 20 consecutive rule-compliant demo/micro trades before resuming.

**8.5 Equity basis:** all percentages computed on the equity at the start of the current day, not intraday floating equity.

---

# SECTION 9 — ABSOLUTE FILTERS (NO TRADE REGARDLESS OF SCORE)

1. **Chop filter:** Definition 1.14 met → no trade until a fresh sweep occurs after the chop window.
2. **News blackout:** D1/D2 windows.
3. **Spread filter:** D7 breach at execution time.
4. **Stop-band filter:** G2 breach.
5. **Structure-quality filter:** the sweep candle itself IS the CHoCH candle AND its total range exceeds 60% of the entire dealing range → no trade (there is no meaningful POI; entry would be mid-candle noise).
6. **Missed-move filter:** rule 4.2c — price ran ≥25% of POI→TP1 distance before your order existed.
7. **Account-state filter:** any Section 8 limit tripped.
8. **Session disqualifiers:** D3–D6.
9. **Platform/connectivity filter:** if you cannot place the full bracket (entry+SL+TP) in one action, no trade.

---

# SECTION 10 — PRE-TRADE CHECKLIST (ALL 15 MUST BE "YES")

| # | Gate | Y/N |
|---|---|---|
| 1 | Time is inside LKZ (07:00–10:00 GMT) or NYKZ (12:00–15:00 GMT) | |
| 2 | No session disqualifier D1–D7 active | |
| 3 | Asia range inside the D3/D4 band | |
| 4 | No red news within −60/+30 min | |
| 5 | Chop condition (1.14) NOT met | |
| 6 | H1 bias supports direction (F1 = 2) | |
| 7 | Qualified pool swept per 1.6 (F2 = 2) | |
| 8 | M5 CHoCH confirmed within 12 candles of sweep (F3 = 2) | |
| 9 | Total score ≥ 9/12 | |
| 10 | POI defined, unmitigated, in correct premium/discount half | |
| 11 | Stop = sweep extreme ± buffer, distance inside G2 band | |
| 12 | TP1 ≥ 2.0R to a real level (F7 verified with exact prices) | |
| 13 | Position size computed by 8.1, rounded down | |
| 14 | Daily/weekly/consecutive-loss/trade-count limits all clear | |
| 15 | Bracket order (entry+SL+TP1) ready to submit as one unit | |

One "NO" anywhere = no trade. The checklist is completed in writing (or in the journal app) before order placement, every time.

---
# SECTION 11 — WORKED EXAMPLES

*(Prices are illustrative to demonstrate the mechanics; the arithmetic and rule application are exact.)*

## 11.1 Example A — A+ setup, TAKEN (EUR/USD, London KZ, long)

**Context:** Asia range 00:00–06:00 GMT = 1.0842–1.0870 (28 pips → D3/D4 pass). H1 printed a bullish BOS at 03:00 GMT (body close above the prior H1 swing high) — H1 bias is long. PDL sits at 1.0845, 3 pips above the Asia low: confluent pool below. No red news until US data at 12:30. GBP/USD's equivalent overnight low: 1.2618.

**Sequence:**
- 07:35 GMT: M5 candle spikes to 1.08385 — trades through the Asia low (1.0842) AND PDL (1.0845). The very next candle body-closes at 1.08455, back above both pools. → **Sweep confirmed (1.6).** GBP/USD's low of the same window: 1.2622 — it did NOT breach 1.2618. → **SMT present.**
- 07:50 GMT: an M5 candle with a 9-pip body (larger than each of the prior 6 bodies) closes at 1.08560 — body close above the last lower high at 1.08525. → **CHoCH + displacement.** The leg leaves a bullish FVG at 1.08470–1.08505 (CE = 1.084875) and an unmitigated OB (last bearish candle) at 1.08440–1.08475.
- A minor pullback at 07:55 forms a confirmed swing low at 1.08515 — inducement above the POI.
- Dealing range: sweep low 1.08385 (0%) → CHoCH close 1.08560 (100%). Midpoint = 1.084725. FVG CE at 1.084875 is... marginally above midpoint. **Check the rule exactly:** discount = lower 50%, i.e., entry must be ≤ 1.084725. CE 1.084875 fails by 1.5 pips → F5 as defined would score 0. However, the OB 50% level = 1.084575, which IS in discount. Per 1.10, FVG is primary *when it exists* — but F5 requires the entry price in discount. **Rule application:** entry moves to the OB 50% (the deeper POI qualifies; the system takes the compliant level, since 4.1.2 places the limit at the level that defines the scored POI). Entry = **1.08458**.

**Scoring:**

| Factor | Pts | Result |
|---|---|---|
| F1 H1 bias | 2 | ✅ 2 — H1 bullish BOS at 03:00 |
| F2 Sweep | 2 | ✅ 2 — Asia low + PDL swept, close-back in 1 candle |
| F3 CHoCH | 2 | ✅ 2 — body close 1.08560 > LH 1.08525, 3 candles after sweep |
| F4 Displacement+FVG | 1 | ✅ 1 |
| F5 POI in discount | 1 | ✅ 1 — OB 50% at 1.084575 ≤ midpoint 1.084725 |
| F6 Inducement | 1 | ✅ 1 — swing low 1.08515 |
| F7 Target ≥2R | 1 | ✅ 1 — see math below |
| F8 Pool seniority | 1 | ✅ 1 — Asia extreme + PDL |
| F9 SMT | 1 | ✅ 1 — GU held |
| F10 Session narrative | 1 | ✅ 1 — LKZ sweep of Asia extreme |
| **TOTAL** | **12** | **12/12, spine full** ✅ |

**Trade construction:**
- Sweep extreme: 1.08385. Sweep candle range: 11 pips. Buffer = spread 0.7 + 15%×11 = 0.7 + 1.65 = 2.35 → within 1.5–4.0 cap. Stop = 1.08385 − 0.00024 ≈ **1.08361**.
- Stop distance = 1.08458 − 1.08361 = **9.7 pips** → inside 5–15 band (G2 ✅).
- TP1: nearest opposing pool = Asia high 1.0870 → 24.2 pips away = 2.49R. Between 2.0R and 2.5R → TP1 = 1.0870 − 2 pips = **1.08680** (2.29R). Close 50% there.
- Runner target: PDH at 1.08925, minus 2 pips = **1.08905** (4.6R). Trail per 6.3.

**Outcome walk-through:** limit fills at 08:20 on the retrace (taking out the 1.08515 inducement on the way down — exactly the point of F6). TP1 fills 09:10 (+2.29R on half). Stop to 1.08465 (entry+costs). Two M5 BOS events trail the stop to 1.08610. Runner tags 1.08905 at 11:05. **Blended result ≈ +3.4R at 1% risk.**

---

## 11.2 Example B — Borderline setup, REJECTED BY SCORE (XAU/USD, NY KZ, short)

**Context:** London range 2,411.00–2,424.50. Asia range $9.80 (pass). H1 structure: last confirmed break was **bullish** at 09:00 GMT. No news in window. Silver at the reference moment made its own new high (no SMT).

**Sequence:**
- 12:40 GMT: price spikes to 2,426.10 — sweeps the London high 2,424.50; body close back below at 2,423.20 two candles later. Sweep ✅.
- 13:05 GMT: M5 body close at 2,419.70, below the last higher low 2,420.40 → bearish CHoCH ✅ (within 12 candles).
- The down-leg's largest body ($1.90) is NOT larger than all prior 6 bodies (a $2.30-body candle sits 4 back) and leaves no clean FVG → F4 = 0.
- OB at 2,423.40–2,424.90; its 50% = 2,424.15 → in premium ✅. No confirmed swing forms between price and the POI before the retrace begins → F6 = 0.

**Scoring:**

| Factor | Pts | Result |
|---|---|---|
| F1 H1 bias | 2 | ❌ 0 — H1 is bullish; this short fights it |
| F2 Sweep | 2 | ✅ 2 |
| F3 CHoCH | 2 | ✅ 2 |
| F4 Displacement+FVG | 1 | ❌ 0 |
| F5 POI premium | 1 | ✅ 1 |
| F6 Inducement | 1 | ❌ 0 |
| F7 Target ≥2R | 1 | ✅ 1 — London low ≈ 3.1R away |
| F8 Pool seniority | 1 | ✅ 1 — London high, ≥4h old |
| F9 SMT | 1 | ❌ 0 |
| F10 Narrative | 1 | ✅ 1 — NYKZ sweep of London high |
| **TOTAL** | **12** | **8/12 — and F1 = 0 (spine broken)** ❌ |

**Verdict:** fails twice — under 9, and the mandatory F1 isn't full. This is precisely the trade that *feels* fine in the moment (clean sweep, clean CHoCH, big room to target) and bleeds accounts over 100 repetitions: a counter-H1 short with no displacement is a pullback entry against an uptrend, not a reversal. **No trade. Log it as a scored skip.**

---

## 11.3 Example C — The trap: 10/12 score, KILLED BY A FILTER (EUR/USD, NY KZ, short)

**Context:** Beautiful morning map. H1 bearish. London high = week's equal highs (three touches within 1.2 pips). Asia range 31 pips.

**Sequence (13:35–13:55 GMT):** price sweeps the London high/equal-highs cluster, closes back inside in 2 candles, prints a bearish M5 CHoCH with a huge displacement candle and a textbook FVG in premium, inducement swing formed, GU made a higher high while EU's cluster held on the second push (SMT ✅), target = PDL at 3.4R.

**Score: 10/12** (drops only F8-adjacent nuance and one minor factor — the spine F1/F2/F3 all full). By score alone: authorized.

**The filter check (checklist row 4):** US retail sales + a scheduled Fed speaker sit at **14:30 GMT**. Intended entry time ≈ 13:55; the limit order would rest *into* the −60 min blackout (13:30–15:00 relative to 14:30). Rule D1: no entries from 60 min before the release. The order may not be placed.

**What the trap looks like in real time:** the setup is genuinely good — that's what makes it a trap. Pre-news engineered moves like this frequently ARE the inducement: the algorithm runs the obvious short into 14:30, then the release spikes 25 pips through the sweep extreme, stops the position at maximum slippage, and *then* delivers the original idea. You cannot know which variant you'll get; the filter exists because the distribution of outcomes through red news is not the distribution your edge was measured on. **No trade. Not at 10/12, not at 12/12.**

---

# SECTION 12 — HONEST PERFORMANCE PROFILE (READ BEFORE RISKING MONEY)

**12.1 What this style realistically produces:**
- **Win rate: 35–45%.** Sweep-reversal limit-entry models miss fills, get stopped by deeper sweeps, and take full −1R losses by design. Anyone quoting 70–80% for this style is either martingaling, moving stops, or selling something.
- **Average winner (blended, with the 50/50 partial structure): ≈ 2.2–2.6R.** Average loser: −1R by construction (occasionally −1.05R with slippage on XAU).
- **Expectancy math:** at 40% WR × 2.3R avg win: (0.40 × 2.3) − (0.60 × 1.0) = **+0.32R per trade** before costs; ≈ +0.25R to +0.30R after spread/slippage. At 2–3 authorized trades per day, ~35–45 trades/month, that is roughly **+9R to +13R per month in a good regime**, with flat-to-negative months guaranteed to occur (a 40% WR system produces 5+ consecutive losses about once every ~80 trades by pure binomial math — roughly once every two months at this frequency; the Section 8 breakers exist for exactly that).
- **Maximum expected drawdown at 1% risk:** 8–12R episodes are normal, not evidence of failure. The monthly −6% brake fires before variance becomes ruin.

**12.2 The win-rate/expectancy trade-off, stated plainly:** you can raise this system's win rate — take profit at 1R, move to BE early, enter on M1 confirmation only. Every one of those changes raises the percentage of green rows in your journal and *lowers* the money the system makes, because each one systematically sells off the right tail (the 3R–5R runners) that funds the losers. Cosmetic win rate is what traders optimize when they're managing their feelings; expectancy per trade × trades per month × survival is what compounds. This rulebook deliberately accepts being wrong most of the time in exchange for being paid asymmetrically when right. If a sub-50% win rate is psychologically unacceptable, do not modify this system to fix that — trade a different system.

**12.3 Validation requirement before live capital:** 60 recorded demo/backtest trades under these exact rules with ≥95% rule-compliance, then 40 live trades at 0.5% risk (8.2). Only then 1%. The edge is unproven for *you* until your own log proves it.

---

# SECTION 13 — DECISION FLOWCHART (TEXT FORM)

```
START (every trading day, 06:45 GMT)
│
├─ IF UK/US holiday OR Dec 20–Jan 3 OR D5 window → NO TRADING TODAY. END.
├─ IF weekly loss ≥ 4% OR monthly brake fired → NO TRADING. END.
│
├─ 06:45: Mark the map → Asia H/L, PDH/PDL, PWH/PWL, equal H/L clusters,
│         H1 bias (last confirmed H1 body-close break), red-news times.
│
├─ IF Asia range outside D3/D4 band → SKIP LONDON KZ (re-check map for NY).
│
├─ ENTER KILL ZONE (07:00 or 12:00 GMT):
│   │
│   ├─ IF daily loss ≥ 2% OR 2 consecutive session losses
│   │    OR 3 running losses OR trade caps hit → SIT OUT. END SESSION.
│   │
│   ├─ WAIT: has a qualified pool been swept (Def 1.6)?
│   │    ├─ NO, and KZ has ended → END SESSION. No sweep = no trade.
│   │    └─ YES ↓
│   │
│   ├─ WAIT ≤ 12 M5 candles: M5 CHoCH (Def 1.4)?
│   │    ├─ NO within 12 candles → setup void. Wait for a NEW sweep.
│   │    └─ YES ↓
│   │
│   ├─ IF chop condition (1.14) → VOID. Wait for new sweep after chop.
│   ├─ IF news blackout covers entry/rest window → VOID (Example C).
│   │
│   ├─ SCORE all 10 factors.
│   │    ├─ IF score < 9 OR any of F1/F2/F3 not full → LOG SKIP. Wait.
│   │    └─ IF score ≥ 9 AND spine full ↓
│   │
│   ├─ CONSTRUCT: POI level → stop (5.1–5.2) → check G2 band
│   │    → verify F7 with exact prices → size (8.1).
│   │    ├─ IF any construction check fails → VOID. LOG SKIP.
│   │    └─ ELSE ↓
│   │
│   ├─ SUBMIT bracket limit (entry + SL + TP1, one action).
│   │
│   ├─ WHILE unfilled:
│   │    ├─ IF body close beyond POI far edge OR opposing CHoCH
│   │    │    OR 25%-to-TP1 run OR KZ+30min → CANCEL.
│   │    └─ IF filled ↓
│   │
│   ├─ MANAGE:
│   │    ├─ Before TP1 → NO ACTION (only exception: unscheduled red news → flatten).
│   │    ├─ TP1 fills → close 50%, stop → entry+costs.
│   │    ├─ Each new same-direction M5 BOS → trail stop behind last swing + buffer.
│   │    └─ Runner: exit at final target, trail-out, or 19:30 GMT — whichever first.
│   │
│   └─ LOG the trade fully. Update daily/weekly counters.
│
└─ 19:30 GMT: FLAT. Journal review. END.
```

---

# SECTION 14 — THE NUMBERED RULEBOOK (ONE-PAGE MECHANICAL SUMMARY)

1. Trade only 07:00–10:00 and 12:00–15:00 GMT; flat by 19:30 GMT.
2. Skip any session failing D1–D7.
3. Mark Asia H/L, PDH/PDL, PWH/PWL, equal H/L, H1 bias, news — before 07:00 GMT.
4. Trade only a qualified sweep (1.6) followed by an M5 CHoCH (1.4) within 12 candles.
5. Score the setup; require ≥9/12 with F1, F2, F3 at full marks; all gates green.
6. Enter by limit at FVG CE, else OB 50% — always inside discount (longs) / premium (shorts).
7. Bracket every order: stop beyond the sweep extreme + buffer (5.2); distance inside G2 band.
8. TP1 at 2R (or a pool between 2–2.5R, fronted); close 50%; BE only after TP1 fills.
9. Trail the runner by M5 structure to the draw on liquidity; front all pool targets.
10. Never touch a trade between fill and TP1; never widen a stop; never re-enter a used sweep.
11. Risk 1% (0.5% in evaluation/recovery); size by formula 8.1, rounded down.
12. Stop at −2% day, −4% week, 2 losses/session, 3 running losses, 3 trades/day.
13. Cancel unfilled orders at KZ+30 min; cancel on POI violation, opposing CHoCH, or 25% run.
14. Log 100% of trades and scored skips, same day.
15. Any situation not covered by a rule = no trade. Silence in the rulebook means NO.

---

*End of playbook. Version 1.0 — recalibrate D3/D4 and G2 bands quarterly from the trailing 60-session statistics; all other rules are frozen for a minimum of 100 logged trades before any revision is permitted.*
