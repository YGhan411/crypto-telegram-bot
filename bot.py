import os
import time
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")

volume_memory = {}
volume_cooldown = {}
whale_memory = {}
whale_cooldown = {}
whale_pro_memory = {}
whale_pro_cooldown = {}
whale_v2_memory = {}
whale_v2_cooldown = {}
ta_cooldown = {}
trade_scan_cooldown = {}
scalp_cooldown = {}
price_cache = {}

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable bulunamadı.")


def fetch_markets(order="market_cap_desc", per_page=100):
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": order,
        "per_page": per_page,
        "page": 1,
        "sparkline": "false"
    }
    r = requests.get(url, params=params, timeout=20)
    if r.status_code != 200:
        raise Exception(f"CoinGecko API hatası: {r.status_code}")
    return r.json()


def get_coin(coin_id):
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {"vs_currency": "usd", "ids": coin_id.lower()}
    r = requests.get(url, params=params, timeout=20)
    if r.status_code != 200:
        raise Exception(f"CoinGecko API hatası: {r.status_code}")
    data = r.json()
    return data[0] if data else None
def get_prices_for_ta(coin_id):
    global price_cache

    now = time.time()

    cache = price_cache.get(coin_id)

    if cache:
        cache_time = cache["time"]

        if now - cache_time < 300:
            return cache["prices"]

    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"

    params = {
        "vs_currency": "usd",
        "days": 7,
        "interval": "hourly"
    }

    r = requests.get(
        url,
        params=params,
        timeout=20
    )

    if r.status_code != 200:
        raise Exception(
            f"TA veri hatası: {r.status_code}"
        )

    data = r.json()

    prices = [
        item[1]
        for item in data.get("prices", [])
    ]

    price_cache[coin_id] = {
        "time": now,
        "prices": prices
    }

    return prices
def calculate_ema(prices, period):
    if len(prices) < period:
        return None

    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period

    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema

    return ema


def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None

    gains = []
    losses = []

    for i in range(1, period + 1):
        change = prices[i] - prices[i - 1]

        if change >= 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_macd(prices):
    ema12 = calculate_ema(prices, 12)
    ema26 = calculate_ema(prices, 26)

    if ema12 is None or ema26 is None:
        return None

    return ema12 - ema26

def to_okx_symbol(symbol):
    return f"{symbol.upper()}-USDT-SWAP"


def get_bybit_klines(symbol, interval="15", limit=100):
    url = "https://www.okx.com/api/v5/market/candles"

    params = {
        "instId": to_okx_symbol(symbol),
        "bar": f"{interval}m",
        "limit": limit
    }

    r = requests.get(url, params=params, timeout=15)

    if r.status_code != 200:
        raise Exception(f"OKX kline hatası: {r.status_code}")

    data = r.json()

    items = data.get("data", [])

    if not items:
        return []

    candles = []

    for item in reversed(items):
        candles.append({
            "time": item[0],
            "open": float(item[1]),
            "high": float(item[2]),
            "low": float(item[3]),
            "close": float(item[4]),
            "volume": float(item[5])
        })

    return candles
   


def calculate_volume_change(candles, period=20):
    if len(candles) < period + 1:
        return 0

    recent_volume = candles[-1]["volume"]
    avg_volume = sum(c["volume"] for c in candles[-period-1:-1]) / period

    if avg_volume <= 0:
        return 0

    return ((recent_volume - avg_volume) / avg_volume) * 100
def calculate_atr(candles, period=14):
    if len(candles) < period + 1:
        return None

    true_ranges = []

    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i - 1]["close"]

        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        true_ranges.append(tr)

    if len(true_ranges) < period:
        return None

    atr_values = true_ranges[-period:]
    return sum(atr_values) / len(atr_values)
def analyze_scalp_timeframe(symbol, interval):
    try:
        candles = get_bybit_klines(symbol, interval=interval, limit=100)

        if len(candles) < 50:
            return "⚪ Veri Yok"

        closes = [c["close"] for c in candles]

        rsi = calculate_rsi(closes)
        ema9 = calculate_ema(closes, 9)
        ema21 = calculate_ema(closes, 21)
        ema50 = calculate_ema(closes, 50)
        ema200 = calculate_ema(closes, 200)
        macd = calculate_macd(closes)
        volume_change = calculate_volume_change(candles)

        if ema9 is None or ema21 is None or macd is None:
            return "⚪ Veri Yok"

        if ema9 > ema21 and macd > 0:
            return "🟢 Pozitif"
        elif ema9 < ema21 and macd < 0:
            return "🔴 Negatif"
        else:
            return "🟡 Kararsız"

    except Exception:
        return "⚪ Veri Yok"


def get_scalp_timeframe_confirmations(symbol):
    return {
        "5m": analyze_scalp_timeframe(symbol, "5"),
        "15m": analyze_scalp_timeframe(symbol, "15"),
        "1H": analyze_scalp_timeframe(symbol, "60")
    }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 CoinGecko Kripto Botu\n\n"
        "Komutlar:\n"
        "/price bitcoin\n"
        "/volume bitcoin\n"
        "/topvolume\n"
        "/scan\n"
        "/gainers\n"
        "/losers\n"
        "/alarm_on\n"
        "/alarm_off"
        "/settings\n"
        "/whale_on\n"
        "/whale_off\n"
        "/whale_status\n"
        "/whale_pro_on\n"
        "/whale_pro_off\n"
        "/whale_pro_status\n"
        "/whale_v2_on\n"
        "/whale_v2_off\n"
        "/whale_v2_status\n"
        "/ta bitcoin\n"
        "/ta_on\n"
        "/ta_off\n"
        "/ta_status\n"
        "/trade bitcoin\n"
        "/trade_scan_on\n"
        "/trade_scan_off\n"
        "/trade_scan_status\n"
        "/scalp btc\n"
        "/scalp_on\n"
        "/scalp_off\n"
        "/scalp_status\n"
    )


async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Örnek: /price bitcoin")
        return

    try:
        coin = get_coin(context.args[0])
        if not coin:
            await update.message.reply_text("❌ Coin bulunamadı.")
            return

        await update.message.reply_text(
            f"💰 {coin['name']}\n\n"
            f"Fiyat: ${coin['current_price']:,.4f}"
        )
    except Exception as e:
        await update.message.reply_text(f"Hata:\n{e}")


async def volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Örnek: /volume bitcoin")
        return

    try:
        coin = get_coin(context.args[0])
        if not coin:
            await update.message.reply_text("❌ Coin bulunamadı.")
            return

        change = coin.get("price_change_percentage_24h") or 0

        await update.message.reply_text(
            f"📊 {coin['name']}\n\n"
            f"Fiyat: ${coin['current_price']:,.4f}\n"
            f"24 Saatlik Hacim: ${coin['total_volume']:,.0f}\n"
            f"24 Saatlik Değişim: %{change:.2f}\n"
            f"Piyasa Değeri: ${coin['market_cap']:,.0f}"
        )
    except Exception as e:
        await update.message.reply_text(f"Hata:\n{e}")


async def topvolume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = fetch_markets(order="volume_desc", per_page=10)
        text = "🔥 En Yüksek Hacimli Coinler\n\n"

        for i, coin in enumerate(data, start=1):
            text += (
                f"{i}. {coin['symbol'].upper()} - {coin['name']}\n"
                f"   Hacim: ${coin['total_volume'] / 1_000_000_000:.2f}B\n\n"
            )

        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"Hata:\n{e}")


async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = fetch_markets(order="volume_desc", per_page=100)
        print(f"Volume Scanner: {len(data)} coin çekildi")
        
        alerts = []

        candidates = [
            coin for coin in data
            if coin.get("price_change_percentage_24h") is not None
            and coin["price_change_percentage_24h"] > 5
            and coin["total_volume"] > 50_000_000
        ]

        candidates = sorted(
            candidates,
            key=lambda x: x["price_change_percentage_24h"],
            reverse=True
        )[:10]

        text = "🚀 Momentum Tarayıcı\n\n"

        if not candidates:
            text += "Uygun coin bulunamadı."

        for coin in candidates:
            text += (
                f"{coin['symbol'].upper()} - {coin['name']}\n"
                f"24s Değişim: %{coin['price_change_percentage_24h']:.2f}\n"
                f"Hacim: ${coin['total_volume']:,.0f}\n\n"
            )

        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"Hata:\n{e}")


async def gainers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = fetch_markets(order="market_cap_desc", per_page=100)

        coins = [
            coin for coin in data
            if coin.get("price_change_percentage_24h") is not None
        ]

        top = sorted(
            coins,
            key=lambda x: x["price_change_percentage_24h"],
            reverse=True
        )[:10]

        text = "🚀 TOP GAINERS (24 Saat)\n\n"

        for i, coin in enumerate(top, start=1):
            text += (
                f"{i}. {coin['symbol'].upper()} - {coin['name']}\n"
                f"📈 %{coin['price_change_percentage_24h']:.2f}\n"
                f"💰 ${coin['current_price']:,.4f}\n\n"
            )

        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"Hata:\n{e}")


async def losers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = fetch_markets(order="market_cap_desc", per_page=100)

        coins = [
            coin for coin in data
            if coin.get("price_change_percentage_24h") is not None
        ]

        bottom = sorted(
            coins,
            key=lambda x: x["price_change_percentage_24h"]
        )[:10]

        text = "📉 TOP LOSERS (24 Saat)\n\n"

        for i, coin in enumerate(bottom, start=1):
            text += (
                f"{i}. {coin['symbol'].upper()} - {coin['name']}\n"
                f"📉 %{coin['price_change_percentage_24h']:.2f}\n"
                f"💰 ${coin['current_price']:,.4f}\n\n"
            )

        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"Hata:\n{e}")

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        url = "https://api.coingecko.com/api/v3/search/trending"
        data = requests.get(url, timeout=20).json()

        coins = data.get("coins", [])[:10]

        if not coins:
            await update.message.reply_text("Trend coin bulunamadı.")
            return

        text = "🔥 TRENDING COINS\n\n"

        for i, item in enumerate(coins, start=1):
            coin = item["item"]

            text += (
                f"{i}. {coin['symbol'].upper()} - {coin['name']}\n"
                f"Market Cap Rank: {coin.get('market_cap_rank', 'N/A')}\n\n"
            )

        await update.message.reply_text(text)

    except Exception as e:
        await update.message.reply_text(f"Hata:\n{e}")
async def smart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = fetch_markets(order="volume_desc", per_page=100)

        signals = []

        for coin in data:
            change = coin.get("price_change_percentage_24h")
            volume = coin.get("total_volume")
            market_cap_rank = coin.get("market_cap_rank")
            price = coin.get("current_price")

            if change is None or volume is None or market_cap_rank is None:
                continue

            if volume < 50_000_000:
                continue

            score = 0

            if change > 3:
                score += 2
            if change > 7:
                score += 3
            if change > 12:
                score += 2

            if volume > 100_000_000:
                score += 2
            if volume > 500_000_000:
                score += 2
            if volume > 1_000_000_000:
                score += 2

            if market_cap_rank <= 100:
                score += 2
            if market_cap_rank <= 50:
                score += 1

            if change > 0 and volume > 100_000_000:
                score += 2

            if score >= 7:
                signals.append({
                    "symbol": coin["symbol"].upper(),
                    "name": coin["name"],
                    "price": price,
                    "change": change,
                    "volume": volume,
                    "rank": market_cap_rank,
                    "score": score
                })

        signals = sorted(
            signals,
            key=lambda x: x["score"],
            reverse=True
        )[:10]

        if not signals:
            await update.message.reply_text("Şu an güçlü akıllı sinyal bulunamadı.")
            return

        text = "🧠 AKILLI SİNYAL TARAMASI\n\n"

        for i, coin in enumerate(signals, start=1):
            text += (
                f"{i}. 🪙 {coin['symbol']} - {coin['name']}\n"
                f"💰 Fiyat: ${coin['price']:,.4f}\n"
                f"📈 24s Değişim: %{coin['change']:.2f}\n"
                f"📊 Hacim: ${coin['volume']:,.0f}\n"
                f"🏆 Rank: {coin['rank']}\n"
                f"⭐ Sinyal Skoru: {coin['score']}/14\n\n"
            )

        text += "⚠️ Bu finansal tavsiye değildir."

        await update.message.reply_text(text)

    except Exception as e:
        await update.message.reply_text(f"Hata:\n{e}")
