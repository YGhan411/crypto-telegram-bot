import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")

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

    print("✅ Bot çalışıyor...")
    app.run_polling()


if __name__ == "__main__":
    main()