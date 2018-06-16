from pprint import pprint
import json
import os
import sys
import time
import numpy
import asciichartpy as asciichart
import hitbtc
from datetime import datetime
import talib
from Errors import err_noid


BEAR_PERC = 78  # % что считаем поворотом при медведе

BULL_PERC = 99.8  # % что считаем поворотом при быке

def get_positive_accounts(balance):
    result = {}
    currencies = list(balance.keys())
    for currency in currencies:
        if balance[currency] and balance[currency] > 0:
            result[currency] = balance[currency]
    return result

def mid_balance(exhange):
    trading_balance = exchange.fetch_balance()
    trading_balance = get_positive_accounts(trading_balance['free'])

    currencie = "ETH"

    total_low = 0
    total_high = 0

    for market in trading_balance:
        try:
            if(not market == currencie):
                order_book = exchange.fetch_order_book(str(market+"/"+currencie), 100)

                i = 0
                val = 0
                while (val < trading_balance[market]):
                    val += order_book['bids'][i][1]
                    i += 1
                current_rate_low = order_book['bids'][max(i - 1, 0)][0] * trading_balance[market]

                i = 0
                val = 0
                while (val < trading_balance[market]):
                    val += order_book['asks'][i][1]
                    i += 1
                current_rate_high = order_book['asks'][max(i - 1, 0)][0] * trading_balance[market]

                total_low += current_rate_low
                total_high += current_rate_high
            else:
                total_low += trading_balance[market]
                total_high += trading_balance[market]
        except:
            pass

    print("Account's price between", total_low, currencie, "and", total_high, currencie)
    return

# Получение исторических данных биржи
def get_ticks(market):
    chart_data = {}
    # Получаем данные свечей
    res = exchange.fetch_ohlcv(symbol = market, timeframe = '5m', limit=350)
    # Заполнение массива для дальнейшего анализа
    for item in res:
        dt_obj = (datetime.fromtimestamp(item[0] / 1000))
        ts = int(time.mktime(dt_obj.timetuple()))
        if not ts in chart_data:
            chart_data[ts] = {'open': float(item[1]), 'close': float(item[4]), 'high': float(item[2]),
                              'low': float(item[3])}

    res = exchange.fetch_trades(market)

    for trade in res:
        try:
            dt_obj = datetime.strptime(trade['datetime'], '%Y-%m-%dT%H:%M:%S.%fZ')
        except ValueError:
            dt_obj = datetime.strptime(trade['datetime'], '%Y-%m-%dT%H:%M:%SZ')

        ts = int((time.mktime(dt_obj.timetuple()) / 300)) * 300
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


# Анализатор сигналов на основе MACD
def get_macd_advice(chart_data):
    macd, macdsignal, macdhist = talib.MACD(numpy.asarray([chart_data[item]['close'] for item in sorted(chart_data)]),
                                            fastperiod=12, slowperiod=26, signalperiod=9)

    #print("MACD:")
    #pprint(macd)
    #print("MACD Signal:")
    #pprint(macdsignal)
    #print("MACD Hist:")
    #pprint(macdhist)

    idx = numpy.argwhere(numpy.diff(numpy.sign(macd - macdsignal)) != 0).reshape(-1) + 0
    trand = 'BULL' if macd[-1] > macdsignal[-1] else 'BEAR'
    max_v = 0
    activity_time = False
    growing = False
    for offset, elem in enumerate(macdhist):
        growing = False
        curr_v = macd[offset] - macdsignal[offset]
        if abs(curr_v) > abs(max_v):
            max_v = curr_v
        perc = curr_v / max_v
        if ((macd[offset] > macdsignal[offset] and perc * 100 > BULL_PERC)  # восходящий тренд
                or (
                        macd[offset] < macdsignal[offset] and perc * 100 < (100 - BEAR_PERC)
                )
        ):
            activity_time = True
            growing = True
        if offset in idx and not numpy.isnan(elem):
            # тренд изменился
            max_v = curr_v = 0  # обнуляем пик спреда между линиями
    return ({'trand': trand, 'growing': growing})

root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath("New.txt"))))
sys.path.append(root + '/python')

import ccxt  # noqa: E402

##############################################
print("My HitBTC")
public_key = "42555f6f72ff2b5f5a7a1b0a52cafd17"
secret = "e077ccce0034bbe610ffa1068630bdac"