async def ta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Örnek kullanım:\n/ta bitcoin")
        return

    coin_id = context.args[0].lower()

    try:
        coin = get_coin(coin_id)

        if not coin:
            await update.message.reply_text("❌ Coin bulunamadı.")
            return

        prices = get_prices_for_ta(coin_id)

        if len(prices) < 50:
            await update.message.reply_text("❌ Teknik analiz için yeterli veri yok.")
            return

        current_price = prices[-1]
        rsi = calculate_rsi(prices)
        ema20 = calculate_ema(prices, 20)
        ema50 = calculate_ema(prices, 50)
        macd = calculate_macd(prices)

        score = 0
        direction = "Nötr"
        comments = []

        if rsi is not None:
            if 45 <= rsi <= 65:
                score += 2
                comments.append("RSI sağlıklı bölgede")
            elif rsi < 30:
                score += 1
                comments.append("RSI aşırı satım bölgesinde")
            elif rsi > 70:
                comments.append("RSI aşırı alım bölgesinde")

        if ema20 and ema50:
            if ema20 > ema50:
                score += 3
                comments.append("EMA20 > EMA50, trend pozitif")
            else:
                comments.append("EMA20 < EMA50, trend zayıf")

        if macd is not None:
            if macd > 0:
                score += 2
                comments.append("MACD pozitif")
            else:
                comments.append("MACD negatif")

        change_24h = coin.get("price_change_percentage_24h") or 0
        volume = coin.get("total_volume") or 0

        if change_24h > 2:
            score += 1
            comments.append("24s fiyat momentumu pozitif")

        if volume > 100_000_000:
            score += 1
            comments.append("Hacim güçlü")

        score = min(score, 10)

        if score >= 7:
            direction = "LONG Eğilimli"
        elif score <= 3:
            direction = "Zayıf / Bekle"
        else:
            direction = "Nötr / İzle"

        comments_text = "\n".join([f"• {c}" for c in comments])

        text = (
            "📊 TEKNİK ANALİZ\n\n"
            f"🪙 {coin['name']} ({coin['symbol'].upper()})\n"
            f"💰 Fiyat: ${current_price:,.4f}\n\n"
            f"RSI: {rsi:.2f}\n"
            f"EMA20: ${ema20:,.4f}\n"
            f"EMA50: ${ema50:,.4f}\n"
            f"MACD: {macd:.4f}\n\n"
            f"📈 24s Değişim: %{change_24h:.2f}\n"
            f"📊 Hacim: ${volume:,.0f}\n\n"
            f"⭐ Teknik Skor: {score}/10\n"
            f"📌 Yön: {direction}\n\n"
            f"🧠 Yorum:\n{comments_text}\n\n"
            "⚠️ Bu finansal tavsiye değildir."
        )

        await update.message.reply_text(text)

    except Exception as e:
        await update.message.reply_text(f"Hata:\n{e}")
async def ta_scan(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id

    try:
        global ta_cooldown

        data = fetch_markets(order="volume_desc", per_page=50)
        alerts = []

        for coin in data:
            coin_id = coin["id"]
            symbol = coin["symbol"].upper()
            name = coin["name"]
            change_24h = coin.get("price_change_percentage_24h") or 0
            volume = coin.get("total_volume") or 0

            if volume < 50_000_000:
                continue

            try:
                prices = get_prices_for_ta(coin_id)
            except Exception:
                continue

            if len(prices) < 50:
                continue

            current_price = prices[-1]
            rsi = calculate_rsi(prices)
            ema20 = calculate_ema(prices, 20)
            ema50 = calculate_ema(prices, 50)
            macd = calculate_macd(prices)

            if rsi is None or ema20 is None or ema50 is None or macd is None:
                continue

            score = 0
            reasons = []

            if 45 <= rsi <= 65:
                score += 2
                reasons.append("RSI sağlıklı bölgede")
            elif 30 <= rsi < 45:
                score += 1
                reasons.append("RSI toparlanma bölgesinde")

            if ema20 > ema50:
                score += 3
                reasons.append("EMA20 > EMA50")

            if macd > 0:
                score += 2
                reasons.append("MACD pozitif")

            if change_24h >= 2:
                score += 1
                reasons.append("24s momentum pozitif")

            if volume >= 100_000_000:
                score += 1
                reasons.append("Hacim güçlü")

            score = min(score, 10)

            if score < 7:
                continue

            now = time.time()
            last_alert_time = ta_cooldown.get(coin_id, 0)
            cooldown_seconds = 45 * 60

            if now - last_alert_time < cooldown_seconds:
                continue

            if score >= 8:
                direction = "Güçlü LONG Eğilimli"
            else:
                direction = "LONG İzleme"

            alerts.append({
                "symbol": symbol,
                "name": name,
                "price": current_price,
                "rsi": rsi,
                "ema20": ema20,
                "ema50": ema50,
                "macd": macd,
                "change": change_24h,
                "volume": volume,
                "score": score,
                "direction": direction,
                "reasons": reasons[:4]
            })

            ta_cooldown[coin_id] = now

        alerts = sorted(
            alerts,
            key=lambda x: x["score"],
            reverse=True
        )[:5]

        if not alerts:
            return

        text = "🚨 TEKNİK İŞLEM FIRSATI\n\n"

        for coin in alerts:
            reasons_text = ", ".join(coin["reasons"])

            text += (
                f"🪙 {coin['symbol']} - {coin['name']}\n"
                f"💰 Fiyat: ${coin['price']:,.4f}\n"
                f"📈 24s Değişim: %{coin['change']:.2f}\n"
                f"📊 Hacim: ${coin['volume']:,.0f}\n\n"
                f"RSI: {coin['rsi']:.2f}\n"
                f"EMA20: ${coin['ema20']:,.4f}\n"
                f"EMA50: ${coin['ema50']:,.4f}\n"
                f"MACD: {coin['macd']:.4f}\n\n"
                f"⭐ Teknik Skor: {coin['score']}/10\n"
                f"📌 Yön: {coin['direction']}\n"
                f"🧠 Sebep: {reasons_text}\n\n"
            )

        text += "⚠️ Bu finansal tavsiye değildir."

        await context.bot.send_message(chat_id=chat_id, text=text)

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"TA tarama hatası:\n{e}")


async def ta_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    for job in context.job_queue.get_jobs_by_name(f"ta_{chat_id}"):
        job.schedule_removal()

    context.job_queue.run_repeating(
        ta_scan,
        interval=300,
        first=20,
        chat_id=chat_id,
        name=f"ta_{chat_id}"
    )

    await update.message.reply_text(
        "✅ Otomatik teknik tarayıcı açıldı.\n\n"
        "Bot her 5 dakikada bir teknik işlem fırsatlarını tarayacak."
    )


async def ta_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    jobs = context.job_queue.get_jobs_by_name(f"ta_{chat_id}")

    if not jobs:
        await update.message.reply_text("Aktif teknik tarayıcı yok.")
        return

    for job in jobs:
        job.schedule_removal()

    await update.message.reply_text("🛑 Otomatik teknik tarayıcı kapatıldı.")


async def ta_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    jobs = context.job_queue.get_jobs_by_name(f"ta_{chat_id}")

    status = "🟢 Aktif" if jobs else "🔴 Kapalı"

    text = (
        "📊 TA TARAMA DURUMU\n\n"
        f"Durum: {status}\n"
        f"⏳ Cooldown'daki Coin: {len(ta_cooldown)}\n"
        f"🔄 Tarama Aralığı: 5 Dakika\n"
        f"🛡️ Cooldown Süresi: 45 Dakika\n"
        f"📌 Filtre: RSI + EMA20/50 + MACD + Hacim"
    )

    await update.message.reply_text(text)
def calculate_atr_from_prices(prices, period=14):
    if len(prices) < period + 1:
        return None

    ranges = []

    for i in range(1, period + 1):
        ranges.append(abs(prices[-i] - prices[-i - 1]))

    atr = sum(ranges) / period
    return atr


def calculate_trade_levels(price, direction, prices):
    atr = calculate_atr_from_prices(prices)

    if atr is None:
        atr = price * 0.02

    if direction == "LONG":
        stop = price - (atr * 1.5)
        target1 = price + (atr * 2)
        target2 = price + (atr * 3)
    else:
        stop = price + (atr * 1.5)
        target1 = price - (atr * 2)
        target2 = price - (atr * 3)

    risk = abs(price - stop)
    reward = abs(target2 - price)

    rr = reward / risk if risk > 0 else 0

    return {
        "atr": atr,
        "stop": stop,
        "target1": target1,
        "target2": target2,
        "rr": rr
    }
def calculate_support_resistance(prices, lookback=48):
    if len(prices) < lookback:
        recent_prices = prices
    else:
        recent_prices = prices[-lookback:]

    support = min(recent_prices)
    resistance = max(recent_prices)

    return {
        "support": support,
        "resistance": resistance
    }
def calculate_trade_quality(score, rr, volume, change_24h):
    quality_score = 0

    if score >= 8:
        quality_score += 3
    elif score >= 7:
        quality_score += 2
    elif score >= 6:
        quality_score += 1

    if rr >= 2.5:
        quality_score += 3
    elif rr >= 2:
        quality_score += 2
    elif rr >= 1.5:
        quality_score += 1

    if volume >= 500_000_000:
        quality_score += 2
    elif volume >= 100_000_000:
        quality_score += 1

    if change_24h >= 5:
        quality_score += 2
    elif change_24h >= 2:
        quality_score += 1

    if quality_score >= 9:
        return "A+"
    elif quality_score >= 7:
        return "A"
    elif quality_score >= 5:
        return "B"
    elif quality_score >= 3:
        return "C"
    else:
        return "D"
def calculate_institutional_flow(volume, change_24h, score, rr):
    flow_score = 0

    if volume >= 100_000_000:
        flow_score += 1
    if volume >= 500_000_000:
        flow_score += 2
    if volume >= 1_000_000_000:
        flow_score += 2

    if change_24h >= 2:
        flow_score += 1
    if change_24h >= 5:
        flow_score += 2
    if change_24h >= 10:
        flow_score += 2

    if score >= 7:
        flow_score += 1
    if score >= 8:
        flow_score += 2

    if rr >= 2:
        flow_score += 1

    if flow_score >= 8:
        return "🟢 Yüksek"
    elif flow_score >= 5:
        return "🟡 Orta"
    else:
        return "🔴 Düşük"
def analyze_timeframe_trend(prices):
    if len(prices) < 50:
        return "⚪ Veri Yok"

    ema20 = calculate_ema(prices, 20)
    ema50 = calculate_ema(prices, 50)
    macd = calculate_macd(prices)

    if ema20 is None or ema50 is None or macd is None:
        return "⚪ Veri Yok"

    if ema20 > ema50 and macd > 0:
        return "🟢 Pozitif"
    elif ema20 < ema50 and macd < 0:
        return "🔴 Negatif"
    else:
        return "🟡 Kararsız"


def get_multi_timeframe_trends(coin_id):
    prices_1h = get_prices_for_ta(coin_id)

    prices_4h = prices_1h[::4]

    prices_1d = get_prices_for_ta(coin_id)
    prices_1d = prices_1d[::24]

    return {
        "1H": analyze_timeframe_trend(prices_1h),
        "4H": analyze_timeframe_trend(prices_4h),
        "1D": analyze_timeframe_trend(prices_1d)
    }
