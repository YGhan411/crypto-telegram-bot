def detect_equal_high_low(candles, lookback=30, tolerance=0.0015):
    if len(candles) < lookback:
        return {
            "type": "⚪ Veri Yok",
            "score": 0,
            "level": None
        }

    highs = [c["high"] for c in candles[-lookback:]]
    lows = [c["low"] for c in candles[-lookback:]]

    last_high = highs[-1]
    last_low = lows[-1]

    previous_highs = highs[:-1]
    previous_lows = lows[:-1]

    equal_high = None
    equal_low = None

    for h in previous_highs:
        if abs(last_high - h) / h <= tolerance:
            equal_high = h
            break

    for l in previous_lows:
        if abs(last_low - l) / l <= tolerance:
            equal_low = l
            break

    if equal_high:
        return {
            "type": "🔴 Equal High Liquidity",
            "score": 2,
            "level": equal_high
        }

    if equal_low:
        return {
            "type": "🟢 Equal Low Liquidity",
            "score": 2,
            "level": equal_low
        }

    return {
        "type": "🟡 Equal High/Low Yok",
        "score": 0,
        "level": None
    }