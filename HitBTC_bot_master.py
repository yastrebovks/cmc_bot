import time
import json
import sqlite3
import ccxt
import numpy
import talib
from pprint import pprint

import os

from datetime import datetime


# Функция инициализации биржи

def init_exchange():
    # Подгружаем файл с настройками
    with open('keys_my.txt', 'r', encoding='utf-8') as fl:
        keys = json.load(fl)
    # Подключаемся к бирже
    # Если в списке нет указания конкретной биржи, то коннектимя к HitBTC
    if not 'marketplace' in keys:
        try:
            exchange = ccxt.hitbtc2({
                "apiKey": keys['apiKey'],
                "secret": keys['secretKey'],
                #"enableRateLimit": True,
                #"verbose": True,
                #"password": password,
            })

        except Exception as e:
            print("Ошибка подключения к бирже1")
    else:
        try:
            exchange = eval('ccxt.%s({\'apiKey\':\"%s\",\'secret\':\"%s\"})' % (keys['marketplace'], keys['apiKey'], keys['secretKey']))
        except Exception as e:
            print("Ошибка подключения к бирже2")
    # Пробуем выгрузить необходимые параметры
    try:

        # Список торгуемых пар

        MARKETS = keys['markets']

        #MARKETS = ['EOS/ETH']

        # Запрашиваем баланс для трейдинга в валюте currency (например, ETH)
        balance = get_positive_accounts(exchange.fetch_balance()[keys['currency']])['free']
        CAN_SPEND = float(keys['percent']) * balance  # Сколько  готовы вложить в бай % от трейдингового баланса
        #CAN_SPEND = 0.001
        print(MARKETS)
        MARKUP = float(keys['markup'])  # 0.001 = 0.1% желаемый процент прибыли со сделки
        STOCK_FEE = float(keys['fee'])  # Какую комиссию берет биржа
        ORDER_LIFE_TIME = float(keys['order_time'])  # Время для отмены неисполненного ордера на покупку 0.5 = 30 сек.
        pprint("""
                Готовы тратить - %0.8f %s
                Комиссия: %0.8f, желаемая прибыль: %0.8f, торговый баланс: %0.8f %s
                """ % (CAN_SPEND, keys['currency'], keys['fee'], keys['markup'], CAN_SPEND, keys['currency'])
               )
    except Exception as e:
        print("Ошибка подключения к бирже1")
    return exchange, MARKETS, CAN_SPEND, MARKUP, STOCK_FEE, ORDER_LIFE_TIME, keys


### Анализатор сигналов ###
USE_MACD = True  # True - оценивать тренд по MACD, False - покупать и продавать невзирая ни на что

BEAR_PERC = 70  # % что считаем поворотом при медведе

BULL_PERC = 98  # % что считаем поворотом при быке

# BEAR_PERC = 70  # % что считаем поворотом при медведе

# BULL_PERC = 100  # Так он будет продавать по минималке, как только курс пойдет вверх
#######
USE_LOG = False
numpy.seterr(all='ignore')
conn = sqlite3.connect('local.db')
cursor = conn.cursor()
# Если не существует таблиц sqlite3, их нужно создать (первый запуск)
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

# Класс исключений
class ScriptError(Exception):
    pass

# Обновляем баланс
def balance_refresh():
    new_spend = CAN_SPEND
    if len(get_positive_accounts(exchange.fetch_balance()['total'])) == 1:
        new_spend = get_positive_accounts(exchange.fetch_balance()[keys['currency']])['free'] * float(keys['percent'])
    return new_spend

# Узнаем активные балансы аккаунта
def get_positive_accounts(balance):
    result = {}
    currencies = list(balance.keys())
    for currency in currencies:
        if balance[currency] and balance[currency] > 0:
            result[currency] = balance[currency]
    return result


# Вывод информации на дисплей и в лог-файл
def log(*args):
    if USE_LOG:
        l = open("./log.txt", 'a', encoding='utf-8')
        print(datetime.now(), *args, file=l)
        l.close()
    print(datetime.now(), *args)


# Получение исторических данных биржи
def get_ticks(market):
    chart_data = {}
    # Получаем данные свечей
    res = exchange.fetch_ohlcv(market, '1m')
    print("OHLCV")
    #print(res)
    # Заполнение массива для дальнейшего анализа
    for item in res:
        dt_obj = (datetime.fromtimestamp(item[0] / 1000))
        #print(item)
        ts = int(time.mktime(dt_obj.timetuple()))
        if not ts in chart_data:
            chart_data[ts] = {'open': float(item[1]), 'close': float(item[4]), 'high': float(item[2]),
                              'low': float(item[3])}
            #print(chart_data[ts]['close'])
    print("Close from Get_ticks!")
    return chart_data