def calculate_confidence_score(score, rr, quality, institutional_flow):
    confidence = 0

    confidence += score * 6

    if rr >= 3:
        confidence += 15
    elif rr >= 2:
        confidence += 10
    elif rr >= 1.5:
        confidence += 5

    if quality == "A+":
        confidence += 15
    elif quality == "A":
        confidence += 10
    elif quality == "B":
        confidence += 5

    if "Yüksek" in institutional_flow:
        confidence += 15
    elif "Orta" in institutional_flow:
        confidence += 8

    confidence = min(confidence, 100)

    if confidence >= 80:
        label = "🟢 Yüksek Güven"
    elif confidence >= 60:
        label = "🟡 Orta Güven"
    else:
        label = "🔴 Düşük Güven"

    return confidence, label
def detect_setup_type(rsi, ema20, ema50, macd, change_24h, price, resistance, support):
    if ema20 > ema50 and macd > 0 and 45 <= rsi <= 65:
        return "Trend Continuation"

    if price >= resistance * 0.98 and macd > 0 and change_24h > 2:
        return "Breakout Adayı"

    if price <= support * 1.03 and 35 <= rsi <= 55 and ema20 > ema50:
        return "Pullback"

    if rsi < 35 and macd > 0:
        return "Reversal Adayı"

    return "Standart Momentum"

async def trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Trade analizi başlatıldı...")

    coin_id = context.args[0].lower()

        
    try:
        
        coin = get_coin(coin_id)
        if not coin:
            await update.message.reply_text("❌ Coin bulunamadı.")
            return
        
        prices = get_prices_for_ta(coin_id)
        if len(prices) < 50:
            await update.message.reply_text("❌ Yeterli veri yok.")
            return

        current_price = prices[-1]

        rsi = calculate_rsi(prices)
        ema20 = calculate_ema(prices, 20)
        ema50 = calculate_ema(prices, 50)
        macd = calculate_macd(prices)

        if rsi is None or ema20 is None or ema50 is None or macd is None:
            await update.message.reply_text("❌ Teknik göstergeler hesaplanamadı.")
            return

        score = 0
        reasons = []

        if 45 <= rsi <= 65:
            score += 2
            reasons.append("RSI sağlıklı bölgede")
        elif rsi < 35:
            score += 1
            reasons.append("RSI aşırı satıma yakın")

        if ema20 > ema50:
            score += 3
            reasons.append("EMA20 > EMA50")

        if macd > 0:
            score += 2
            reasons.append("MACD pozitif")

        change_24h = coin.get("price_change_percentage_24h") or 0
        volume = coin.get("total_volume") or 0

        if change_24h > 2:
            score += 1
            reasons.append("Momentum pozitif")

        if volume > 100_000_000:
            score += 1
            reasons.append("Hacim güçlü")

        score = min(score, 10)

        if score < 7:
            await update.message.reply_text(
                f"🪙 {coin['name']}\n\n"
                f"⭐ Teknik Skor: {score}/10\n"
                "📌 Şu an güçlü işlem fırsatı yok."
            )
            return

        direction = "LONG"

        levels = calculate_trade_levels(
            current_price,
            direction,
            prices
        )

        sr = calculate_support_resistance(prices)
        support = sr["support"]
        resistance = sr["resistance"]

        fib = calculate_fibonacci_levels(prices)

        if fib is None:
            fib = {
                "swing_low": support,
                "swing_high": resistance,
                "fib_236": resistance,
                "fib_382": resistance,
                "fib_500": current_price,
                "fib_618": support,
                "fib_786": support
            }

        fibo_comment = "Nötr"
        fibo_zone = "Nötr"

        if current_price <= fib["fib_618"]:
            fibo_comment = "0.618 bölgesine yakın, pullback fırsatı olabilir."
        elif current_price <= fib["fib_500"]:
            fibo_comment = "0.500 bölgesinde, destek aranabilir."
        elif current_price >= fib["fib_382"]:
            fibo_comment = "Yukarı momentum güçlü."

        distance_618 = abs(current_price - fib["fib_618"]) / current_price
        distance_500 = abs(current_price - fib["fib_500"]) / current_price

        if distance_618 <= 0.01:
            fibo_zone = "🟢 0.618 Golden Zone"
        elif distance_500 <= 0.01:
            fibo_zone = "🟡 0.500 Re-test Zone"
        elif current_price > fib["fib_236"]:
            fibo_zone = "🚀 Fibo Üst Momentum Bölgesi"

        market_structure = detect_market_structure(prices)
        liquidity_sweep = detect_liquidity_sweep(prices)

        setup_type = detect_setup_type(
            rsi,
            ema20,
            ema50,
            macd,
            change_24h,
            current_price,
            resistance,
            support
        )

        quality = calculate_trade_quality(
            score,
            levels["rr"],
            volume,
            change_24h
        )

        institutional_flow = calculate_institutional_flow(
            volume,
            change_24h,
            score,
            levels["rr"]
        )

        confidence, confidence_label = calculate_confidence_score(
            score,
            levels["rr"],
            quality,
            institutional_flow
        )
        timeframes = get_multi_timeframe_trends(coin_id)

        reasons_text = "\n".join(f"• {r}" for r in reasons)

    

        await update.message.reply_text(text)

    except Exception as e:
        await update.message.reply_text(
            f"TRADE HATASI:\n{type(e).__name__}\n{e}"
        )

async def scalp_scan(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id

    symbols = ["BTC", "ETH", "SOL", "XRP", "DOGE", "SUI", "LINK", "AVAX"]

    try:
        global scalp_cooldown

        alerts = []

        for symbol in symbols:
            candles = get_bybit_klines(symbol, interval="15", limit=100)

            if len(candles) < 50:
                continue

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

            market_structure = detect_scalp_market_structure(closes)
            liquidity_sweep = detect_liquidity_sweep(candles)
            fvg = detect_fvg(candles)
            order_block = detect_order_block(candles)
            pd_zone = detect_pd_zone(candles)

            last_momentum = ((current_price - previous_close) / previous_close) * 100

            rsi = calculate_rsi(closes)
            ema9 = calculate_ema(closes, 9)
            ema21 = calculate_ema(closes, 21)
            ema50 = calculate_ema(closes, 50)
            ema200 = calculate_ema(closes, 200)
            macd = calculate_macd(closes)
            volume_change = calculate_volume_change(candles)
            atr = calculate_atr(candles)
            timeframe_confirmations = get_scalp_timeframe_confirmations(symbol)

            if rsi is None or ema9 is None or ema21 is None or macd is None:
                continue
           

            score = 0
            reasons = []
            ict_score = 0
            if 45 <= rsi <= 68:
                score += 2
                reasons.append("RSI scalp için sağlıklı")
            elif 35 <= rsi < 45:
                score += 1
                reasons.append("RSI toparlanma bölgesinde")

            if ema9 and ema21 and ema50 and ema200:
                if ema9 > ema21 > ema50 > ema200:
                    score += 4
                    reasons.append("EMA Ribbon tamamen bullish")
                    ribbon = "🟢 Mükemmel"
                elif ema9 > ema21 > ema50:
                    score += 3
                    reasons.append("EMA Ribbon güçlü")
                    ribbon = "🟢 Güçlü"
                elif ema9 > ema21:
                    score += 2
                    reasons.append("Kısa vadeli EMA bullish")
                    ribbon = "🟡 Orta"
                else:
                    ribbon = "🔴 Zayıf"
            else:
                ribbon = "⚪ Veri Yok"

            if macd > 0:
                score += 2
                reasons.append("MACD pozitif")

            if last_momentum > 0:
                score += 1
                reasons.append("Son mum pozitif")
            if liquidity_sweep == "🟢 Sell-side Liquidity Sweep":
                score += 2
                reasons.append("Sell-side liquidity sweep sonrası dönüş sinyali")

            elif liquidity_sweep == "🔴 Buy-side Liquidity Sweep":
                score += 2
                reasons.append("Buy-side liquidity sweep sonrası düşüş sinyali")
            if fvg == "🟢 Bullish FVG İçinde":
                score += 3
                reasons.append("Bullish FVG içinde fiyatlanıyor")

            elif fvg == "🟢 Bullish FVG Var":
                score += 1
                reasons.append("Yakında bullish FVG bulundu")

            elif fvg == "🔴 Bearish FVG İçinde":
                score += 3
                reasons.append("Bearish FVG içinde fiyatlanıyor")

            elif fvg == "🔴 Bearish FVG Var":
                score += 1
                reasons.append("Yakında bearish FVG bulundu")
            if order_block == "🟢 Bullish Order Block":
                score += 2
                reasons.append("Bullish order block tespit edildi")

            elif order_block == "🔴 Bearish Order Block":
                score += 2
                reasons.append("Bearish order block tespit edildi")
            if pd_zone == "🟢 Discount Zone":
                score += 1
                reasons.append("Fiyat discount bölgede")

            elif pd_zone == "🔴 Premium Zone":
                score += 1
                reasons.append("Fiyat premium bölgede")

            if market_structure == "🟢 Bullish BOS":
                score += 2
                reasons.append("Bullish BOS tespit edildi")
            elif market_structure == "🔴 Bearish BOS":
                score += 2
                reasons.append("Bearish BOS tespit edildi")
            elif market_structure == "🟢 Bullish CHoCH":
                score += 3
                reasons.append("Bullish CHoCH tespit edildi")
            elif market_structure == "🔴 Bearish CHoCH":
                score += 3
                reasons.append("Bearish CHoCH tespit edildi")

            if volume_change >= 20:
                score += 2
                reasons.append("Hacim ortalamanın üstünde")
            elif volume_change >= 5:
                score += 1
                reasons.append("Hacimde hafif artış")

            positive_tf = 0

            for trend in timeframe_confirmations.values():
                if trend == "🟢 Pozitif":
                    positive_tf += 1

            if positive_tf == 3:
                score += 3
                reasons.append("Tüm zaman dilimleri uyumlu")
            elif positive_tf == 2:
                score += 2
                reasons.append("Zaman dilimlerinin çoğu pozitif")
            elif positive_tf == 1:
                score += 1
                reasons.append("Bir zaman dilimi pozitif")

            if breakout == "🚀 Yukarı Kırılım":
                score += 2
                reasons.append("Son 20 mum direnci kırılıyor")
            elif breakout == "🔴 Aşağı Kırılım":
                reasons.append("Son 20 mum desteği aşağı kırılıyor")
            if market_structure in ["🟢 Bullish BOS", "🔴 Bearish BOS"]:
                ict_score += 2
            elif market_structure in ["🟢 Bullish CHoCH", "🔴 Bearish CHoCH"]:
                ict_score += 3

            if liquidity_sweep in ["🟢 Sell-side Liquidity Sweep", "🔴 Buy-side Liquidity Sweep"]:
                ict_score += 2

            if fvg in ["🟢 Bullish FVG İçinde", "🔴 Bearish FVG İçinde"]:
                ict_score += 2
            elif fvg in ["🟢 Bullish FVG Var", "🔴 Bearish FVG Var"]:
                ict_score += 1

            if order_block in ["🟢 Bullish Order Block", "🔴 Bearish Order Block"]:
                ict_score += 2

            if pd_zone in ["🟢 Discount Zone", "🔴 Premium Zone"]:
                ict_score += 1

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

            if ema9 and ema21 and ema50:
                if ema9 > ema21 > ema50:
                    long_score += 3
                elif ema9 < ema21 < ema50:
                    short_score += 3

            if macd is not None:
                if macd > 0:
                    long_score += 2
                elif macd < 0:
                    short_score += 2

            if breakout == "🚀 Yukarı Kırılım":
                long_score += 2
            elif breakout == "🔴 Aşağı Kırılım":
                short_score += 2
            if liquidity_sweep == "🟢 Sell-side Liquidity Sweep":
                long_score += 3

            elif liquidity_sweep == "🔴 Buy-side Liquidity Sweep":
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

            if last_momentum > 0:
                long_score += 1
            elif last_momentum < 0:
                short_score += 1

            if long_score >= short_score + 2:
                signal_side = "🟢 LONG"
            elif short_score >= long_score + 2:
                signal_side = "🔴 SHORT"
            else:
                signal_side = "🟡 NÖTR"

            score = min(score, 10)
            setup_power = min(100, (score * 7) + (ict_score * 3))

            if setup_power < 90:
                continue

            if ict_score < 5:
                continue
           
            if signal_side == "🟢 LONG":
                if market_structure not in ["🟢 Bullish BOS", "🟢 Bullish CHoCH"]:
                    continue

            elif signal_side == "🔴 SHORT":
                if market_structure not in ["🔴 Bearish BOS", "🔴 Bearish CHoCH"]:
                    continue

            else:
                continue


            if ribbon not in ["🟢 Mükemmel", "🟢 Güçlü"]:
                continue 
            if signal_side == "🟢 LONG":
                if positive_tf < 2:
                    continue
                if volume_change < 5:
                    continue
                if breakout != "🚀 Yukarı Kırılım":
                    continue

            elif signal_side == "🔴 SHORT":
                if negative_tf < 2:
                    continue
                if volume_change < 5:
                    continue
                if breakout != "🔴 Aşağı Kırılım":
                    continue           
            now = time.time()
            last_alert_time = scalp_cooldown.get(symbol, 0)
            cooldown_seconds = 45 * 60

            if now - last_alert_time < cooldown_seconds:
                continue

            if setup_power >= 90:
                setup_label = "🏆 A+ SCALP SETUP"
            else:
                setup_label = "🔥 GÜÇLÜ SCALP SETUP"

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

            alerts.append({
                "symbol": symbol,
                "price": current_price,
                "score": score,
                "setup_power": setup_power,
                "setup_label": setup_label,
                "signal_side": signal_side,
                "ribbon": ribbon,
                "breakout": breakout,
                "rsi": rsi,
                "volume_change": volume_change,
                "momentum": last_momentum,
                "stop": stop,
                "rr": rr,
                "target1": target1,
                "target2": target2,
                "timeframes": timeframe_confirmations,
                "reasons": reasons[:5]
                
            })

            scalp_cooldown[symbol] = now

        alerts = sorted(alerts, key=lambda x: x["setup_power"], reverse=True)[:3]

        if not alerts:
            return

        text = "⚡ SCALP PRO TARAMA SİNYALİ\n━━━━━━━━━━━━━━\n\n"

        for coin in alerts:
            reasons_text = "\n".join(f"• {r}" for r in coin["reasons"])

            text += (
                f"🔥 SETUP GÜCÜ: %{coin['setup_power']}\n"
                f"{coin['setup_label']}\n\n"
                f"🪙 {coin['symbol']}USDT\n"
                f"⏱️ Zaman Dilimi: 15m\n"
                f"💰 Fiyat: ${coin['price']:,.4f}\n"
                f"🎯 Hedef 1: ${coin['target1']:,.4f}\n"
                f"🎯 Hedef 2: ${coin['target2']:,.4f}\n"
                f"🛑 Stop: ${coin['stop']:,.4f}\n\n"
                f"📊 Risk/Ödül: 1:{coin['rr']:.2f}\n\n"
                f"📈 EMA Ribbon: {coin['ribbon']}\n"
                f"💥 Breakout: {coin['breakout']}\n"
                f"RSI: {coin['rsi']:.2f}\n"
                f"📊 Hacim Değişimi: %{coin['volume_change']:.2f}\n"
                f"📈 Son Mum Momentum: %{coin['momentum']:.2f}\n\n"
                f"📊 Zaman Dilimi Onayı:\n"
                f"5m ➜ {coin['timeframes']['5m']}\n"
                f"15m ➜ {coin['timeframes']['15m']}\n"
                f"1H ➜ {coin['timeframes']['1H']}\n\n"
                f"🧠 Sebep:\n{reasons_text}\n\n"
            )

        text += "⚠️ Bu finansal tavsiye değildir."

        await context.bot.send_message(chat_id=chat_id, text=text)

    except Exception as e:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Scalp scan hatası:\n{type(e).__name__}\n{e}"
        )


