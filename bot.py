import asyncio
import aiohttp
import time
import math
from binance.client import Client

# ==============================
# CONFIG
# ==============================

TOKEN = "TELEGRAM_BOT_TOKEN"
CHAT_ID = "CHAT_ID"

API_KEY = "BINANCE_API"
API_SECRET = "BINANCE_SECRET"

client = Client(API_KEY, API_SECRET)

SYMBOLS = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT"]

INTERVAL = "5m"
HTF_INTERVAL = "1h"
LIMIT = 100

RISK_PERCENT = 1  # %1 risk

sent_signals = {}

# ==============================
# DATA
# ==============================

async def get_klines(session, symbol, interval):
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={LIMIT}"
    async with session.get(url) as res:
        return await res.json()

# ==============================
# EMA
# ==============================

def ema(values, period):
    k = 2 / (period + 1)
    ema_vals = [values[0]]
    for price in values[1:]:
        ema_vals.append(price * k + ema_vals[-1] * (1 - k))
    return ema_vals

# ==============================
# TREND
# ==============================

def trend(data):
    closes = [float(x[4]) for x in data]
    ema50 = ema(closes, 50)[-1]
    ema200 = ema(closes, 200)[-1]
    price = closes[-1]

    if price > ema50 and ema50 > ema200:
        return "long"
    if price < ema50 and ema50 < ema200:
        return "short"
    return None

# ==============================
# VOLUME
# ==============================

def volume_spike(data):
    volumes = [float(x[5]) for x in data]
    avg = sum(volumes[:-1]) / len(volumes[:-1])
    return volumes[-1] > avg * 1.5

# ==============================
# SWEEP
# ==============================

def sweep(data):
    low = float(data[-1][3])
    prev_low = min(float(x[3]) for x in data[-10:-1])
    close = float(data[-1][4])

    high = float(data[-1][2])
    prev_high = max(float(x[2]) for x in data[-10:-1])

    if low < prev_low and close > prev_low:
        return "long"
    if high > prev_high and close < prev_high:
        return "short"

    return None

# ==============================
# FVG
# ==============================

def fvg(data):
    c1 = data[-3]
    c2 = data[-2]
    c3 = data[-1]

    # bullish gap
    if float(c1[2]) < float(c3[3]):
        return "long"

    # bearish gap
    if float(c1[3]) > float(c3[2]):
        return "short"

    return None

# ==============================
# ORDER BLOCK (basit)
# ==============================

def order_block(data):
    last = data[-2]
    prev = data[-3]

    # bullish OB
    if float(prev[4]) < float(prev[1]) and float(last[4]) > float(last[1]):
        return "long"

    # bearish OB
    if float(prev[4]) > float(prev[1]) and float(last[4]) < float(last[1]):
        return "short"

    return None

# ==============================
# ATR (SL için)
# ==============================

def atr(data, period=14):
    trs = []

    for i in range(1, len(data)):
        high = float(data[i][2])
        low = float(data[i][3])
        prev_close = float(data[i-1][4])

        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)

    return sum(trs[-period:]) / period

# ==============================
# RISK
# ==============================

def calc_position(balance, entry, sl):
    risk_amount = balance * (RISK_PERCENT / 100)
    distance = abs(entry - sl)

    if distance == 0:
        return 0

    qty = risk_amount / distance
    return round(qty, 3)

# ==============================
# TELEGRAM
# ==============================

async def send_telegram(session, message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    await session.post(url, data={"chat_id": CHAT_ID, "text": message})

# ==============================
# TRADE
# ==============================

def open_trade(symbol, direction, qty):
    side = "BUY" if direction == "long" else "SELL"

    client.futures_create_order(
        symbol=symbol,
        side=side,
        type="MARKET",
        quantity=qty
    )

# ==============================
# SCAN
# ==============================

async def scan_symbol(session, symbol):

    data = await get_klines(session, symbol, INTERVAL)
    htf = await get_klines(session, symbol, HTF_INTERVAL)

    direction = sweep(data)
    vol = volume_spike(data)
    trend_ltf = trend(data)
    trend_htf = trend(htf)
    gap = fvg(data)
    ob = order_block(data)

    if direction and direction == trend_ltf == trend_htf and vol:

        # ekstra filtre
        if gap != direction and ob != direction:
            return

        now = time.time()
        last = sent_signals.get(symbol)

        if last and now - last < 900:
            return

        close = float(data[-1][4])
        atr_val = atr(data)

        if direction == "long":
            sl = close - atr_val
            tp1 = close + atr_val
            tp2 = close + atr_val * 2
            tp3 = close + atr_val * 3
        else:
            sl = close + atr_val
            tp1 = close - atr_val
            tp2 = close - atr_val * 2
            tp3 = close - atr_val * 3

        balance = float(client.futures_account_balance()[0]['balance'])
        qty = calc_position(balance, close, sl)

        msg = f"""
🔥 ELITE SNIPER 🔥

{symbol} | {direction.upper()}

Entry: {close:.4f}
SL: {sl:.4f}

TP1: {tp1:.4f}
TP2: {tp2:.4f}
TP3: {tp3:.4f}

Qty: {qty}
"""

        await send_telegram(session, msg)

        # AUTO TRADE
        open_trade(symbol, direction, qty)

        sent_signals[symbol] = now

# ==============================
# LOOP
# ==============================

async def main():
    async with aiohttp.ClientSession() as session:
        while True:
            tasks = [scan_symbol(session, s) for s in SYMBOLS]
            await asyncio.gather(*tasks)
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
