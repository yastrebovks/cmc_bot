import time
import json
import sqlite3
import ccxt
import numpy
import talib
from pprint import pprint

import os

from datetime import datetime

### ���������� ����� � ���������� ###
Working = True
PROFIT = 0
REFRESH = False
USE_LOG = False

### ���������� �������� ###
USE_MACD = True  # True - ��������� ����� �� MACD, False - �������� � ��������� �������� �� �� ���

BEAR_PERC = 72  # % ��� ������� ��������� ��� �������

BULL_PERC = 99.8  # % ��� ������� ��������� ��� ����


# BEAR_PERC = 70  # % ��� ������� ��������� ��� �������

# BULL_PERC = 100  # ��� �� ����� ��������� �� ���������, ��� ������ ���� ������ �����
#######

# ������� ������������� �����

def init_exchange():
    # ���������� ���� � �����������
    with open('keys.txt', 'r', encoding='utf-8') as fl:
        keys = json.load(fl)

    # ������������ � �����
    # ���� � ������ ��� �������� ���������� �����, �� ���������� � HitBTC

    if not 'marketplace' in keys:
        try:
            exchange = ccxt.hitbtc2({
                "apiKey": keys['apiKey'],
                "secret": keys['secretKey'],
                # "enableRateLimit": True,
                # "verbose": True,
                # "password": password,
            })

        except Exception as e:
            print("Connection Error 1")
    else:
        try:
            exchange = eval('ccxt.%s({\'apiKey\':\"%s\",\'secret\':\"%s\"})' % (
            keys['marketplace'], keys['apiKey'], keys['secretKey']))
        except Exception as e:
            print("Connection Error 2")
    # ������� ��������� ����������� ���������
    try:

        # ������ ��������� ���

        MARKETS = keys['markets']

        # MARKETS = ['EOS/ETH']
        if 'tradeCount' in keys:
            print(1)
            # ����������� ������ ��� ��������� � ������ currency (��������, ETH)
            balance = get_positive_accounts(exchange.fetch_balance()[keys['currency']])['free']
            print(2)
            CAN_SPEND = keys['tradeCount']  # �������  ������ ������� � ��� % �� ������������� �������
            REFRESH = False
            # if CAN_SPEND > balance:
            # raise IOError("Trading account less for this trade!")
            print(3)
        else:
            balance = get_positive_accounts(exchange.fetch_balance()[keys['currency']])['free']
            CAN_SPEND = float(keys['percent']) * balance
            REFRESH = True

        print(MARKETS)
        MARKUP = float(keys['markup'])  # 0.001 = 0.1% �������� ������� ������� �� ������
        STOCK_FEE = float(keys['fee'])  # ����� �������� ����� �����
        ORDER_LIFE_TIME = float(keys['order_time'])  # ����� ��� ������ �������������� ������ �� ������� 0.5 = 30 ���.
        pprint("""
                Can Spend - %0.8f %s
                Fee: %0.8f, Markup: %0.8f, Balance: %0.8f %s
                """ % (CAN_SPEND, keys['currency'], keys['fee'], keys['markup'], CAN_SPEND, keys['currency'])
               )
    except Exception as e:
        print("Connection Error 3")
    return exchange, MARKETS, CAN_SPEND, MARKUP, STOCK_FEE, ORDER_LIFE_TIME, keys, REFRESH


numpy.seterr(all='ignore')
conn = sqlite3.connect('local.db')
cursor = conn.cursor()
# ���� �� ���������� ������ sqlite3, �� ����� ������� (������ ������)
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


# ����� ����������
class ScriptError(Exception):
    pass


# ��������� ������
def balance_refresh():
    if not REFRESH:
        return CAN_SPEND
    new_spend = CAN_SPEND
    if len(get_positive_accounts(exchange.fetch_balance()['total'])) == 1:
        new_spend = get_positive_accounts(exchange.fetch_balance()[keys['currency']])['free'] * float(keys['percent'])
    return new_spend