async def scalp_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    for job in context.job_queue.get_jobs_by_name(f"scalp_{chat_id}"):
        job.schedule_removal()

    context.job_queue.run_repeating(
        scalp_scan,
        interval=300,
        first=20,
        chat_id=chat_id,
        name=f"scalp_{chat_id}"
    )

    await update.message.reply_text(
        "✅ Scalp tarayıcı açıldı.\n\n"
        "Bot her 5 dakikada bir güçlü kısa zaman dilimi fırsatlarını tarayacak."
    )


async def scalp_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    jobs = context.job_queue.get_jobs_by_name(f"scalp_{chat_id}")

    if not jobs:
        await update.message.reply_text("Aktif scalp tarayıcı yok.")
        return

    for job in jobs:
        job.schedule_removal()

    await update.message.reply_text("🛑 Scalp tarayıcı kapatıldı.")


async def scalp_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    jobs = context.job_queue.get_jobs_by_name(f"scalp_{chat_id}")
    status = "🟢 Aktif" if jobs else "🔴 Kapalı"

    text = (
        "⚡ SCALP TARAMA DURUMU\n\n"
        f"Durum: {status}\n"
        f"⏳ Cooldown'daki Coin: {len(scalp_cooldown)}\n"
        f"🔄 Tarama Aralığı: 5 Dakika\n"
        f"🛡️ Cooldown Süresi: 45 Dakika\n"
        f"📌 Filtre: Setup Gücü %80+"
    )

    await update.message.reply_text(text)
async def scalp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    market_structure = "⚪ Devre Dışı"
    if not context.args:
        await update.message.reply_text("Örnek kullanım:\n/scalp btc")
        return

    symbol = context.args[0].upper()

    try:
        candles = get_bybit_klines(symbol, interval="15", limit=100)

        if len(candles) < 50:
            await update.message.reply_text("❌ Scalp analizi için yeterli mum verisi yok.")
            return

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

        market_structure = detect_scalp_market_structure(closes)
        liquidity_sweep = detect_liquidity_sweep(candles)
        fvg = detect_fvg(candles)
        order_block = detect_order_block(candles)
        pd_zone = detect_pd_zone(candles)

        last_momentum = ((current_price - previous_close) / previous_close) * 100  
      
        rsi = calculate_rsi(closes)
        ema9 = calculate_ema(closes, 9)
        ema21 = calculate_ema(closes, 21)
        ema50 = calculate_ema(closes, 50)
        ema200 = calculate_ema(closes, 200)
        macd = calculate_macd(closes)

        volume_change = calculate_volume_change(candles)
        atr = calculate_atr(candles)
        timeframe_confirmations = get_scalp_timeframe_confirmations(symbol)

        
        score = 0
        reasons = []
        ict_score = 0

        if rsi is not None:
            if 45 <= rsi <= 68:
                score += 1
                reasons.append("RSI destekleyici")
            elif rsi > 75:
                reasons.append("RSI aşırı ısınmış")

        if ema9 and ema21 and ema50 and ema200:

            if ema9 > ema21 > ema50 > ema200:
                score += 4
                reasons.append("EMA Ribbon tamamen bullish")

            elif ema9 > ema21 > ema50:
                score += 3
                reasons.append("EMA Ribbon güçlü")

            elif ema9 > ema21:
                score += 2
                reasons.append("Kısa vadeli EMA bullish")

            else:
                reasons.append("EMA Ribbon zayıf")
        if macd is not None:
            if macd > 0:
                score += 1
                reasons.append("MACD destekleyici")
            else:
                reasons.append("MACD zayıf")        
        if last_momentum > 0:
            score += 1
            reasons.append("Son mum pozitif")
        if liquidity_sweep == "🟢 Sell-side Liquidity Sweep":
            score += 2
            reasons.append("Sell-side liquidity sweep sonrası dönüş sinyali")

        elif liquidity_sweep == "🔴 Buy-side Liquidity Sweep":
            score += 2
            reasons.append("Buy-side liquidity sweep sonrası düşüş sinyali")
        if fvg == "🟢 Bullish FVG İçinde":
            score += 3
            reasons.append("Bullish FVG içinde fiyatlanıyor")

        elif fvg == "🟢 Bullish FVG Var":
            score += 1
            reasons.append("Yakında bullish FVG bulundu")

        elif fvg == "🔴 Bearish FVG İçinde":
            score += 3
            reasons.append("Bearish FVG içinde fiyatlanıyor")

        elif fvg == "🔴 Bearish FVG Var":
            score += 1
            reasons.append("Yakında bearish FVG bulundu")
        if order_block == "🟢 Bullish Order Block":
            score += 2
            reasons.append("Bullish order block tespit edildi")

        elif order_block == "🔴 Bearish Order Block":
            score += 2
            reasons.append("Bearish order block tespit edildi")
        if pd_zone == "🟢 Discount Zone":
            score += 1
            reasons.append("Fiyat discount bölgede")

        elif pd_zone == "🔴 Premium Zone":
            score += 1
            reasons.append("Fiyat premium bölgede")

        if volume_change >= 20:
            score += 2
            reasons.append("Hacim ortalamanın üstünde")
        elif volume_change >= 5:
            score += 1
            reasons.append("Hacimde hafif artış")

        score = min(score, 10)
        if breakout == "🚀 Yukarı Kırılım":
            score += 2
            reasons.append("Son 20 mum direnci kırılıyor")

        elif breakout == "🔴 Aşağı Kırılım":
            reasons.append("Son 20 mum desteği aşağı kırılıyor")
        if market_structure in ["🟢 Bullish BOS", "🔴 Bearish BOS"]:
            ict_score += 2
        elif market_structure in ["🟢 Bullish CHoCH", "🔴 Bearish CHoCH"]:
            ict_score += 3

        if liquidity_sweep in ["🟢 Sell-side Liquidity Sweep", "🔴 Buy-side Liquidity Sweep"]:
            ict_score += 2

        if fvg in ["🟢 Bullish FVG İçinde", "🔴 Bearish FVG İçinde"]:
            ict_score += 2
        elif fvg in ["🟢 Bullish FVG Var", "🔴 Bearish FVG Var"]:
            ict_score += 1

        if order_block in ["🟢 Bullish Order Block", "🔴 Bearish Order Block"]:
            ict_score += 2

        if pd_zone in ["🟢 Discount Zone", "🔴 Premium Zone"]:
            ict_score += 1

        ict_score = min(ict_score, 10)
        long_score = 0
        short_score = 0

        if ema9 and ema21 and ema50:
            if ema9 > ema21 > ema50:
                long_score += 3
            elif ema9 < ema21 < ema50:
                short_score += 3

        if macd is not None:
            if macd > 0:
                long_score += 2
            elif macd < 0:
                short_score += 2

        if rsi is not None:
            if 45 <= rsi <= 70:
                long_score += 1
            elif 30 <= rsi <= 55:
                short_score += 1

        if breakout == "🚀 Yukarı Kırılım":
            long_score += 2
        elif breakout == "🔴 Aşağı Kırılım":
            short_score += 2
        if liquidity_sweep == "🟢 Sell-side Liquidity Sweep":
            long_score += 3

        elif liquidity_sweep == "🔴 Buy-side Liquidity Sweep":
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

        if last_momentum > 0:
            long_score += 1
        elif last_momentum < 0:
            short_score += 1

        positive_tf = 0
        negative_tf = 0

        for trend in timeframe_confirmations.values():
            if trend == "🟢 Pozitif":
                positive_tf += 1
            elif trend == "🔴 Negatif":
                negative_tf += 1

        if positive_tf >= 2:
            long_score += 2

        if negative_tf >= 2:
            short_score += 2

        if long_score >= short_score + 2:
            signal_side = "🟢 LONG"
        elif short_score >= long_score + 2:
            signal_side = "🔴 SHORT"
        else:
            signal_side = "🟡 NÖTR"
        if score >= 8:
            direction = f"GÜÇLÜ {signal_side}"
        elif score >= 6:
            direction = f"{signal_side} İZLE"
        else:
            direction = "BEKLE"

        setup_power = min(100, (score * 7) + (ict_score * 3))

        if setup_power >= 90:
            setup_label = "🏆 A+ KURUMSAL LONG"
        elif setup_power >= 80:
            setup_label = "🔥 GÜÇLÜ LONG"
        elif setup_power >= 60:
            setup_label = "🟢 LONG İZLE"
        else:
            setup_label = "🟡 BEKLE"

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

        if ema9 and ema21 and ema50 and ema200:
            if ema9 > ema21 > ema50 > ema200:
                ribbon = "🟢 Mükemmel"
            elif ema9 > ema21 > ema50:
                ribbon = "🟢 Güçlü"
            elif ema9 > ema21:
                ribbon = "🟡 Orta"
            else:
                ribbon = "🔴 Zayıf"
        else:
            ribbon = "⚪ Veri Yok"       
        
        reasons_text = "\n".join(f"• {r}" for r in reasons)

        text = (
            "⚡ SCALP PRO\n"
            "━━━━━━━━━━━━━━\n\n"
            f"🔥 SETUP GÜCÜ: %{setup_power}\n"
            f"{setup_label}\n\n"
            f"🪙 {symbol}USDT\n"
            f"⏱️ Zaman Dilimi: 15m\n"
            f"📌 Sinyal Yönü: {signal_side}\n"
            f"📌 Durum: {direction}\n\n"
            f"📈 EMA Ribbon: {ribbon}\n\n"
            f"💥 Breakout: {breakout}\n\n"
            f"📈 Market Structure: {market_structure}\n\n"
            f"💧 Liquidity Sweep: {liquidity_sweep}\n\n"
            f"🟪 FVG: {fvg}\n\n"
            f"🧱 Order Block: {order_block}\n\n"
            f"📍 P/D Zone: {pd_zone}\n\n"
            f"💰 Fiyat: ${current_price:,.4f}\n"
            f"🎯 Hedef 1: ${target1:,.4f}\n"
            f"🎯 Hedef 2: ${target2:,.4f}\n"
            f"🛑 Stop: ${stop:,.4f}\n\n"
            f"📊 Risk/Ödül: 1:{rr:.2f}\n\n"

            f"RSI: {rsi:.2f}\n"
            f"EMA9: ${ema9:,.4f}\n"
            f"EMA21: ${ema21:,.4f}\n"
            f"MACD: {macd:.4f}\n"
            f"📊 Hacim Değişimi: %{volume_change:.2f}\n"
            f"📈 Son Mum Momentum: %{last_momentum:.2f}\n\n"
            f"📊 Zaman Dilimi Onayı:\n"
            f"5m ➜ {timeframe_confirmations['5m']}\n"
            f"15m ➜ {timeframe_confirmations['15m']}\n"
            f"1H ➜ {timeframe_confirmations['1H']}\n\n"

            f"⭐ Scalp Skoru: {score}/10\n"
            f"🧠 ICT Skoru: {ict_score}/10\n\n"
            f"🧠 Sebep:\n{reasons_text}\n\n"
            "⚠️ Bu finansal tavsiye değildir."
        )

        await update.message.reply_text(text)

    except Exception as e:
        await update.message.reply_text(
            f"SCALP HATASI:\n{type(e).__name__}\n{e}"
        )
        
