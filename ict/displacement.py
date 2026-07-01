def detect_displacement(candles, lookback=20):
    if len(candles) < lookback + 1:
        return {
            "type": "⚪ Veri Yok",
            "score": 0,
            "strength": 0
        }

    recent = candles[-lookback:]

    bodies = [
        abs(c["close"] - c["open"])
        for c in recent[:-1]
    ]

    avg_body = sum(bodies) / len(bodies)

    last = recent[-1]
    last_body = abs(last["close"] - last["open"])
    candle_range = last["high"] - last["low"]

    if candle_range == 0 or avg_body == 0:
        return {
            "type": "⚪ Veri Yok",
            "score": 0,
            "strength": 0
        }

    body_ratio = last_body / candle_range
    strength = last_body / avg_body

    if last["close"] > last["open"] and strength >= 1.8 and body_ratio >= 0.6:
        return {
            "type": "🟢 Bullish Displacement",
            "score": 3,
            "strength": round(strength, 2)
        }

    if last["close"] < last["open"] and strength >= 1.8 and body_ratio >= 0.6:
        return {
            "type": "🔴 Bearish Displacement",
            "score": 3,
            "strength": round(strength, 2)
        }

    return {
        "type": "🟡 Displacement Yok",
        "score": 0,
        "strength": round(strength, 2)
    }