# Анализатор сигналов на основе MACD
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

# Ордер на покупку
def create_buy(market):
    global USE_LOG
    USE_LOG = True
    log(market, 'Создаем ордер на покупку')
    log(market, 'Получаем текущие курсы')
    # Берем цену лучшего аска
    current_rate = float(exchange.fetch_ticker(market)['ask'])
    # Проверяем возможность реинвестирования процентов
    CAN_SPEND = balance_refresh()
    can_buy = CAN_SPEND / current_rate
    pair = market.split('/')
    log(market, """
        Текущая цена - %0.8f
        На сумму %0.8f %s можно купить %0.8f %s
        Создаю ордер на покупку
        """ % (current_rate, CAN_SPEND, pair[1], can_buy, pair[0])
        )
    # Создание пробного ордера по заниженной цене
    #current_rate /= 10

    print(current_rate)
    #time.sleep(10)
    order_res = exchange.create_order(market, 'limit', 'buy', can_buy, current_rate)
    # Заполняем БД при успешном создании оредера
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
              ) Values (
                :order_id,
                'buy',
                :order_pair,
                datetime(),
                :order_price,
                :order_amount,
                :order_spent
              )
            """, {
                'order_id': order_res['info']['clientOrderId'],
                'order_pair': market,
                'order_price': order_res['price'],
                'order_amount': order_res['amount'],
                'order_spent': CAN_SPEND
            })
        conn.commit()
        log("Создан ордер на покупку %s" % order_res['info']['clientOrderId'])
    else:
        log(market, """
            Не удалось создать ордер: %s
        """ % order_res['message'])
    USE_LOG = False

# Ордер на продажу
def create_sell(from_order, market):
    global USE_LOG
    USE_LOG = True
    pair = market.split('/')
    buy_order_q = """
        SELECT order_spent, order_amount FROM orders WHERE order_id='%s'
    """ % from_order

    order_amount = exchange.fetch_order(from_order)['amount']
    order_spent = exchange.fetch_order(from_order)['price']*order_amount

    print(order_spent)
    print(order_amount)
    new_rate = (order_spent + order_spent * MARKUP) / order_amount
    new_rate_fee = new_rate + (new_rate * STOCK_FEE) / (1 - STOCK_FEE)
    # Берем цену лучшего бида
    current_rate = float(exchange.fetch_ticker(market)['bid'])
    choosen_rate = current_rate if current_rate > new_rate_fee else new_rate_fee
    log(market, """
        Итого на этот ордер было потрачено %0.8f %s, получено %0.8f %s
        Что бы выйти в плюс, необходимо продать купленную валюту по курсу %0.8f
        Тогда, после вычета комиссии %0.4f останется сумма %0.8f %s
        Итоговая прибыль составит %0.8f %s
        Текущий курс продажи %0.8f
        Создаю ордер на продажу по курсу %0.8f
    """
        % (
            order_spent, pair[1], order_amount, pair[0],
            new_rate_fee,
            STOCK_FEE, (new_rate_fee * order_amount - new_rate_fee * order_amount * STOCK_FEE), pair[1],
            (new_rate_fee * order_amount - new_rate_fee * order_amount * STOCK_FEE) - order_spent, pair[1],
            current_rate,
            choosen_rate,
        )
        )
    #time.sleep(100)
    order_res = exchange.create_order(market, 'limit', 'sell', order_amount, choosen_rate)
    # Заполняем БД по созданному ордеру
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
              ) Values (
                :order_id,
                'sell',
                :order_pair,
                datetime(),
                :order_price,
                :order_amount,
                :from_order_id
              )
            """, {
                'order_id': order_res['info']['clientOrderId'],
                'order_pair': market,
                'order_price': choosen_rate,
                'order_amount': order_amount,
                'from_order_id': from_order
            })
        conn.commit()
        log(market, "Создан ордер на продажу %s" % order_res['info']['clientOrderId'])
    USE_LOG = False


# Инициализируем биржу

exchange, MARKETS, CAN_SPEND, MARKUP, STOCK_FEE, ORDER_LIFE_TIME, keys = init_exchange()

# Основная логика, бесконечный цикл

