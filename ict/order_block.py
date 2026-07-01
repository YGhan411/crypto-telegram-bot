def detect_order_block(candles, lookback=20):
    if len(candles) < lookback + 2:
        return "⚪ Veri Yok"

    recent = candles[-lookback:]

    for i in range(len(recent) - 2, 1, -1):
        prev_candle = recent[i - 1]
        current_candle = recent[i]

        prev_open = prev_candle["open"]
        prev_close = prev_candle["close"]

        current_open = current_candle["open"]
        current_close = current_candle["close"]

        # Bullish Order Block
        if prev_close < prev_open and current_close > current_open:
            body_strength = abs(current_close - current_open)
            prev_body = abs(prev_close - prev_open)

            if body_strength > prev_body * 1.2:
                return "🟢 Bullish Order Block"

        # Bearish Order Block
        if prev_close > prev_open and current_close < current_open:
            body_strength = abs(current_close - current_open)
            prev_body = abs(prev_close - prev_open)

            if body_strength > prev_body * 1.2:
                return "🔴 Bearish Order Block"

    return "🟡 Order Block Yok"