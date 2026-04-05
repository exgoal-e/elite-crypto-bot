import requests
import time
import os

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

symbols = [
"BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT"
]

sent = {}

def send(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

def get_data(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=15m&limit=100"
    return requests.get(url).json()

def check(symbol):
    data = get_data(symbol)
    closes = [float(x[4]) for x in data]

    A = closes[-20]
    B = closes[-15]
    C = closes[-10]

    AB = B - A
    BC = C - B

    if AB == 0:
        return

    ratio = abs(BC / AB)

    if 0.382 <= ratio <= 0.786:

        bullish = AB < 0 and BC > 0
        bearish = AB > 0 and BC < 0

        price = closes[-1]

        if bullish:
            key = f"{symbol}_long"
            if sent.get(key) != C:
                send(f"🚀 {symbol} LONG\nPrice: {price}")
                sent[key] = C

        if bearish:
            key = f"{symbol}_short"
            if sent.get(key) != C:
                send(f"🔻 {symbol} SHORT\nPrice: {price}")
                sent[key] = C

while True:
    for s in symbols:
        try:
            check(s)
        except:
            pass
    time.sleep(60)
