import os
import time
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")

volume_memory = {}
volume_cooldown = {}

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

            if old_volume is None:
                continue

            diff = volume - old_volume

            if old_volume <= 0:
                continue

            spike_percent = (diff / old_volume) * 100

            now = time.time()
last_alert_time = volume_cooldown.get(coin_id, 0)
cooldown_seconds = 30 * 60  # 30 dakika

if diff > 10_000_000 and spike_percent >= 3:
    if now - last_alert_time >= cooldown_seconds:
        alerts.append({
            "symbol": symbol,
            "name": name,
            "price": price,
            "volume": volume,
            "diff": diff,
            "spike_percent": spike_percent,
            "change": change
        })

        volume_cooldown[coin_id] = now

        alerts = sorted(
            alerts,
            key=lambda x: x["spike_percent"],
            reverse=True
        )[:5]

        if not alerts:
            return

        text = "🚨 ANLIK HACİM ARTIŞI TESPİT EDİLDİ\n\n"

        for coin in alerts:
            text += (
                f"🪙 {coin['symbol']} - {coin['name']}\n"
                f"💰 Fiyat: ${coin['price']:,.4f}\n"
                f"📈 24s Değişim: %{coin['change']:.2f}\n"
                f"📊 Hacim Artışı: +${coin['diff']:,.0f}\n"
                f"🔥 Artış Oranı: %{coin['spike_percent']:.2f}\n\n"
            )

        text += "⚠️ Bu finansal tavsiye değildir."

        await context.bot.send_message(chat_id=chat_id, text=text)

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"Volume spike hatası:\n{e}")


async def volume_spike_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    for job in context.job_queue.get_jobs_by_name(f"volume_spike_{chat_id}"):
        job.schedule_removal()

    context.job_queue.run_repeating(
        volume_spike_scan,
        interval=300,
        first=10,
        chat_id=chat_id,
        name=f"volume_spike_{chat_id}"
    )

    await update.message.reply_text(
        "✅ Anlık hacim artışı tarayıcısı açıldı.\n\n"
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
    app.add_handler(CommandHandler("volume_spike_on", volume_spike_on))
    app.add_handler(CommandHandler("volume_spike_off", volume_spike_off))

    print("✅ Bot çalışıyor...")
    app.run_polling()


if __name__ == "__main__":
    main()