while True:
    try:
        # Проходим по каждой торгуемой паре из списка в начале
        for market in MARKETS:
            log(market, "Получаем все неисполненные ордера по БД")
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
            # Проходим по всем сохраненным ордерам в локальной базе
            orders_info = {}
            for row in cursor.execute(orders_q):
                orders_info[str(row[0])] = {'order_id': row[0], 'order_type': row[1], 'order_price': row[2],
                                            'order_amount': row[3], 'order_filled': row[4], 'order_created': row[5],
                                            'partially_filled': False, 'order_cancelled': False
                                            }
                print(row[4])
            if orders_info:
                # Проверяем, были ли выполнены ранее созданные ордера, и помечаем в БД.
                log(market, "Получены неисполненные ордера из БД", orders_info)
                for order in orders_info:
                    if not orders_info[order]['order_filled']:
                        log(market, "Проверяем состояние ордера %s" % order)
                        # Запрашиваем данные ордера у биржи
                        order_info = exchange.fetch_order(orders_info[order]['order_id'])
                        print(order_info)
                        # Проверяем пришедший статус
                        if order_info['status'] == 'closed':
                            log(market, 'Ордер %s уже выполнен!' % order)

                            if(order_info['fee'] == None):
                                print("FEEEEE")
                                order_info['fee'] = 0
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
                                    'fee': float(order_info['fee'])
                                }
                            )
                            conn.commit()
                            log(market, "Ордер %s помечен выполненным в БД" % order)
                            orders_info[order]['order_filled'] = datetime.now()
                        elif order_info['status'] == 'canceled':
                            log(market, 'Ордер %s отменен!' % order)
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
                                    'fee': (order_info['fee'])
                                }
                            )
                            conn.commit()
                            log(market, "Ордер %s помечен отмененным в БД" % order)
                            orders_info[order]['order_cancelled'] = datetime.now()

                        else:
                            orders_info[order]['order_cancelled'] = False
                            log(market, "Ордер %s еще не выполнен" % order)
                            # Проверяем на частичное выполнение ордера
                            if order_info['remaining'] != order_info['amount']:
                                orders_info[order]['partially_filled'] = True
                for order in orders_info:
                    if orders_info[order]['order_type'] == 'buy':
                        if orders_info[order]['order_filled']:
                            # если ордер на покупку был выполнен
                            if USE_MACD:
                                macd_advice = get_macd_advice(
                                    chart_data=get_ticks(market))  # проверяем, можно ли создать sell
                                if macd_advice['trand'] == 'BEAR' or (
                                        macd_advice['trand'] == 'BULL' and macd_advice['growing']):
                                    log(market,
                                        'Для ордера %s не создаем ордер на продажу, т.к. ситуация на рынке неподходящая' % order)
                                else:
                                    log(market, "Для выполненного ордера на покупку выставляем ордер на продажу")
                                    create_sell(from_order=orders_info[order]['order_id'], market=market)
                            else:  # создаем sell если тенденция рынка позволяет
                                log(market, "Для выполненного ордера на покупку выставляем ордер на продажу")
                                create_sell(from_order=orders_info[order]['order_id'], market=market)
                        else:

                            print(
                                "NOT FILLED")  # Если buy не был исполнен, и прошло достаточно времени для отмены ордера, отменяем

                            if not orders_info[order]['partially_filled'] and not orders_info[order]['order_cancelled']:
                                time_passed = int((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()) - int(time.mktime(datetime.strptime(orders_info[order]['order_created'],
                                                      "%Y-%m-%d %H:%M:%S").timetuple()))
                                if time_passed-10800 > ORDER_LIFE_TIME * 60:
                                    log('Пора отменять ордер %s' % order)
                                    cancel_res = exchange.cancel_order(order)
                                    if cancel_res['success']:
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
                                        log(market, "Ордер %s помечен отмененным в БД" % order)
                    else:  # Ордер на продажу
                        pass
            else:
                log(market, "Неисполненных ордеров в БД нет, пора ли создать новый?")
                # Проверяем MACD, если рынок в нужном состоянии, выставляем ордер на покупку
                if USE_MACD:
                    macd_advice = get_macd_advice(chart_data=get_ticks(market))
                    # Условия для покупки: BEAR и растущий прогноз MACD
                    if macd_advice['trand'] == 'BEAR' and macd_advice['growing']:
                        log(market, "Создаем ордер на покупку1")
                        create_buy(market=market)
                    else:
                        log(market, "Условия рынка не подходят для торговли", macd_advice)
                else:
                    log(market, "Создаем ордер на покупку2")
                    create_buy(market=market)
        time.sleep(1)
    except Exception as e:
        print(e)