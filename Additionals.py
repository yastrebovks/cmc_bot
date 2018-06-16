import numpy
import sqlite3
import json
import ccxt
from datetime import datetime
from pprint import pprint
import time

PROFIT = 0
REFRESH = False
USE_LOG = True

USE_MACD = True
BEAR_PERC = 68

BULL_PERC = 99.8

maxv = {
    "BCH/ETH": 0.006,
    "XMR/ETH": 0.0006,
    "ETH/BTC": 0.00004,
    "ETC/ETH": 0.00007,
    "DASH/ETH": 0.0007
}

def init_exchange():
    #Create DB
    numpy.seterr(all='ignore')
    conn = sqlite3.connect('local.db')
    cursor = conn.cursor()
    orders_q = """
          create table if not exists
            orders (
              order_id TEXT,
              order_type TEXT,
              order_pair TEXT,
              order_created DATETIME,
              order_filled DATETIME,
              order_cancelled DATETIME,
              from_order_id TEXT,
              order_price REAL,
              order_amount REAL,
              order_spent REAL
            );
        """
    cursor.execute(orders_q)

    #Get Config-file
    with open('keys.txt', 'r', encoding='utf-8') as fl:
        keys = json.load(fl)

    try:
        exchange = eval('ccxt.%s({\'apiKey\':\"%s\",\'secret\':\"%s\"})' % (
            keys['marketplace'], keys['apiKey'], keys['secretKey']))

        MARKETS = keys['markets']
        ZeroFlag = 0
        ZeroCount = 0
        balance = 0
        try:
            balance = float(get_positive_accounts(exchange.fetch_balance()[keys['currency']])['free'])
        except:
            pass

        CAN_SPEND = keys['tradeCount']

        if((0.97 * CAN_SPEND) > balance and len(MARKETS) == 1
                and not (cursor.execute("SELECT * FROM orders").fetchone())):
            if(check_balances(MARKETS, CAN_SPEND, exchange)):
                ZeroFlag = 1
                ZeroCount = (CAN_SPEND - balance)/exchange.fetch_order_book(MARKETS[0], 1)['asks'][0][0]
            else:
                raise Exception

        REFRESH = False

        print(MARKETS)
        MARKUP = float(keys['markup'])
        STOCK_FEE = float(keys['fee'])
        ORDER_LIFE_TIME = float(keys['order_time'])

        StopFlag = False
        if 'StopFlag' in keys:
            StopFlag = keys['StopFlag']

        StopOrders = False
        if 'StopOrders' in keys:
            StopOrders = keys['StopOrders']

        ClosePositions = False
        if 'ClosePositions' in keys:
            ClosePositions = keys['ClosePositions']

        pprint("""
                Can Spend - %0.8f %s
                Fee: %0.8f, Markup: %0.8f, Balance: %0.8f %s
                """ % (CAN_SPEND, keys['currency'], keys['fee'], keys['markup'], CAN_SPEND, keys['currency'])
               )
    except Exception as e:
        print("Connection Error 3")

    main_properties = {
        "exchange": exchange,
        "MARKETS": MARKETS,
        "CAN_SPEND": CAN_SPEND,
        "MARKUP": MARKUP,
        "STOCK_FEE": STOCK_FEE,
        "ORDER_LIFE_TIME": ORDER_LIFE_TIME,
        "keys": keys,
        "REFRESH": REFRESH,
        "USE_MACD": True,
        "BEAR_PERC": BEAR_PERC,
        "BULL_PERC": BULL_PERC,
        "conn": conn,
        "cursor": cursor,
        "ZeroFlag": ZeroFlag,
        "ZeroCount": ZeroCount,
        "MarketPlace": keys['marketplace'],
        "StopFlag": StopFlag,
        "ClosePositions": ClosePositions,
        "maxv": maxv,
        "StopOrders": StopOrders,
        "LastPSAR": "null"
    }
    return main_properties


class ScriptError(Exception):
    pass


def balance_refresh(main_properties):
    if not REFRESH:
        return main_properties["CAN_SPEND"]
    new_spend = main_properties["CAN_SPEND"]
    if len(get_positive_accounts(main_properties["exchange"].fetch_balance()['total'])) == 1:
        new_spend = get_positive_accounts(main_properties["exchange"].fetch_balance()[main_properties["keys"]['currency']])['free'] * float(main_properties["keys"]['percent'])
    return new_spend


def get_positive_accounts(balance):
    result = {}
    currencies = list(balance.keys())
    for currency in currencies:
        if balance[currency] and balance[currency] > 0:
            result[currency] = balance[currency]
    return result


def log(*args):
    if USE_LOG:
        l = open("./log.txt", 'a', encoding='utf-8')
        print(datetime.now(), *args, file=l)
        l.close()
    print(datetime.now(), *args)


def log_macd(*args):
    if USE_LOG:
        l = open("./log_macd.txt", 'a', encoding='utf-8')
        print(datetime.now(), *args, file=l)
        l.close()
    print(datetime.now(), *args)


def get_ticks(main_properties, market, timeframe = '5m'):
    chart_data = {}
    res = main_properties["exchange"].fetch_ohlcv(symbol=market, timeframe=timeframe, limit=450)
    for item in res:
        dt_obj = (datetime.fromtimestamp(item[0] / 1000))
        ts = int(time.mktime(dt_obj.timetuple()))
        if not ts in chart_data:
            chart_data[ts] = {'open': float(item[1]), 'close': float(item[4]), 'high': float(item[2]),
                              'low': float(item[3])}

    res = main_properties["exchange"].fetch_trades(market)

    for trade in res:
        try:
            dt_obj = datetime.strptime(trade['datetime'], '%Y-%m-%dT%H:%M:%S.%fZ')
        except ValueError:
            dt_obj = datetime.strptime(trade['datetime'], '%Y-%m-%dT%H:%M:%SZ')

        time_const = 300 if timeframe == '5m' else 1800

        ts = int((time.mktime(dt_obj.timetuple()) / time_const)) * time_const
        if not ts in chart_data:
            chart_data[ts] = {'open': 0, 'close': 0, 'high': 0, 'low': 0}

        chart_data[ts]['close'] = float(trade['price'])

        if not chart_data[ts]['open']:
            chart_data[ts]['open'] = float(trade['price'])

        if not chart_data[ts]['high'] or chart_data[ts]['high'] < float(trade['price']):
            chart_data[ts]['high'] = float(trade['price'])

        if not chart_data[ts]['low'] or chart_data[ts]['low'] > float(trade['price']):
            chart_data[ts]['low'] = float(trade['price'])

    return chart_data

def profit(main_properties, from_order, market):
    if(not from_order['order_price']):
        return 1
    order_book = main_properties['exchange'].fetch_order_book(market, 100)['bids']
    old_rate = from_order['order_price'] * (1 + main_properties["MARKUP"])
    i = 0
    val = 0
    alpha = 0.2
    while (val < from_order['order_amount'] * (1 + alpha)):
        val += order_book[i][1]
        i += 1
    current_rate = order_book[max(i - 1, 0)][0]

    return ((current_rate / old_rate) - 1)

def check_balances(markets, can_spend, exchange):
    if(len(markets)== 1):
        pair = markets[0].split('/')
        curr_price = exchange.fetch_order_book(markets[0], 1)['asks'][0][0]
        if(get_positive_accounts(exchange.fetch_balance()[pair[0]])['free'] / curr_price >= 0.95 * can_spend):
            return 1
        else:
            print("Not enogh money!")
            return 0
    return 1