exchange = ccxt.hitbtc2({
    "apiKey": public_key,
    "secret": secret,
   # "verbose": True,
    #"password": password,
})

##Балансы
#ex = exchange.create_order("BCH/ETH", 'limit','sell',0.22, 2.05)
trading_balance = exchange.fetch_balance()
account_balance = exchange.fetch_balance({'type': 'account'})

print(get_positive_accounts(exchange.fetch_balance()['ETH'])['free'])

pprint('Trading balance:')
print(get_positive_accounts(trading_balance['free']))
pprint('Account balance:')
pprint(get_positive_accounts(account_balance['total']))
pprint( exchange.fetch_open_orders())
mid_balance(exchange)
##########################################
print("Bittrex1")
public_key = "8218caa78a7c4a4ab4b1077ae7677d1f"
secret = "82e20dc47ba64e3eb89e64f6b9981975"

print(datetime.utcnow())

exchange = ccxt.bittrex({
    "apiKey": public_key,
    "secret": secret,
   # "verbose": True,
    #"password": password,
})
#exchange.cancel_order('73c89d00-584c-4abf-b513-c57c2635e1cf')
#exchange.create_order("XRP/ETH",'limit', 'sell', 2678.31684386, 0.00111)
##Балансы
trading_balance = exchange.fetch_balance()
account_balance = exchange.fetch_balance({'type': 'account'})

pprint('Trading balance:')
print(get_positive_accounts(trading_balance['free']))
pprint('Account balance:')
pprint(get_positive_accounts(account_balance['total']))

pprint( exchange.fetch_open_orders())
mid_balance(exchange)
##############################################
print("Mikhail HitBTC")
public_key = "e477da3eb0df760c2658af9e64970b9a"
secret = "f3ffe041fd929308c58eefe00eaa0acd"

exchange = ccxt.hitbtc2({
    "apiKey": public_key,
    "secret": secret,
   # "verbose": True,
    #"password": password,
})
##Балансы
#ex = exchange.create_order("BCH/ETH", 'limit','sell',0.26, 2.15)
#print(len(exchange.fetch_ohlcv(symbol = "BCH/ETH", timeframe = '1m', limit=350)))

trading_balance = exchange.fetch_balance()
account_balance = exchange.fetch_balance({'type': 'account'})

#pprint(len(exchange.fetch_ohlcv("ETH/BTC", '5m')))

pprint('Trading balance:')
print(get_positive_accounts(trading_balance['free']))
pprint('Account balance:')
pprint(get_positive_accounts(account_balance['total']))

pprint(exchange.fetch_open_orders())
mid_balance(exchange)
##############################################
print("Bittrex2")
public_key = "7cbe62ead6824193b99e1b865dfe2269"
secret = "301c0d0a46234cd5bbb0ff0a61906351"

exchange = ccxt.bittrex({
    "apiKey": public_key,
    "secret": secret,
   # "verbose": True,
    #"password": password,
})
#exchange.cancel_order('a09bc936-8d7a-463d-92a3-934046c14056')
#ex = exchange.create_order("XMR/ETH",'limit', 'sell', 2.85650263, 0.293)

##Балансы
trading_balance = exchange.fetch_balance()
account_balance = exchange.fetch_balance({'type': 'account'})
#exchange.create_order("BCH/ETH",'limit', 'sell',  0.559458, 1.95)


pprint('Trading balance:')
print(get_positive_accounts(trading_balance['free']))
pprint('Account balance:')
pprint(get_positive_accounts(account_balance['total']))

pprint(exchange.fetch_open_orders())
mid_balance(exchange)
####################################################################
print("ZEC HitBTC")
public_key = "e5aeecc53f3d6b0cabf7684de2e3eb0e"
secret = "023bcb3a43bf3eb5075468e82073be10"

exchange = ccxt.hitbtc2({
    "apiKey": public_key,
    "secret": secret,
   # "verbose": True,
    #"password": password,
})
##Балансы
#ex = exchange.create_order("ZEC/ETH", 'limit','sell',0.14, 0.5)
trading_balance = exchange.fetch_balance()
account_balance = exchange.fetch_balance({'type': 'account'})

