from indicators.atr import calculate_atr

from ict.market_structure import detect_scalp_market_structure
from ict.liquidity import detect_liquidity_sweep, detect_liquidity_sweep_v2
from ict.fvg import detect_fvg
from ict.order_block import detect_order_block
from ict.pd_zone import detect_pd_zone


def analyze_ict_setup(
    symbol,
    get_klines_func,
    get_timeframes_func,
    interval="15"
):
    candles = get_klines_func(symbol, interval=interval, limit=100)

    if len(candles) < 50:
        return None

    closes = [c["close"] for c in candles]

    current_price = closes[-1]
    previous_close = closes[-2]
    recent_high = max(closes[-20:])
    recent_low = min(closes[-20:])

    breakout = "🟡 Yok"

    if current_price >= recent_high * 0.999:
        breakout = "🚀 Yukarı Kırılım"
    elif current_price <= recent_low * 1.001:
        breakout = "🔴 Aşağı Kırılım"

    last_momentum = ((current_price - previous_close) / previous_close) * 100
    timeframe_confirmations = get_timeframes_func(symbol)

    market_structure = detect_scalp_market_structure(closes)
    liquidity_sweep = detect_liquidity_sweep(candles)
    liquidity_v2 = detect_liquidity_sweep_v2(candles)
    fvg = detect_fvg(candles)
    order_block = detect_order_block(candles)
    pd_zone = detect_pd_zone(candles)
    atr = calculate_atr(candles)

    ict_score = 0
    reasons = []

    if market_structure in ["🟢 Bullish BOS", "🔴 Bearish BOS"]:
        ict_score += 2
        reasons.append("BOS tespit edildi")
    elif market_structure in ["🟢 Bullish CHoCH", "🔴 Bearish CHoCH"]:
        ict_score += 3
        reasons.append("CHoCH tespit edildi")

    if liquidity_v2["score"] > 0:
        ict_score += liquidity_v2["score"]
        reasons.append("Liquidity Sweep V2 tespit edildi")

    if fvg in ["🟢 Bullish FVG İçinde", "🔴 Bearish FVG İçinde"]:
        ict_score += 2
        reasons.append("FVG içinde fiyatlanıyor")
    elif fvg in ["🟢 Bullish FVG Var", "🔴 Bearish FVG Var"]:
        ict_score += 1
        reasons.append("FVG bulundu")

    if order_block in ["🟢 Bullish Order Block", "🔴 Bearish Order Block"]:
        ict_score += 2
        reasons.append("Order Block tespit edildi")

    if pd_zone in ["🟢 Discount Zone", "🔴 Premium Zone"]:
        ict_score += 1
        reasons.append("Premium / Discount bölgesi tespit edildi")

    ict_score = min(ict_score, 10)

    long_score = 0
    short_score = 0

    if market_structure == "🟢 Bullish BOS":
        long_score += 2
    elif market_structure == "🔴 Bearish BOS":
        short_score += 2
    elif market_structure == "🟢 Bullish CHoCH":
        long_score += 3
    elif market_structure == "🔴 Bearish CHoCH":
        short_score += 3

    if liquidity_v2["type"] == "🟢 Sell-side Sweep V2":
        long_score += 3
    elif liquidity_v2["type"] == "🔴 Buy-side Sweep V2":
        short_score += 3

    if fvg in ["🟢 Bullish FVG İçinde", "🟢 Bullish FVG Var"]:
        long_score += 2
    elif fvg in ["🔴 Bearish FVG İçinde", "🔴 Bearish FVG Var"]:
        short_score += 2

    if order_block == "🟢 Bullish Order Block":
        long_score += 2
    elif order_block == "🔴 Bearish Order Block":
        short_score += 2

    if pd_zone == "🟢 Discount Zone":
        long_score += 1
    elif pd_zone == "🔴 Premium Zone":
        short_score += 1

    if long_score >= short_score + 2:
        signal_side = "🟢 LONG"
    elif short_score >= long_score + 2:
        signal_side = "🔴 SHORT"
    else:
        signal_side = "🟡 NÖTR"

    setup_power = min(100, ict_score * 10)

    if atr is None:
        stop = current_price * 0.995
        target1 = current_price * 1.006
        target2 = current_price * 1.012
        rr = 1.5
    else:
        if signal_side == "🔴 SHORT":
            stop = current_price + (atr * 1.2)
            target1 = current_price - (atr * 1.5)
            target2 = current_price - (atr * 2.5)
            rr = (current_price - target2) / (stop - current_price)
        else:
            stop = current_price - (atr * 1.2)
            target1 = current_price + (atr * 1.5)
            target2 = current_price + (atr * 2.5)
            rr = (target2 - current_price) / (current_price - stop)

    return {
        "symbol": symbol,
        "candles": candles,
        "closes": closes,
        "current_price": current_price,
        "previous_close": previous_close,
        "market_structure": market_structure,
        "liquidity_sweep": liquidity_sweep,
        "liquidity_v2": liquidity_v2,
        "fvg": fvg,
        "order_block": order_block,
        "pd_zone": pd_zone,
        "atr": atr,
        "breakout": breakout,
        "last_momentum": last_momentum,
        "timeframe_confirmations": timeframe_confirmations,
        "ict_score": ict_score,
        "reasons": reasons,
        "signal_side": signal_side,
        "long_score": long_score,
        "short_score": short_score,
        "setup_power": setup_power,
        "stop": stop,
        "target1": target1,
        "target2": target2,
        "rr": rr,
    }