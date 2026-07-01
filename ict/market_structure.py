def detect_scalp_market_structure(closes, lookback=30):
    if len(closes) < lookback + 5:
        return "⚪ Veri Yok"

    recent = closes[-lookback:]

    previous_high = max(recent[:-5])
    previous_low = min(recent[:-5])

    current_price = recent[-1]
    previous_price = recent[-5]

    if current_price > previous_high:
        return "🟢 Bullish BOS"

    elif current_price < previous_low:
        return "🔴 Bearish BOS"

    elif current_price > previous_price and previous_price <= previous_low * 1.01:
        return "🟢 Bullish CHoCH"

    elif current_price < previous_price and previous_price >= previous_high * 0.99:
        return "🔴 Bearish CHoCH"

    return "🟡 Range / Belirsiz"