#exchange.create_order("DASH/ETH", 'market', 'sell', 0.34)
#exchange.create_order("ETC/ETH", 'market', 'sell', 4.37)
#exchange.create_order("ETH/BTC", 'limit', 'sell', 0.413, 0.0789)

pprint('Trading balance:')
print(get_positive_accounts(trading_balance['free']))
pprint('Account balance:')
pprint(get_positive_accounts(account_balance['total']))

pprint(exchange.fetch_open_orders())
mid_balance(exchange)
####################################################################
print("BIG HitBTC")
public_key = "678fe9e2e5ef183457b5e69ac3a6952b"
secret = "82aeea112508f21bcd26b201822e0361"

exchange = ccxt.hitbtc2({
    "apiKey": public_key,
    "secret": secret,
   # "verbose": True,
    #"password": password,
})
##Балансы
#ex = exchange.create_order("ZEC/ETH", 'limit','sell',0.5, 0.41)
trading_balance = exchange.fetch_balance()
account_balance = exchange.fetch_balance({'type': 'account'})

#print("Ticks 5m:")
#pprint(ticks)
#print("MACD Out:")
#pprint(macd_out)

pprint('Trading balance:')
print(get_positive_accounts(trading_balance['free']))
pprint('Account balance:')
pprint(get_positive_accounts(account_balance['total']))

#pprint(exchange.fetch_open_orders())
mid_balance(exchange)
####################################################################
print("BTC HitBTC")
public_key = "86e68904074e1d83c4308aa833304120"
secret = "56815e308e75abe47d16ea8cee0b9887"

exchange = ccxt.hitbtc2({
    "apiKey": public_key,
    "secret": secret,
   # "verbose": True,
    #"password": password,
})
##Балансы
#ex = exchange.create_order("ETH/BTC", 'limit','sell', 5.684, 0.078)
trading_balance = exchange.fetch_balance()
account_balance = exchange.fetch_balance({'type': 'account'})

#print("Ticks 5m:")
#pprint(ticks)
#print("MACD Out:")
#pprint(macd_out)

pprint('Trading balance:')
print(get_positive_accounts(trading_balance['free']))
pprint('Account balance:')
pprint(get_positive_accounts(account_balance['total']))

pprint(exchange.fetch_open_orders())
mid_balance(exchange)
####################################################################
print("Handy Bittrex")
public_key = "4ca5a1d9ca49477f9f9ba90b9e243b5a"
secret = "c192a57a6f0049e0842713654f400ef9"

exchange = ccxt.bittrex({
    "apiKey": public_key,
    "secret": secret,
   # "verbose": True,
    #"password": password,
})
##Балансы
#ex = exchange.create_order("ZEC/ETH", 'limit','sell',0.5, 0.41)
trading_balance = exchange.fetch_balance()
account_balance = exchange.fetch_balance({'type': 'account'})

#print("Ticks 5m:")
#pprint(ticks)
#print("MACD Out:")
#pprint(macd_out)

pprint('Trading balance:')
print(get_positive_accounts(trading_balance['free']))
pprint('Account balance:')
pprint(get_positive_accounts(account_balance['total']))
mid_balance(exchange)
####################################################################
time.sleep(100)
print("Binance")
public_key = "Unh9J0ZGbi65b9B3lJ3fDAKAWmD5mUz0v9mApXka0dE2dhBJxEcFoB8kC0Y79Z1m"
secret = "DkX86aWneavBCCwkzUD2ItKIYooEyqAf5yYEPxbjcQDaVx5m9SrZnfsliFTve5Bd"

exchange = ccxt.binance({
    "apiKey": public_key,
    "secret": secret,
   # "verbose": True,
    #"password": password,
})
##Балансы
trading_balance = exchange.fetch_balance()
account_balance = exchange.fetch_balance({'type': 'account'})



pprint('Trading balance:')
print(get_positive_accounts(trading_balance['free']))
pprint('Account balance:')
pprint(get_positive_accounts(account_balance['total']))

pprint( exchange.fetch_open_orders())
#tm = datetime.strptime(exchange.fetch_order("330110f74b624f2db10862dd3550f69b")['datetime'], "'%Y-%m-%dT%H:%M:%S.%fZ")

#print(exchange.fetch_order("f5bc0b50331e4941ac16530e29750027"))
#pprint((exchange.fetch_order_book("XMR/ETH")['bids'][1][0]))


time.sleep(100)