async def scalp_radar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbols = ["BTC", "ETH", "SOL", "XRP", "DOGE", "SUI", "LINK", "AVAX"]
    radar = []

    try:
        for symbol in symbols:
            candles = get_bybit_klines(symbol, interval="15", limit=100)

            if len(candles) < 50:
                continue

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

            market_structure = detect_scalp_market_structure(closes)

            last_momentum = ((current_price - previous_close) / previous_close) * 100

            rsi = calculate_rsi(closes)
            ema9 = calculate_ema(closes, 9)
            ema21 = calculate_ema(closes, 21)
            ema50 = calculate_ema(closes, 50)
            macd = calculate_macd(closes)

            score = 0
            long_score = 0
            short_score = 0

            if ema9 and ema21 and ema50:
                if ema9 > ema21 > ema50:
                    score += 3
                    long_score += 3
                elif ema9 < ema21 < ema50:
                    score += 3
                    short_score += 3

            if macd is not None:
                if macd > 0:
                    score += 2
                    long_score += 2
                elif macd < 0:
                    score += 2
                    short_score += 2

            if rsi is not None:
                if 45 <= rsi <= 70:
                    score += 1
                    long_score += 1
                elif 30 <= rsi <= 55:
                    score += 1
                    short_score += 1

            if market_structure == "🟢 Bullish BOS":
                score += 2
                long_score += 2
            elif market_structure == "🔴 Bearish BOS":
                score += 2
                short_score += 2
            elif market_structure == "🟢 Bullish CHoCH":
                score += 3
                long_score += 3
            elif market_structure == "🔴 Bearish CHoCH":
                score += 3
                short_score += 3

            if breakout == "🚀 Yukarı Kırılım":
                score += 2
                long_score += 2
            elif breakout == "🔴 Aşağı Kırılım":
                score += 2
                short_score += 2

            if last_momentum > 0:
                score += 1
                long_score += 1
            elif last_momentum < 0:
                score += 1
                short_score += 1

            score = min(score, 10)
            setup_power = score * 10

            if long_score >= short_score + 2:
                signal_side = "🟢 LONG"
            elif short_score >= long_score + 2:
                signal_side = "🔴 SHORT"
            else:
                signal_side = "🟡 NÖTR"

            radar.append({
                "symbol": symbol,
                "signal": signal_side,
                "power": setup_power,
                "structure": market_structure,
                "breakout": breakout
            })

        radar = sorted(radar, key=lambda x: x["power"], reverse=True)[:3]

        if not radar:
            await update.message.reply_text("Radar için veri bulunamadı.")
            return

        medals = ["🥇", "🥈", "🥉"]

        text = "📡 SCALP RADAR\n"
        text += "━━━━━━━━━━━━━━\n\n"

        for i, coin in enumerate(radar):
            text += (
                f"{medals[i]} {coin['symbol']}USDT\n"
                f"📌 Yön: {coin['signal']}\n"
                f"🔥 Güç: %{coin['power']}\n"
                f"📈 Structure: {coin['structure']}\n"
                f"💥 Breakout: {coin['breakout']}\n\n"
            )

        await update.message.reply_text(text)

    except Exception as e:
        await update.message.reply_text(
            f"RADAR HATASI:\n{type(e).__name__}\n{e}"
        )
def calculate_fibonacci_levels(prices):
    if len(prices) < 20:
        return None

    recent_prices = prices[-72:]

    swing_low = min(recent_prices)
    swing_high = max(recent_prices)

    diff = swing_high - swing_low

    if diff <= 0:
        return None

    fib_236 = swing_high - (diff * 0.236)
    fib_382 = swing_high - (diff * 0.382)
    fib_500 = swing_high - (diff * 0.500)
    fib_618 = swing_high - (diff * 0.618)
    fib_786 = swing_high - (diff * 0.786)

    return {
        "swing_low": swing_low,
        "swing_high": swing_high,
        "fib_236": fib_236,
        "fib_382": fib_382,
        "fib_500": fib_500,
        "fib_618": fib_618,
        "fib_786": fib_786
    }

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

        # Bullish Order Block:
        # Düşüş mumu sonrası güçlü yükseliş mumu
        if prev_close < prev_open and current_close > current_open:
            body_strength = abs(current_close - current_open)
            prev_body = abs(prev_close - prev_open)

            if body_strength > prev_body * 1.2:
                return "🟢 Bullish Order Block"

        # Bearish Order Block:
        # Yükseliş mumu sonrası güçlü düşüş mumu
        if prev_close > prev_open and current_close < current_open:
            body_strength = abs(current_close - current_open)
            prev_body = abs(prev_close - prev_open)

            if body_strength > prev_body * 1.2:
                return "🔴 Bearish Order Block"

    return "🟡 Order Block Yok"
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
def detect_market_structure(prices, lookback=48):
    if len(prices) < lookback + 5:
        return "⚪ Veri Yetersiz"

    recent = prices[-lookback:]

    previous_high = max(recent[:-5])
    previous_low = min(recent[:-5])

    current_price = recent[-1]

    if current_price > previous_high:
        return "🟢 Bullish BOS"

    elif current_price < previous_low:
        return "🔴 Bearish BOS"

    elif current_price > recent[-5] and recent[-5] < previous_low * 1.01:
        return "🟢 Bullish CHoCH"

    elif current_price < recent[-5] and recent[-5] > previous_high * 0.99:
        return "🔴 Bearish CHoCH"

    else:
        return "🟡 Range / Yapı Belirsiz"