# ������ �������� ������� ��������
def get_positive_accounts(balance):
    result = {}
    currencies = list(balance.keys())
    for currency in currencies:
        if balance[currency] and balance[currency] > 0:
            result[currency] = balance[currency]
    return result


# ����� ���������� �� ������� � � ���-����
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


# ��������� ������������ ������ �����
def get_ticks(market):
    chart_data = {}
    # �������� ������ ������
    res = exchange.fetch_ohlcv(symbol=market, timeframe='5m', limit=450)
    # ���������� ������� ��� ����������� �������
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


# ���������� �������� �� ������ MACD
def get_macd_advice(chart_data):
    macd, macdsignal, macdhist = talib.MACD(numpy.asarray([chart_data[item]['close'] for item in sorted(chart_data)]),
                                            fastperiod=12, slowperiod=26, signalperiod=9)

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
        if ((macd[offset] > macdsignal[offset] and perc * 100 > BULL_PERC)  # ���������� �����
                or (
                        macd[offset] < macdsignal[offset] and perc * 100 < (100 - BEAR_PERC)
                )
        ):
            activity_time = True
            growing = True
        if offset in idx and not numpy.isnan(elem):
            # ����� ���������
            max_v = curr_v = 0  # �������� ��� ������ ����� �������
    return ({'trand': trand, 'growing': growing, 'maxv': max_v})


# ����� �� �������
def create_buy(market):
    global USE_LOG
    USE_LOG = True
    pair = market.split('/')
    # ����� ���� ������� ����
    order_book = exchange.fetch_order_book(market, 100)['asks']

    try:
        current_balance = get_positive_accounts(exchange.fetch_balance()[pair[1]])['free']
        try:
            old_position = get_positive_accounts(exchange.fetch_balance()[pair[0]])
        except:
            old_position = 0
        if 'free' in old_position:
            old_position = old_position['free']
    except:
        log("Error With Buy 1")
        return

    real_spend = current_balance if CAN_SPEND > current_balance else CAN_SPEND

    i = 0
    val = 0
    alpha = 0.1
    while (val < (real_spend / order_book[i][0]) * (1 + alpha)):
        val += order_book[i][1]
        i += 1

    current_rate = order_book[max(i - 1, 0)][0]
    # current_rate = float(exchange.fetch_order_book(market, 100)['asks'][1][0])
    # ��������� ����������� ���������������� ���������
    # CAN_SPEND = balance_refresh()
    can_buy = real_spend / current_rate

    log(market, """
        Current Rate - %0.8f
        By sum %0.8f %s can buy %0.8f %s
        Creating Order
        """ % (current_rate, real_spend, pair[1], can_buy, pair[0])
        )
    # current_rate /= 10
    # �������� �������� ������ �� ���������� ����
    order_res = {}
    try:
        order_res = exchange.create_order(market, 'limit', 'buy', can_buy, current_rate)
    except:
        log("Error with Buy Creation")
        log(order_res)
    iter = 5
    while (not ('price' in order_res) or not ('amount' in order_res)) and iter > 0:
        try:
            order_res = exchange.fetch_order(order_res['id'], symbol=market)
        except:
            log("Error with Buy Fetching")
        iter -= 1
        time.sleep(5)

    current_position = get_positive_accounts(exchange.fetch_balance()[pair[0]])['free']

    if (not ('price' in order_res) or not ('amount' in order_res)):
        if (old_position == current_position):
            log("Buy Creation Failure")
            return
        else:
            order_res['amount'] = current_position
            order_res['price'] = (current_balance - get_positive_accounts(exchange.fetch_balance()[pair[1]])[
                'free']) / current_position
            order_res['id'] = "NoID"

    # ��������� �� ��� �������� �������� �������
    print(order_res)
    if order_res:
        cursor.execute(
            """
              INSERT INTO orders(
                  order_id,
                  order_type,
                  order_pair,
                  order_created,
                  order_price,
                  order_amount,
                  order_spent
              ) VALUES (
                :order_id,
                'buy',
                :order_pair,
                datetime(),
                :order_price,
                :order_amount,
                :order_spent
              )
            """, {
                'order_id': order_res['id'],
                'order_pair': market,
                'order_price': order_res['price'],
                'order_amount': order_res['amount'],
                'order_spent': real_spend
            })
        conn.commit()
        log(order_res, " - Order Created!")
    else:
        log(market, """
            Error with creating order: %s
        """ % order_res['message'])
    USE_LOG = False


