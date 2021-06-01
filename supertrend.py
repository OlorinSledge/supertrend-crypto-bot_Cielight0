import ccxt
import config
import schedule
import pandas as pd
import talib

pd.set_option('display.max_rows', None, "display.max_columns", None, 'display.width', 320)

import warnings

warnings.filterwarnings('ignore')

import numpy as np
from datetime import datetime
import time

exchange = ccxt.binance({
    "apiKey": config.BINANCE_API_KEY,
    "secret": config.BINANCE_SECRET_KEY
})


def tr(data):
    data['previous_close'] = data['close'].shift(1)
    data['high-low'] = abs(data['high'] - data['low'])
    data['high-pc'] = abs(data['high'] - data['previous_close'])
    data['low-pc'] = abs(data['low'] - data['previous_close'])

    tr = data[['high-low', 'high-pc', 'low-pc']].max(axis=1)

    return tr

def rsi(df, RSI_PERIOD =14):
    np_closes = df['close']
    rsi = talib.RSI(np_closes, RSI_PERIOD)
    df['rsi']=rsi
    return rsi

def adx(df, ADX_PERIOD=14):
    high = df['high']
    low = df['low']
    close = df['close']
    adx = talib.ADX(high, low, close, ADX_PERIOD)
    df['adx'] = adx
    return adx

def psar(df, acceleration=0.02,maximum=0.2):
    high = df['high']
    low = df['low']
    psar = talib.SAR(high, low, acceleration, maximum)
    df['psar'] = psar
    return psar


def atr(data, period):
    data['tr'] = tr(data)
    atr = data['tr'].rolling(period).mean()

    return atr


def supertrend(df, period=7, atr_multiplier=3):
    hl2 = (df['high'] + df['low']) / 2
    df['atr'] = atr(df, period)
    df['upperband'] = hl2 + (atr_multiplier * df['atr'])
    df['lowerband'] = hl2 - (atr_multiplier * df['atr'])
    df['in_uptrend'] = True

    for current in range(1, len(df.index)):
        previous = current - 1

        if df['close'][current] > df['upperband'][previous]:
            df['in_uptrend'][current] = True
        elif df['close'][current] < df['lowerband'][previous]:
            df['in_uptrend'][current] = False
        else:
            df['in_uptrend'][current] = df['in_uptrend'][previous]

            if df['in_uptrend'][current] and df['lowerband'][current] < df['lowerband'][previous]:
                df['lowerband'][current] = df['lowerband'][previous]

            if not df['in_uptrend'][current] and df['upperband'][current] > df['upperband'][previous]:
                df['upperband'][current] = df['upperband'][previous]

    #print(df)
    return df


in_position = False


def check_buy_sell_signals(df):
    global in_position
    rsi(df,14)
    adx(df,14)
    psar(df)
    print("checking for buy and sell signals")
    print(df.tail(5))
    last_row_index = len(df.index) - 1
    previous_row_index = last_row_index - 1

    if not df['in_uptrend'][previous_row_index] and df['in_uptrend'][last_row_index]:
        print("changed to uptrend, buy")
        if not in_position:
            order = exchange.create_market_buy_order('ETH/BUSD', 0.05)
            print(order)
            in_position = True
        else:
            print("already in position, nothing to do")

    if df['in_uptrend'][previous_row_index] and not df['in_uptrend'][last_row_index]:
        if in_position:
            print("changed to downtrend, sell")
            order = exchange.create_market_sell_order('ETH/BUSD', 0.05)
            print(order)
            in_position = False
        else:
            print("You aren't in position, nothing to sell")


def run_bot():
    print(f"Fetching new bars for {datetime.now().isoformat()}")
    bars = exchange.fetch_ohlcv('ETH/BUSD', timeframe='1m', limit=100)
    df = pd.DataFrame(bars[:-1], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    supertrend_data = supertrend(df)

    check_buy_sell_signals(supertrend_data)

schedule.every(10).seconds.do(run_bot)

while True:

    schedule.run_pending()
    time.sleep(1)
