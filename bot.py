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
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {
        "vs_currency": "usd",
        "days": 7,
        "interval": "hourly"
    }

    r = requests.get(url, params=params, timeout=20)

    if r.status_code != 200:
        raise Exception(f"TA veri hatası: {r.status_code}")

    data = r.json()
    prices = [item[1] for item in data.get("prices", [])]

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


    print("✅ Bot çalışıyor...")
    app.run_polling()


if __name__ == "__main__":
    main()