# ����� �� �������
def create_sell(from_order, market, trand=""):
    global USE_LOG
    USE_LOG = True
    pair = market.split('/')

    buy_order_q = """
        SELECT order_spent, order_amount FROM orders WHERE order_id='%s'
    """ % from_order

    if (from_order['order_id'] != "NoID"):
        try:
            from_order = from_order['order_id']
            order_amount = exchange.fetch_order(from_order, symbol=market)['amount']
            current_balance = get_positive_accounts(exchange.fetch_balance()[pair[0]])['free']
            order_spent = exchange.fetch_order(from_order, symbol=market)['price']
        except:
            log("Error with Sell order 1")
            return
    else:
        order_amount = from_order['amount']
        order_spent = from_order['order_price']
        try:
            current_balance = get_positive_accounts(exchange.fetch_balance()[pair[0]])['free']
        except:
            log("Error with Sell order 2")

    if order_amount > current_balance:
        order_amount = current_balance



    new_rate = (order_spent + order_spent * MARKUP)
    new_rate_fee = new_rate + (new_rate * STOCK_FEE) / (1 - STOCK_FEE)
    # ����� ���� ������� ����
    order_book = exchange.fetch_order_book(market, 100)['bids']

    i = 0
    val = 0
    alpha = 0.2
    while (val < order_amount * (1 + alpha)):
        val += order_book[i][1]
        i += 1

    current_rate = order_book[max(i - 1, 0)][0]

    if (trand == 'BEAR'):
        choosen_rate = current_rate
    else:
        choosen_rate = current_rate if current_rate > new_rate_fee else new_rate_fee

    log(market, """
        Was spent: %0.8f %s, Was Recieve: %0.8f %s
        New Price for Murkup %0.8f
        Fee %0.4f, After fee: %0.8f %s
        Main markup: %0.8f %s
        Current rate %0.8f
        Creating sell's order %0.8f
    """
        % (
            order_spent, pair[1], order_amount, pair[0],
            new_rate_fee,
            STOCK_FEE, (new_rate_fee * order_amount - new_rate_fee * order_amount * STOCK_FEE), pair[1],
            (new_rate_fee * order_amount - new_rate_fee * order_amount * STOCK_FEE) - order_spent*order_amount, pair[1],
            # MAIN MARKUP!
            current_rate,
            choosen_rate,
        )
        )
    # choosen_rate *= 10
    order_res = exchange.create_order(market, 'limit', 'sell', order_amount, choosen_rate)
    if not ('price' in order_res) or not ('amount' in order_res):
        order_res = exchange.fetch_order(order_res['id'], symbol=market)
    # ��������� �� �� ���������� ������
    if order_res:
        cursor.execute(
            """
              INSERT INTO orders(
                  order_id,
                  order_type,
                  order_pair,
                  order_created,
                  order_price,
                  order_amount,
                  from_order_id
              ) VALUES (
                :order_id,
                'sell',
                :order_pair,
                datetime(),
                :order_price,
                :order_amount,
                :from_order_id
              )
            """, {
                'order_id': order_res['id'],
                'order_pair': market,
                'order_price': choosen_rate,
                'order_amount': order_res['amount'],
                'from_order_id': from_order
            })
        conn.commit()
        log(trand, " - Reason for order.")
        log(order_res, " - Sell order created!")
    USE_LOG = False

