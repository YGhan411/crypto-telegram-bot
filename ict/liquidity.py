def detect_liquidity_sweep(candles, lookback=20):
    if len(candles) < lookback + 2:
        return "⚪ Veri Yok"

    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    closes = [c["close"] for c in candles]

    recent_high = max(highs[-lookback-1:-1])
    recent_low = min(lows[-lookback-1:-1])

    last_high = highs[-1]
    last_low = lows[-1]
    last_close = closes[-1]

    if last_low < recent_low and last_close > recent_low:
        return "🟢 Sell-side Liquidity Sweep"

    if last_high > recent_high and last_close < recent_high:
        return "🔴 Buy-side Liquidity Sweep"

    return "🟡 Sweep Yok"
def detect_liquidity_sweep_v2(candles, lookback=30):
    if len(candles) < lookback + 5:
        return {
            "type": "⚪ Veri Yok",
            "score": 0,
            "swept_level": None
        }

    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    closes = [c["close"] for c in candles]

    recent_high = max(highs[-lookback-1:-1])
    recent_low = min(lows[-lookback-1:-1])

    last_high = highs[-1]
    last_low = lows[-1]
    last_close = closes[-1]

    if last_low < recent_low and last_close > recent_low:
        return {
            "type": "🟢 Sell-side Sweep V2",
            "score": 3,
            "swept_level": recent_low
        }

    if last_high > recent_high and last_close < recent_high:
        return {
            "type": "🔴 Buy-side Sweep V2",
            "score": 3,
            "swept_level": recent_high
        }

    return {
        "type": "🟡 Sweep Yok",
        "score": 0,
        "swept_level": None
    }