async def trade_scan(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id

    try:
        global trade_scan_cooldown

        data = fetch_markets(order="volume_desc", per_page=8)
        alerts = []

        for coin in data:
            coin_id = coin["id"]
            symbol = coin["symbol"].upper()
            name = coin["name"]
            volume = coin.get("total_volume") or 0
            change_24h = coin.get("price_change_percentage_24h") or 0

            if volume < 50_000_000:
                continue

            try:
                prices = get_prices_for_ta(coin_id)
            except Exception:
                continue

            if len(prices) < 50:
                continue

            current_price = prices[-1]
            rsi = calculate_rsi(prices)
            ema20 = calculate_ema(prices, 20)
            ema50 = calculate_ema(prices, 50)
            macd = calculate_macd(prices)

            if rsi is None or ema20 is None or ema50 is None or macd is None:
                continue

            score = 0
            reasons = []

            if 45 <= rsi <= 65:
                score += 2
                reasons.append("RSI sağlıklı")
            elif 30 <= rsi < 45:
                score += 1
                reasons.append("RSI toparlanma bölgesi")

            if ema20 > ema50:
                score += 3
                reasons.append("EMA20 > EMA50")
            positive_tf = 0

            for trend in timeframe_confirmations.values():
                if trend == "🟢 Pozitif":
                    positive_tf += 1

            if positive_tf == 3:
                score += 3
                reasons.append("Tüm zaman dilimleri uyumlu")

            elif positive_tf == 2:
                score += 2
                reasons.append("Zaman dilimlerinin çoğu pozitif")

            elif positive_tf == 1:
                score += 1
                reasons.append("Bir zaman dilimi pozitif")

            if macd > 0:
                score += 2
                reasons.append("MACD pozitif")

            if change_24h >= 2:
                score += 1
                reasons.append("Momentum pozitif")

            if volume >= 100_000_000:
                score += 1
                reasons.append("Hacim güçlü")

            score = min(score, 10)
            setup_power = score * 10

            if setup_power >= 90:
                setup_label = "🏆 A+ KURUMSAL LONG"

            elif setup_power >= 80:
                setup_label = "🔥 GÜÇLÜ LONG"

            elif setup_power >= 60:
                setup_label = "🟢 LONG İZLE"

            else:
                setup_label = "🟡 BEKLE"

            if score < 7:
                continue

            direction = "LONG"

            levels = calculate_trade_levels(
                current_price,
                direction,
                prices
            )

            sr = calculate_support_resistance(prices)
            support = sr["support"]
            resistance = sr["resistance"]

            fib = calculate_fibonacci_levels(prices)
            if fib is None:
                fib = {
                    "swing_low": support,
                    "swing_high": resistance,
                    "fib_236": resistance,
                    "fib_382": resistance,
                    "fib_500": current_price,
                    "fib_618": support,
                    "fib_786": support
                }

            fibo_comment = "Nötr"
            fibo_zone = "Nötr"

            if fib:
                if current_price <= fib["fib_618"]:
                    fibo_comment = "0.618 bölgesine yakın, pullback fırsatı olabilir."
                elif current_price <= fib["fib_500"]:
                    fibo_comment = "0.500 bölgesinde, destek aranabilir."
                elif current_price >= fib["fib_382"]:
                    fibo_comment = "Yukarı momentum güçlü."

                distance_618 = abs(current_price - fib["fib_618"]) / current_price
                distance_500 = abs(current_price - fib["fib_500"]) / current_price

                if distance_618 <= 0.01:
                    fibo_zone = "🟢 0.618 Golden Zone"
                elif distance_500 <= 0.01:
                    fibo_zone = "🟡 0.500 Re-test Zone"
                elif current_price > fib["fib_236"]:
                    fibo_zone = "🚀 Fibo Üst Momentum Bölgesi"
            quality = calculate_trade_quality(
                score,
                levels["rr"],
                volume,
                change_24h
            )

            institutional_flow = calculate_institutional_flow(
                volume,
                change_24h,
                score,
                levels["rr"]
            )

            timeframes = get_multi_timeframe_trends(coin_id)

            if quality not in ["A+", "A"]:
                continue

            if timeframes["1H"] != "🟢 Pozitif":
                continue

            now = time.time()
            last_alert_time = trade_scan_cooldown.get(coin_id, 0)
            cooldown_seconds = 60 * 60

            if now - last_alert_time < cooldown_seconds:
                continue

            alerts.append({
                "symbol": symbol,
                "name": name,
                "price": current_price,
                "support": support,
                "resistance": resistance,
                "target1": levels["target1"],
                "target2": levels["target2"],
                "stop": levels["stop"],
                "atr": levels["atr"],
                "rr": levels["rr"],
                "score": score,
                "quality": quality,
                "institutional_flow": institutional_flow,
                "timeframes": timeframes,
                "change": change_24h,
                "volume": volume,
                "reasons": reasons[:5]
            })

            trade_scan_cooldown[coin_id] = now

        alerts = sorted(
            alerts,
            key=lambda x: x["score"],
            reverse=True
        )[:3]

        if not alerts:
            return

        text = "🚨 HIGH QUALITY TRADE SCANNER\n\n"

        for coin in alerts:
            reasons_text = "\n".join(f"• {r}" for r in coin["reasons"])

            text += (
                f"🪙 {coin['symbol']} - {coin['name']}\n"
                f"📌 Yön: LONG\n\n"
                f"💰 Giriş: ${coin['price']:,.4f}\n"
                f"📉 Destek: ${coin['support']:,.4f}\n"
                f"📈 Direnç: ${coin['resistance']:,.4f}\n"
                f"🎯 Hedef 1: ${coin['target1']:,.4f}\n"
                f"🎯 Hedef 2: ${coin['target2']:,.4f}\n"
                f"🛑 Stop: ${coin['stop']:,.4f}\n\n"
                f"📏 ATR: ${coin['atr']:,.4f}\n"
                f"📊 Risk/Ödül: 1:{coin['rr']:.2f}\n"
                f"⭐ İşlem Skoru: {coin['score']}/10\n"
                f"🏆 İşlem Kalitesi: {coin['quality']}\n"
                f"🐋 Kurumsal Para Girişi: {coin['institutional_flow']}\n\n"
                f"📊 Çoklu Zaman Dilimi:\n"
                f"1H: {coin['timeframes']['1H']}\n"
                f"4H: {coin['timeframes']['4H']}\n"
                f"1D: {coin['timeframes']['1D']}\n\n"
                f"🧠 Sebep:\n{reasons_text}\n\n"
            )

        text += "⚠️ Bu finansal tavsiye değildir."

        await context.bot.send_message(chat_id=chat_id, text=text)

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"Trade scan hatası:\n{e}")


async def trade_scan_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    for job in context.job_queue.get_jobs_by_name(f"trade_scan_{chat_id}"):
        job.schedule_removal()

    context.job_queue.run_repeating(
        trade_scan,
        interval=900,
        first=60,
        chat_id=chat_id,
        name=f"trade_scan_{chat_id}"
    )

    await update.message.reply_text(
        "✅ Trade Scanner açıldı.\n\n"
        "Bot her 5 dakikada bir yüksek kaliteli işlem fırsatlarını tarayacak."
    )


async def trade_scan_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    jobs = context.job_queue.get_jobs_by_name(f"trade_scan_{chat_id}")

    if not jobs:
        await update.message.reply_text("Aktif Trade Scanner yok.")
        return

    for job in jobs:
        job.schedule_removal()

    await update.message.reply_text("🛑 Trade Scanner kapatıldı.")


async def trade_scan_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    jobs = context.job_queue.get_jobs_by_name(f"trade_scan_{chat_id}")
    status = "🟢 Aktif" if jobs else "🔴 Kapalı"

    text = (
        "🚨 TRADE SCANNER DURUMU\n\n"
        f"Durum: {status}\n"
        f"⏳ Cooldown'daki Coin: {len(trade_scan_cooldown)}\n"
        f"🔄 Tarama Aralığı: 5 Dakika\n"
        f"🛡️ Cooldown Süresi: 60 Dakika\n"
        f"📌 Filtre: A/A+ kalite + 1H pozitif trend"
    )

    await update.message.reply_text(text)


async def cache_status(update, context):
    text = (
        "📦 CACHE DURUMU\n\n"
        f"Cache'deki Coin: {len(price_cache)}"
    )

    await update.message.reply_text(text)


async def volume_spike_scan(context: ContextTypes.DEFAULT_TYPE):
  async def volume_spike_scan(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id

    try:
        global volume_memory, volume_cooldown

        data = fetch_markets(order="volume_desc", per_page=100)
        alerts = []

        for coin in data:
            coin_id = coin["id"]
            symbol = coin["symbol"].upper()
            name = coin["name"]
            price = coin["current_price"]
            volume = coin["total_volume"]
            change = coin.get("price_change_percentage_24h") or 0

            if volume < 50_000_000:
                continue

            old_volume = volume_memory.get(coin_id)
            volume_memory[coin_id] = volume

            if old_volume is None or old_volume <= 0:
                continue

            diff = volume - old_volume
            spike_percent = (diff / old_volume) * 100

            now = time.time()
            last_alert_time = volume_cooldown.get(coin_id, 0)
            cooldown_seconds = 30 * 60

            if (
               diff >= 20_000_000
               and spike_percent >= 3
               and change >= 2
               and volume >= 50_000_000
):

                if now - last_alert_time >= cooldown_seconds:

                    signal_score = 0

                    if spike_percent >= 5:
                        signal_score += 2
                    if spike_percent >= 10:
                        signal_score += 2
                    if spike_percent >= 20:
                        signal_score += 2

                    if diff >= 50_000_000:
                        signal_score += 1
                    if diff >= 100_000_000:
                        signal_score += 2
                    if diff >= 250_000_000:
                        signal_score += 2

                    if change >= 3:
                        signal_score += 1
                    if change >= 7:
                        signal_score += 2

                    signal_score = min(signal_score, 10)

                    if signal_score < 5:
                        continue

                    if signal_score >= 8:
                        signal_status = "Çok Güçlü"
                    else:
                        signal_status = "Güçlü"

                    alerts.append({
                        "symbol": symbol,
                        "name": name,
                        "price": price,
                        "volume": volume,
                        "diff": diff,
                        "spike_percent": spike_percent,
                        "change": change,
                        "signal_score": signal_score,
                        "signal_status": signal_status
                    })

                    volume_cooldown[coin_id] = now

        alerts = sorted(
            alerts,
            key=lambda x: x["signal_score"],
            reverse=True
        )[:5]

        if not alerts:
            return

        text = "🚨 GÜÇLÜ HACİM SİNYALİ\n\n"

        for coin in alerts:
            text += (
                f"🪙 {coin['symbol']} - {coin['name']}\n"
                f"💰 Fiyat: ${coin['price']:,.4f}\n"
                f"📈 24s Değişim: %{coin['change']:.2f}\n"
                f"📊 Hacim Artışı: +${coin['diff']:,.0f}\n"
                f"🔥 Artış Oranı: %{coin['spike_percent']:.2f}\n"
                f"⭐ Sinyal Gücü: {coin['signal_score']}/10\n"
                f"📌 Durum: {coin['signal_status']}\n\n"
                f"📌 Sinyal Yönü: {coin['signal_side']}\n"
            )

        text += "⚠️ Bu finansal tavsiye değildir."

        await context.bot.send_message(
            chat_id=chat_id,
            text=text
        )

    except Exception as e:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Volume spike hatası:\n{e}"
        )

async def volume_spike_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global volume_memory

    chat_id = update.effective_chat.id

    for job in context.job_queue.get_jobs_by_name(f"volume_spike_{chat_id}"):
        job.schedule_removal()

    # İlk açılışta hafızayı hemen doldur
    try:
        data = fetch_markets(order="volume_desc", per_page=100)

        for coin in data:
            volume_memory[coin["id"]] = coin["total_volume"]

        memory_count = len(volume_memory)

    except Exception as e:
        await update.message.reply_text(f"İlk hacim hafızası oluşturulamadı:\n{e}")
        return

    context.job_queue.run_repeating(
        volume_spike_scan,
        interval=300,
        first=300,
        chat_id=chat_id,
        name=f"volume_spike_{chat_id}"
    )

    await update.message.reply_text(
        "✅ Anlık hacim artışı tarayıcısı açıldı.\n\n"
        f"📊 Hafızaya alınan coin sayısı: {memory_count}\n"
        "Bot her 5 dakikada bir hacim artışlarını tarayacak."
    )


async def volume_spike_off(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id

    jobs = context.job_queue.get_jobs_by_name(f"volume_spike_{chat_id}")

    if not jobs:
        await update.message.reply_text("Aktif hacim artışı tarayıcısı yok.")
        return

    for job in jobs:
        job.schedule_removal()

    await update.message.reply_text("🛑 Anlık hacim artışı tarayıcısı kapatıldı.")


async def volume_spike_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    jobs = context.job_queue.get_jobs_by_name(
        f"volume_spike_{chat_id}"
    )

    status = "🟢 Aktif" if jobs else "🔴 Kapalı"

    memory_count = len(volume_memory)
    cooldown_count = len(volume_cooldown)

    text = (
        "📡 VOLUME SPIKE DURUMU\n\n"
        f"Durum: {status}\n"
        f"📊 Hafızadaki Coin: {memory_count}\n"
        f"⏳ Cooldown'daki Coin: {cooldown_count}\n"
        f"🔄 Tarama Aralığı: 5 Dakika\n"
        f"🛡️ Cooldown Süresi: 30 Dakika"
    )

    await update.message.reply_text(text)
async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "⚙️ BOT AYARLARI\n\n"
        "📊 Minimum Toplam Hacim: $50M\n"
        "📈 Minimum Hacim Artışı: $20M\n"
        "🔥 Minimum Artış Oranı: %3\n"
        "💹 Minimum 24s Fiyat Değişimi: %2\n"
        "⭐ Minimum Sinyal Skoru: 5/10\n"
        "⏳ Cooldown Süresi: 30 dakika\n"
        "🔄 Tarama Aralığı: 5 dakika\n\n"
        "Aktif komutlar:\n"
        "/volume_spike_on\n"
        "/volume_spike_off\n"
        "/volume_spike_status"
    )

    await update.message.reply_text(text)
