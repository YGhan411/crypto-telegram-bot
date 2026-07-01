def detect_pd_zone(candles, lookback=30):
    if len(candles) < lookback:
        return "⚪ Veri Yok"

    highs = [c["high"] for c in candles[-lookback:]]
    lows = [c["low"] for c in candles[-lookback:]]

    swing_high = max(highs)
    swing_low = min(lows)

    current_price = candles[-1]["close"]
    equilibrium = (swing_high + swing_low) / 2

    if current_price < equilibrium:
        return "🟢 Discount Zone"
    elif current_price > equilibrium:
        return "🔴 Premium Zone"
    else:
        return "🟡 Equilibrium"