# ����� �� �������
def create_sell_executive(from_order, market, trand=""):
    global USE_LOG
    USE_LOG = True
    pair = market.split('/')

    buy_order_q = """
        SELECT order_spent, order_amount FROM orders WHERE order_id='%s'
    """ % from_order

    if (from_order['order_id'] != "NoID"):
        try:
            from_order = from_order['order_id']
            order_amount = exchange.fetch_order(from_order, symbol=market)['amount']
            current_balance = get_positive_accounts(exchange.fetch_balance()[pair[0]])['free']
            order_spent = exchange.fetch_order(from_order, symbol=market)['price']
        except:
            log("Error with Sell order 1")
            return
    else:
        order_amount = from_order['amount']
        order_spent = from_order['order_price']
        try:
            current_balance = get_positive_accounts(exchange.fetch_balance()[pair[0]])['free']
        except:
            log("Error with Sell order 2")

    if order_amount > current_balance:
        order_amount = current_balance

    new_rate = (order_spent + order_spent * MARKUP)
    new_rate_fee = new_rate + (new_rate * STOCK_FEE) / (1 - STOCK_FEE)
    # ����� ���� ������� ����
    order_book = exchange.fetch_order_book(market, 100)['bids']

    i = 0
    val = 0
    alpha = 1
    while (val < order_amount * (1 + alpha)):
        val += order_book[i][1]
        i += 1

    current_rate = order_book[max(i - 1, 0)][0]
    choosen_rate = current_rate

    log(market, """
        Was spent: %0.8f %s, Was Recieve: %0.8f %s
        New Price for Murkup %0.8f
        Fee %0.4f, After fee: %0.8f %s
        Main markup: %0.8f %s
        Current rate %0.8f
        Creating sell's order %0.8f
    """
        % (
            order_spent, pair[1], order_amount, pair[0],
            new_rate_fee,
            STOCK_FEE, (new_rate_fee * order_amount - new_rate_fee * order_amount * STOCK_FEE), pair[1],
            (new_rate_fee * order_amount - new_rate_fee * order_amount * STOCK_FEE) - order_spent*order_amount, pair[1],
            # MAIN MARKUP!
            current_rate,
            choosen_rate,
        )
        )
    # choosen_rate *= 10
    order_res = exchange.create_order(market, 'limit', 'sell', order_amount, choosen_rate)
    if not ('price' in order_res) or not ('amount' in order_res):
        order_res = exchange.fetch_order(order_res['id'], symbol=market)
    # ��������� �� �� ���������� ������
    if order_res:
        cursor.execute(
            """
              INSERT INTO orders(
                  order_id,
                  order_type,
                  order_pair,
                  order_created,
                  order_price,
                  order_amount,
                  from_order_id
              ) VALUES (
                :order_id,
                'sell',
                :order_pair,
                datetime(),
                :order_price,
                :order_amount,
                :from_order_id
              )
            """, {
                'order_id': order_res['id'],
                'order_pair': market,
                'order_price': choosen_rate,
                'order_amount': order_res['amount'],
                'from_order_id': from_order
            })
        conn.commit()
        log(trand, " - Reason for order.")
        log(order_res, " - Sell order created!")
    USE_LOG = False


def profit(from_order, market):
    old_rate = exchange.fetch_order(from_order, symbol=market)['price'] * (1 + MARKUP)
    current_rate = float(exchange.fetch_ticker(market)['bid'])

    return (old_rate < current_rate)


# �������������� �����

exchange, MARKETS, CAN_SPEND, MARKUP, STOCK_FEE, ORDER_LIFE_TIME, keys, REFRESH = init_exchange()

# �������� ������, ����������� ����

while Working:
    try:
        # �������� �� ������ ��������� ���� �� ������ � ������
        for market in MARKETS:
            orders_q = """
                       SELECT
                         o.order_id,
                         o.order_type,
                         o.order_price,
                         o.order_amount,
                         o.order_filled,
                         o.order_created
                       FROM
                         orders o
                       WHERE
                            o.order_pair='%s'
                            AND (   
                                    (o.order_type = 'buy' and o.order_filled IS NULL)
                                    OR
                                    (o.order_type = 'buy' AND order_filled IS NOT NULL AND NOT EXISTS (
                                        SELECT 1 FROM orders o2 WHERE o2.from_order_id = o.order_id
                                        )
                                    )
                                    OR (
                                        o.order_type = 'sell' and o.order_filled IS NULL
                                    )
                                )
                            AND o.order_cancelled IS NULL
                   """ % market
            # �������� �� ���� ����������� ������� � ��������� ����
            orders_info = {}
            for row in cursor.execute(orders_q):
                orders_info[str(row[0])] = {'order_id': row[0], 'order_type': row[1], 'order_price': row[2],
                                            'order_amount': row[3], 'order_filled': row[4], 'order_created': row[5],
                                            'partially_filled': False, 'order_cancelled': False
                                            }
            if orders_info:
                # ���������, ���� �� ��������� ����� ��������� ������, � �������� � ��.
                for order in orders_info:
                    print("!")
                    pprint(order)
                    if not orders_info[order]['order_filled']:
                        # ����������� ������ ������ � �����
                        order_info = exchange.fetch_order(orders_info[order]['order_id'], symbol=market)
                        # ��������� ��������� ������
                        if order_info['status'] == 'closed':
                            if (order_info['fee'] == None) or not ('fee' in order_info):
                                order_info['fee'] = {}
                                order_info['fee']['cost'] = STOCK_FEE
                            cursor.execute(
                                """
                                  UPDATE orders
                                  SET
                                    order_filled=datetime(),
                                    order_price=:order_price,
                                    order_amount=:order_amount,
                                    order_spent=order_spent + :fee
                                  WHERE
                                    order_id = :order_id

                                """, {
                                    'order_id': order,
                                    'order_price': order_info['price'],
                                    'order_amount': order_info['amount'],
                                    'fee': float(order_info['fee']['cost'])
                                }
                            )
                            conn.commit()
                            log(orders_info[order], " - Order was closed in DB")
                            orders_info[order]['order_filled'] = datetime.now()
                        elif order_info['status'] == 'canceled':
                            pprint(order_info)
                            if order_info['filled'] > 0:
                                if (order_info['fee'] == None) or not ('fee' in order_info):
                                    order_info['fee'] = {}
                                    order_info['fee']['cost'] = STOCK_FEE
                                cursor.execute(
                                    """
                                      UPDATE orders
                                      SET
                                        order_filled=datetime(),
                                        order_price=:order_price,
                                        order_amount=:order_amount,
                                        order_spent=order_spent + :fee
                                      WHERE
                                        order_id = :order_id

                                    """, {
                                        'order_id': order,
                                        'order_price': order_info['price'],
                                        'order_amount': order_info['filled'],
                                        'fee': float(order_info['fee']['cost'])
                                    }
                                )
                                conn.commit()
                                log(orders_info[order], " - Order was closed in DB")
                                orders_info[order]['order_filled'] = datetime.now()
                            else:
                                if (order_info['fee'] == None) or not ('fee' in order_info):
                                    order_info['fee'] = {}
                                    order_info['fee']['cost'] = STOCK_FEE
                                cursor.execute(
                                    """
                                      UPDATE orders
                                      SET
                                        order_cancelled=datetime(),
                                        order_price=:order_price,
                                        order_amount=:order_amount,
                                        order_spent=order_spent + :fee
                                      WHERE
                                        order_id = :order_id

                                    """, {
                                        'order_id': order,
                                        'order_price': order_info['price'],
                                        'order_amount': order_info['amount'],
                                        'fee': float(order_info['fee']['cost'])
                                    }
                                )
                                conn.commit()
                                log(orders_info[order], " - Order was Canceled in DB")
                                orders_info[order]['order_cancelled'] = datetime.now()
                        else:
                            orders_info[order]['order_cancelled'] = False
                            # ��������� �� ��������� ���������� ������
                            if order_info['remaining'] != order_info['amount']:
                                orders_info[order]['partially_filled'] = True
                for order in orders_info:
                    if orders_info[order]['order_type'] == 'buy':
                        if orders_info[order]['order_filled']:
                            # ���� ����� �� ������� ��� ��������
                            if USE_MACD:
                                chart = get_ticks(market)
                                macd_advice = get_macd_advice(chart_data=chart)  # ���������, ����� �� ������� sell
                                if (macd_advice['trand'] == 'BEAR' and not profit(
                                        from_order=orders_info[order]['order_id'], market=market)) or \
                                        (macd_advice['trand'] == 'BULL' and macd_advice['growing']):
                                    print('Not create order')
                                else:
                                    # log_macd(talib.MACD(numpy.asarray([chart[item]['close'] for item in sorted(chart)]),
                                    #                   fastperiod=12, slowperiod=26, signalperiod=9))
                                    log(market, "Start to create Sell order")
                                    log("MAXV: ", macd_advice['maxv'])
                                    if (market == "BCH/ETH" and abs(macd_advice['maxv']) >= 0.006) or \
                                        (abs(macd_advice['maxv']) >= 0.0006 and market == "XMR/ETH") or \
                                        (market != "BCH/ETH" and market != "XMR/ETH"):
                                        create_sell(from_order=orders_info[order], market=market,
                                                    trand=macd_advice['trand'])
                            else:  # ������� sell ���� ��������� ����� ���������
                                log(market, "Start to create Sell order")
                                log("MAXV: ", macd_advice['maxv'])
                                create_sell(from_order=orders_info[order], market=market)
                        else:

                            print(
                                "NOT FILLED")  # ���� buy �� ��� ��������, � ������ ���������� ������� ��� ������ ������, ��������
                            # not orders_info[order]['partially_filled'] and
                            time_passed = int((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()) - int(
                                time.mktime(datetime.strptime(orders_info[order]['order_created'],
                                                              "%Y-%m-%d %H:%M:%S").timetuple()))
                            if not orders_info[order]['partially_filled'] and not orders_info[order]['order_cancelled']:
                                if time_passed > ORDER_LIFE_TIME * 60:
                                    cancel_res = exchange.cancel_order(order, symbol=market)
                                    if cancel_res['status'] == 'canceled':
                                        cursor.execute(
                                            """
                                              UPDATE orders
                                              SET
                                                order_cancelled=datetime()
                                              WHERE
                                                order_id = :order_id
                                            """, {
                                                'order_id': order
                                            }
                                        )
                                        conn.commit()
                                        log(orders_info[order], " - Order was Canceled in DB")
                            if orders_info[order]['partially_filled'] and not orders_info[order]['order_cancelled']:
                                if time_passed > 10:
                                    cancel_res = exchange.cancel_order(order, symbol=market)
                    else:  # ����� �� �������
                        print("!")
                        if not orders_info[order]['partially_filled'] and not orders_info[order]['order_cancelled']:
                            time_passed = int((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()) - int(
                                time.mktime(datetime.strptime(orders_info[order]['order_created'],
                                                              "%Y-%m-%d %H:%M:%S").timetuple()))
                            if time_passed > 600:
                                cancel_res = exchange.cancel_order(order, symbol=market)
                                create_sell_executive(from_order=orders_info[order], market=market, trand="Executive")
            else:
                if(not StopFlag):
                    # ��������� MACD, ���� ����� � ������ ���������, ���������� ����� �� �������
                    if USE_MACD:
                        chart = get_ticks(market)
                        macd_advice = get_macd_advice(chart_data=chart)
                        # ������� ��� �������: BEAR � �������� ������� MACD
                        print(macd_advice['trand'])
                        if macd_advice['trand'] == 'BEAR' and macd_advice['growing']:
                            log("MAXV: ", macd_advice['maxv'])
                            if (market == "BCH/ETH" and abs(macd_advice['maxv']) >= 0.006) or \
                                (abs(macd_advice['maxv']) >= 0.0006 and market == "XMR/ETH") or \
                                (market != "BCH/ETH" and market != "XMR/ETH"):
                                create_buy(market=market)
                            # log_macd(talib.MACD(numpy.asarray([chart[item]['close'] for item in sorted(chart)]),
                            #                   fastperiod=12, slowperiod=26, signalperiod=9))
                    else:
                        create_buy(market=market)
                else:
                    Working = False
        time.sleep(5)
    except Exception as e:
        print("Exit bot")
        print(e)