async def whale_scan(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id

    try:
        global whale_memory, whale_cooldown

        data = fetch_markets(order="volume_desc", per_page=100)
        alerts = []

        for coin in data:
            coin_id = coin["id"]
            symbol = coin["symbol"].upper()
            name = coin["name"]
            price = coin["current_price"]
            volume = coin["total_volume"]
            change = coin.get("price_change_percentage_24h") or 0

            if volume < 100_000_000:
                continue

            old_volume = whale_memory.get(coin_id)
            whale_memory[coin_id] = volume

            if old_volume is None or old_volume <= 0:
                continue

            diff = volume - old_volume
            spike_percent = (diff / old_volume) * 100

            now = time.time()
            last_alert_time = whale_cooldown.get(coin_id, 0)
            cooldown_seconds = 45 * 60

            if (
                diff >= 75_000_000
                and spike_percent >= 4
                and change >= 2
                and volume >= 150_000_000
            ):
                if now - last_alert_time >= cooldown_seconds:
                    whale_score = 0

                    if diff >= 75_000_000:
                        whale_score += 2
                    if diff >= 150_000_000:
                        whale_score += 2
                    if diff >= 300_000_000:
                        whale_score += 2

                    if spike_percent >= 4:
                        whale_score += 2
                    if spike_percent >= 8:
                        whale_score += 2

                    if change >= 2:
                        whale_score += 1
                    if change >= 5:
                        whale_score += 2

                    whale_score = min(whale_score, 10)

                    if whale_score < 6:
                        continue

                    if whale_score >= 8:
                        whale_status = "Çok Güçlü Balina Alımı İhtimali"
                    else:
                        whale_status = "Güçlü Balina Alımı İhtimali"

                    alerts.append({
                        "symbol": symbol,
                        "name": name,
                        "price": price,
                        "volume": volume,
                        "diff": diff,
                        "spike_percent": spike_percent,
                        "change": change,
                        "whale_score": whale_score,
                        "whale_status": whale_status
                    })

                    whale_cooldown[coin_id] = now

        alerts = sorted(
            alerts,
            key=lambda x: x["whale_score"],
            reverse=True
        )[:5]

        if not alerts:
            return

        text = "🐋 OLASI BALİNA ALIMI TESPİT EDİLDİ\n\n"

        for coin in alerts:
            text += (
                f"🪙 {coin['symbol']} - {coin['name']}\n"
                f"💰 Fiyat: ${coin['price']:,.4f}\n"
                f"📈 24s Değişim: %{coin['change']:.2f}\n"
                f"📊 Hacim Girişi: +${coin['diff']:,.0f}\n"
                f"🔥 Hacim Artış Oranı: %{coin['spike_percent']:.2f}\n"
                f"🐋 Balina Skoru: {coin['whale_score']}/10\n"
                f"📌 Durum: {coin['whale_status']}\n\n"
            )

        text += "⚠️ Bu kesin balina alımı değildir; hacim ve fiyat hareketine göre olası büyük alım sinyalidir."

        await context.bot.send_message(chat_id=chat_id, text=text)

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"Whale scan hatası:\n{e}")


async def whale_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global whale_memory

    chat_id = update.effective_chat.id

    for job in context.job_queue.get_jobs_by_name(f"whale_{chat_id}"):
        job.schedule_removal()

    try:
        data = fetch_markets(order="volume_desc", per_page=100)

        for coin in data:
            whale_memory[coin["id"]] = coin["total_volume"]

        memory_count = len(whale_memory)

    except Exception as e:
        await update.message.reply_text(f"Balina hafızası oluşturulamadı:\n{e}")
        return

    context.job_queue.run_repeating(
        whale_scan,
        interval=300,
        first=300,
        chat_id=chat_id,
        name=f"whale_{chat_id}"
    )

    await update.message.reply_text(
        "✅ Balina alım tarayıcısı açıldı.\n\n"
        f"📊 Hafızaya alınan coin sayısı: {memory_count}\n"
        "Bot her 5 dakikada bir olası büyük alımları tarayacak."
    )


async def whale_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    jobs = context.job_queue.get_jobs_by_name(f"whale_{chat_id}")

    if not jobs:
        await update.message.reply_text("Aktif balina tarayıcısı yok.")
        return

    for job in jobs:
        job.schedule_removal()

    await update.message.reply_text("🛑 Balina alım tarayıcısı kapatıldı.")


async def whale_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    jobs = context.job_queue.get_jobs_by_name(f"whale_{chat_id}")

    status = "🟢 Aktif" if jobs else "🔴 Kapalı"

    text = (
        "🐋 BALİNA TARAMA DURUMU\n\n"
        f"Durum: {status}\n"
        f"📊 Hafızadaki Coin: {len(whale_memory)}\n"
        f"⏳ Cooldown'daki Coin: {len(whale_cooldown)}\n"
        f"🔄 Tarama Aralığı: 5 Dakika\n"
        f"🛡️ Cooldown Süresi: 45 Dakika"
    )

    await update.message.reply_text(text)
def get_trending_symbols():
    try:
        url = "https://api.coingecko.com/api/v3/search/trending"
        data = requests.get(url, timeout=20).json()

        symbols = set()

        for item in data.get("coins", []):
            coin = item.get("item", {})
            symbol = coin.get("symbol")

            if symbol:
                symbols.add(symbol.upper())

        return symbols

    except Exception:
        return set()
def to_bybit_symbol(symbol):
    return f"{symbol.upper()}USDT"


def get_bybit_open_interest(symbol):
    try:
        url = "https://api.bybit.com/v5/market/open-interest"
        params = {
            "category": "linear",
            "symbol": to_bybit_symbol(symbol),
            "intervalTime": "5min",
            "limit": 2
        }

        data = requests.get(url, params=params, timeout=20).json()

        result = data.get("result", {})
        items = result.get("list", [])

        if len(items) < 2:
            return None

        latest = float(items[0]["openInterest"])
        previous = float(items[1]["openInterest"])

        if previous <= 0:
            return None

        change_percent = ((latest - previous) / previous) * 100

        return {
            "latest": latest,
            "previous": previous,
            "change_percent": change_percent
        }

    except Exception:
        return None


def get_bybit_long_short(symbol):
    try:
        url = "https://api.bybit.com/v5/market/account-ratio"
        params = {
            "category": "linear",
            "symbol": to_bybit_symbol(symbol),
            "period": "5min",
            "limit": 1
        }

        data = requests.get(url, params=params, timeout=20).json()

        result = data.get("result", {})
        items = result.get("list", [])

        if not items:
            return None

        item = items[0]

        buy_ratio = float(item.get("buyRatio", 0))
        sell_ratio = float(item.get("sellRatio", 0))

        if sell_ratio <= 0:
            return None

        ratio = buy_ratio / sell_ratio

        return {
            "buy_ratio": buy_ratio,
            "sell_ratio": sell_ratio,
            "ratio": ratio
        }

    except Exception:
        return None


async def whale_pro_scan(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id

    try:
        global whale_pro_memory, whale_pro_cooldown

        data = fetch_markets(order="volume_desc", per_page=100)
        trending_symbols = get_trending_symbols()

        alerts = []

        for coin in data:
            coin_id = coin["id"]
            symbol = coin["symbol"].upper()
            name = coin["name"]
            price = coin["current_price"]
            volume = coin["total_volume"]
            change = coin.get("price_change_percentage_24h") or 0
            market_cap_rank = coin.get("market_cap_rank") or 9999

            if volume < 75_000_000:
                continue

            old_volume = whale_pro_memory.get(coin_id)
            whale_pro_memory[coin_id] = volume

            if old_volume is None or old_volume <= 0:
                continue

            diff = volume - old_volume
            spike_percent = (diff / old_volume) * 100

            now = time.time()
            last_alert_time = whale_pro_cooldown.get(coin_id, 0)
            cooldown_seconds = 45 * 60

            if (
                diff >= 30_000_000
                and spike_percent >= 3
                and change >= 2
                and volume >= 75_000_000
            ):
                if now - last_alert_time >= cooldown_seconds:
                    score = 0
                    reasons = []

                    if diff >= 30_000_000:
                        score += 1
                        reasons.append("Yüksek hacim girişi")
                    if diff >= 75_000_000:
                        score += 2
                        reasons.append("Çok yüksek hacim girişi")
                    if diff >= 150_000_000:
                        score += 2
                        reasons.append("Dev hacim girişi")

                    if spike_percent >= 3:
                        score += 1
                    if spike_percent >= 6:
                        score += 2
                        reasons.append("Hacim ivmesi güçlü")
                    if spike_percent >= 10:
                        score += 2
                        reasons.append("Hacim patlaması")

                    if change >= 2:
                        score += 1
                    if change >= 5:
                        score += 2
                        reasons.append("Fiyat momentumlu")
                    if change >= 10:
                        score += 2
                        reasons.append("Güçlü fiyat hareketi")

                    if symbol in trending_symbols:
                        score += 2
                        reasons.append("Trending listesinde")

                    if market_cap_rank <= 100:
                        score += 1
                    if market_cap_rank <= 50:
                        score += 1

                    score = min(score, 10)

                    if score < 6:
                        continue

                    if score >= 9:
                        status = "Çok Güçlü Whale Pro Sinyali"
                    elif score >= 7:
                        status = "Güçlü Whale Pro Sinyali"
                    else:
                        status = "Orta Güçte Whale Pro Sinyali"

                    alerts.append({
                        "symbol": symbol,
                        "name": name,
                        "price": price,
                        "volume": volume,
                        "diff": diff,
                        "spike_percent": spike_percent,
                        "change": change,
                        "rank": market_cap_rank,
                        "score": score,
                        "status": status,
                        "reasons": reasons[:4]
                    })

                    whale_pro_cooldown[coin_id] = now

        alerts = sorted(
            alerts,
            key=lambda x: x["score"],
            reverse=True
        )[:5]

        if not alerts:
            return

        text = "🐋🚀 WHALE PRO SİNYALİ\n\n"

        for coin in alerts:
            reasons_text = ", ".join(coin["reasons"]) if coin["reasons"] else "Standart hacim + momentum"

            text += (
                f"🪙 {coin['symbol']} - {coin['name']}\n"
                f"💰 Fiyat: ${coin['price']:,.4f}\n"
                f"📈 24s Değişim: %{coin['change']:.2f}\n"
                f"📊 Hacim Girişi: +${coin['diff']:,.0f}\n"
                f"🔥 Hacim Artış Oranı: %{coin['spike_percent']:.2f}\n"
                f"🏆 Rank: {coin['rank']}\n"
                f"🐋 Whale Pro Skoru: {coin['score']}/10\n"
                f"📌 Durum: {coin['status']}\n"
                f"🧠 Sebep: {reasons_text}\n\n"
            )

        text += "⚠️ Bu kesin balina alımı değildir; hacim, momentum ve trend verilerine göre olası büyük alım sinyalidir."

        await context.bot.send_message(chat_id=chat_id, text=text)

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"Whale Pro hatası:\n{e}")


async def whale_pro_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global whale_pro_memory

    chat_id = update.effective_chat.id

    for job in context.job_queue.get_jobs_by_name(f"whale_pro_{chat_id}"):
        job.schedule_removal()

    try:
        data = fetch_markets(order="volume_desc", per_page=100)

        for coin in data:
            whale_pro_memory[coin["id"]] = coin["total_volume"]

        memory_count = len(whale_pro_memory)

    except Exception as e:
        await update.message.reply_text(f"Whale Pro hafızası oluşturulamadı:\n{e}")
        return

    context.job_queue.run_repeating(
        whale_pro_scan,
        interval=300,
        first=300,
        chat_id=chat_id,
        name=f"whale_pro_{chat_id}"
    )

    await update.message.reply_text(
        "✅ Whale Pro tarayıcısı açıldı.\n\n"
        f"📊 Hafızaya alınan coin sayısı: {memory_count}\n"
        "Bot her 5 dakikada bir hacim + momentum + trend kontrolü yapacak."
    )


async def whale_pro_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    jobs = context.job_queue.get_jobs_by_name(f"whale_pro_{chat_id}")

    if not jobs:
        await update.message.reply_text("Aktif Whale Pro tarayıcısı yok.")
        return

    for job in jobs:
        job.schedule_removal()

    await update.message.reply_text("🛑 Whale Pro tarayıcısı kapatıldı.")


async def whale_pro_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    jobs = context.job_queue.get_jobs_by_name(f"whale_pro_{chat_id}")

    status = "🟢 Aktif" if jobs else "🔴 Kapalı"

    text = (
        "🐋🚀 WHALE PRO DURUMU\n\n"
        f"Durum: {status}\n"
        f"📊 Hafızadaki Coin: {len(whale_pro_memory)}\n"
        f"⏳ Cooldown'daki Coin: {len(whale_pro_cooldown)}\n"
        f"🔄 Tarama Aralığı: 5 Dakika\n"
        f"🛡️ Cooldown Süresi: 45 Dakika\n"
        f"🧠 Ek Filtre: Trending + Momentum + Hacim"
    )

    await update.message.reply_text(text)
