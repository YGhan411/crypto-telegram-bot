def calculate_volume_change(candles, period=20):
    if len(candles) < period + 1:
        return 0

    recent_volume = candles[-1]["volume"]
    avg_volume = sum(c["volume"] for c in candles[-period-1:-1]) / period

    if avg_volume <= 0:
        return 0

    return ((recent_volume - avg_volume) / avg_volume) * 100