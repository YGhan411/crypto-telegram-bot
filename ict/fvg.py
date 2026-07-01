def detect_fvg(candles, lookback=10):
    if len(candles) < 3:
        return "⚪ Veri Yok"

    recent = candles[-lookback:] if len(candles) >= lookback else candles

    bullish_fvg = None
    bearish_fvg = None

    for i in range(2, len(recent)):
        c1 = recent[i - 2]
        c2 = recent[i - 1]
        c3 = recent[i]

        # Bullish FVG:
        # 1. mumun high'ı ile 3. mumun low'u arasında boşluk
        if c1["high"] < c3["low"]:
            bullish_fvg = {
                "low": c1["high"],
                "high": c3["low"]
            }

        # Bearish FVG:
        # 1. mumun low'u ile 3. mumun high'ı arasında boşluk
        if c1["low"] > c3["high"]:
            bearish_fvg = {
                "low": c3["high"],
                "high": c1["low"]
            }

    last_close = candles[-1]["close"]

    if bullish_fvg:
        if bullish_fvg["low"] <= last_close <= bullish_fvg["high"]:
            return "🟢 Bullish FVG İçinde"
        return "🟢 Bullish FVG Var"

    if bearish_fvg:
        if bearish_fvg["low"] <= last_close <= bearish_fvg["high"]:
            return "🔴 Bearish FVG İçinde"
        return "🔴 Bearish FVG Var"

    return "🟡 FVG Yok"