async def whale_v2_scan(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id

    try:
        global whale_v2_memory, whale_v2_cooldown

        data = fetch_markets(order="volume_desc", per_page=50)
        trending_symbols = get_trending_symbols()

        alerts = []

        for coin in data:
            coin_id = coin["id"]
            symbol = coin["symbol"].upper()
            name = coin["name"]
            price = coin["current_price"]
            volume = coin["total_volume"]
            change = coin.get("price_change_percentage_24h") or 0
            market_cap_rank = coin.get("market_cap_rank") or 9999

            if volume < 75_000_000:
                continue

            old_volume = whale_v2_memory.get(coin_id)
            whale_v2_memory[coin_id] = volume

            if old_volume is None or old_volume <= 0:
                continue

            diff = volume - old_volume
            spike_percent = (diff / old_volume) * 100

            if diff < 20_000_000 or spike_percent < 2 or change < 1:
                continue

            oi = get_bybit_open_interest(symbol)
            long_short = get_bybit_long_short(symbol)

            now = time.time()
            last_alert_time = whale_v2_cooldown.get(coin_id, 0)
            cooldown_seconds = 45 * 60

            if now - last_alert_time < cooldown_seconds:
                continue

            score = 0
            reasons = []

            if diff >= 20_000_000:
                score += 1
                reasons.append("Hacim girişi")
            if diff >= 75_000_000:
                score += 2
                reasons.append("Yüksek hacim girişi")
            if diff >= 150_000_000:
                score += 2
                reasons.append("Dev hacim girişi")

            if spike_percent >= 2:
                score += 1
            if spike_percent >= 5:
                score += 2
                reasons.append("Hacim ivmesi güçlü")
            if spike_percent >= 10:
                score += 2
                reasons.append("Hacim patlaması")

            if change >= 1:
                score += 1
            if change >= 3:
                score += 1
                reasons.append("Fiyat yukarı hareketli")
            if change >= 7:
                score += 2
                reasons.append("Güçlü fiyat momentumu")

            oi_text = "Yok"
            oi_change = None

            if oi is not None:
                oi_change = oi["change_percent"]
                oi_text = f"%{oi_change:.2f}"

                if oi_change >= 1:
                    score += 1
                    reasons.append("Open Interest artıyor")
                if oi_change >= 3:
                    score += 2
                    reasons.append("OI güçlü artıyor")
                if oi_change >= 6:
                    score += 2
                    reasons.append("OI patlaması")

            ls_text = "Yok"

            if long_short is not None:
                ls_ratio = long_short["ratio"]
                ls_text = f"{ls_ratio:.2f}"

                if ls_ratio >= 1.2:
                    score += 1
                    reasons.append("Long tarafı baskın")
                if ls_ratio >= 1.5:
                    score += 2
                    reasons.append("Long/Short güçlü")
                if ls_ratio >= 2:
                    score += 2
                    reasons.append("Aşırı long ilgisi")

            if symbol in trending_symbols:
                score += 2
                reasons.append("Trending listesinde")

            if market_cap_rank <= 100:
                score += 1
            if market_cap_rank <= 50:
                score += 1

            score = min(score, 10)

            if score < 6:
                continue

            if score >= 9:
                status = "Çok Güçlü Whale Pro v2 Sinyali"
            elif score >= 7:
                status = "Güçlü Whale Pro v2 Sinyali"
            else:
                status = "Orta Güçte Whale Pro v2 Sinyali"

            alerts.append({
                "symbol": symbol,
                "name": name,
                "price": price,
                "volume": volume,
                "diff": diff,
                "spike_percent": spike_percent,
                "change": change,
                "rank": market_cap_rank,
                "score": score,
                "status": status,
                "reasons": reasons[:5],
                "oi_text": oi_text,
                "ls_text": ls_text
            })

            whale_v2_cooldown[coin_id] = now

        alerts = sorted(
            alerts,
            key=lambda x: x["score"],
            reverse=True
        )[:5]

        if not alerts:
            return

        text = "🐋🚀 WHALE PRO V2 SİNYALİ\n\n"

        for coin in alerts:
            reasons_text = ", ".join(coin["reasons"]) if coin["reasons"] else "Hacim + momentum"

            text += (
                f"🪙 {coin['symbol']} - {coin['name']}\n"
                f"💰 Fiyat: ${coin['price']:,.4f}\n"
                f"📈 24s Değişim: %{coin['change']:.2f}\n"
                f"📊 Hacim Girişi: +${coin['diff']:,.0f}\n"
                f"🔥 Hacim Artış Oranı: %{coin['spike_percent']:.2f}\n"
                f"📈 Open Interest Değişimi: {coin['oi_text']}\n"
                f"⚖️ Long/Short Ratio: {coin['ls_text']}\n"
                f"🏆 Rank: {coin['rank']}\n"
                f"🐋 Whale Pro v2 Skoru: {coin['score']}/10\n"
                f"📌 Durum: {coin['status']}\n"
                f"🧠 Sebep: {reasons_text}\n\n"
            )

        text += "⚠️ Bu kesin balina alımı değildir; hacim, momentum, trend ve türev piyasa verilerine göre olası büyük alım sinyalidir."

        await context.bot.send_message(chat_id=chat_id, text=text)

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"Whale Pro v2 hatası:\n{e}")


async def whale_v2_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global whale_v2_memory

    chat_id = update.effective_chat.id

    for job in context.job_queue.get_jobs_by_name(f"whale_v2_{chat_id}"):
        job.schedule_removal()

    try:
        data = fetch_markets(order="volume_desc", per_page=50)

        for coin in data:
            whale_v2_memory[coin["id"]] = coin["total_volume"]

        memory_count = len(whale_v2_memory)

    except Exception as e:
        await update.message.reply_text(f"Whale Pro v2 hafızası oluşturulamadı:\n{e}")
        return

    context.job_queue.run_repeating(
        whale_v2_scan,
        interval=300,
        first=300,
        chat_id=chat_id,
        name=f"whale_v2_{chat_id}"
    )

    await update.message.reply_text(
        "✅ Whale Pro v2 tarayıcısı açıldı.\n\n"
        f"📊 Hafızaya alınan coin sayısı: {memory_count}\n"
        "Bot her 5 dakikada bir hacim + momentum + trend + Open Interest + Long/Short kontrolü yapacak."
    )


async def whale_v2_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    jobs = context.job_queue.get_jobs_by_name(f"whale_v2_{chat_id}")

    if not jobs:
        await update.message.reply_text("Aktif Whale Pro v2 tarayıcısı yok.")
        return

    for job in jobs:
        job.schedule_removal()

    await update.message.reply_text("🛑 Whale Pro v2 tarayıcısı kapatıldı.")


async def whale_v2_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    jobs = context.job_queue.get_jobs_by_name(f"whale_v2_{chat_id}")

    status = "🟢 Aktif" if jobs else "🔴 Kapalı"

    text = (
        "🐋🚀 WHALE PRO V2 DURUMU\n\n"
        f"Durum: {status}\n"
        f"📊 Hafızadaki Coin: {len(whale_v2_memory)}\n"
        f"⏳ Cooldown'daki Coin: {len(whale_v2_cooldown)}\n"
        f"🔄 Tarama Aralığı: 5 Dakika\n"
        f"🛡️ Cooldown Süresi: 45 Dakika\n"
        f"🧠 Ek Filtre: Volume + Momentum + Trending + OI + Long/Short"
    )

    await update.message.reply_text(text)

async def auto_scan(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id

    try:
        data = fetch_markets(order="volume_desc", per_page=100)

        candidates = [
            coin for coin in data
            if coin.get("price_change_percentage_24h") is not None
            and coin["price_change_percentage_24h"] >= 7
            and coin["total_volume"] >= 100_000_000
        ]

        candidates = sorted(
            candidates,
            key=lambda x: x["price_change_percentage_24h"],
            reverse=True
        )[:5]

        if not candidates:
            return

        text = "🚨 OTOMATİK HACİM / MOMENTUM ALARMI\n\n"

        for coin in candidates:
            text += (
                f"🪙 {coin['symbol'].upper()} - {coin['name']}\n"
                f"💰 Fiyat: ${coin['current_price']:,.4f}\n"
                f"📈 24s Değişim: %{coin['price_change_percentage_24h']:.2f}\n"
                f"📊 24s Hacim: ${coin['total_volume']:,.0f}\n\n"
            )

        await context.bot.send_message(chat_id=chat_id, text=text)

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"Alarm hatası:\n{e}")


async def alarm_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    for job in context.job_queue.get_jobs_by_name(str(chat_id)):
        job.schedule_removal()

    context.job_queue.run_repeating(
        auto_scan,
        interval=900,
        first=10,
        chat_id=chat_id,
        name=str(chat_id)
    )

    await update.message.reply_text(
        "✅ Otomatik alarm sistemi açıldı.\n\n"
        "Bot her 15 dakikada bir hacim/momentum taraması yapacak."
    )


async def alarm_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    jobs = context.job_queue.get_jobs_by_name(str(chat_id))

    if not jobs:
        await update.message.reply_text("Zaten aktif alarm yok.")
        return

    for job in jobs:
        job.schedule_removal()

    await update.message.reply_text("🛑 Otomatik alarm sistemi kapatıldı.")


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("volume", volume))
    app.add_handler(CommandHandler("topvolume", topvolume))
    app.add_handler(CommandHandler("scan", scan))
    app.add_handler(CommandHandler("gainers", gainers))
    app.add_handler(CommandHandler("losers", losers))
    app.add_handler(CommandHandler("alarm_on", alarm_on))
    app.add_handler(CommandHandler("alarm_off", alarm_off))
    app.add_handler(CommandHandler("trending", trending))
    app.add_handler(CommandHandler("smart", smart))
    app.add_handler(CommandHandler("ta", ta))
    app.add_handler(CommandHandler("volume_spike_on", volume_spike_on))
    app.add_handler(CommandHandler("volume_spike_off", volume_spike_off))
    app.add_handler(CommandHandler("volume_spike_status", volume_spike_status))
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(CommandHandler("whale_on", whale_on))
    app.add_handler(CommandHandler("whale_off", whale_off))
    app.add_handler(CommandHandler("whale_status", whale_status))
    app.add_handler(CommandHandler("whale_pro_on", whale_pro_on))
    app.add_handler(CommandHandler("whale_pro_off", whale_pro_off))
    app.add_handler(CommandHandler("whale_pro_status", whale_pro_status))
    app.add_handler(CommandHandler("whale_v2_on", whale_v2_on))
    app.add_handler(CommandHandler("whale_v2_off", whale_v2_off))
    app.add_handler(CommandHandler("whale_v2_status", whale_v2_status))
    app.add_handler(CommandHandler("ta_on", ta_on))
    app.add_handler(CommandHandler("ta_off", ta_off))
    app.add_handler(CommandHandler("ta_status", ta_status))
    app.add_handler(CommandHandler("trade", trade))
    app.add_handler(CommandHandler("cache", cache_status))
    app.add_handler(CommandHandler("trade_scan_on", trade_scan_on))
    app.add_handler(CommandHandler("trade_scan_off", trade_scan_off))
    app.add_handler(CommandHandler("trade_scan_status", trade_scan_status))
    app.add_handler(CommandHandler("scalp", scalp))
    app.add_handler(CommandHandler("scalp_on", scalp_on))
    app.add_handler(CommandHandler("scalp_off", scalp_off))
    app.add_handler(CommandHandler("scalp_status", scalp_status))
    app.add_handler(CommandHandler("scalp_radar", scalp_radar))
                


    print("✅ Bot çalışıyor...")
    app.run_polling()


if __name__ == "__main__":
    main()