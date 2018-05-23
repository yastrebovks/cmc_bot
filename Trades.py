from Additionals import log, get_positive_accounts
from Errors import err_noid
from time import time


# Покупка
def create_buy(main_properties, market):
    global USE_LOG
    USE_LOG = True
    exchange = main_properties["exchange"]
    pair = market.split('/')
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

    real_spend = current_balance if main_properties["CAN_SPEND"] > current_balance else main_properties["CAN_SPEND"]

    i = 0
    val = 0
    alpha = 0.1
    while (val < (real_spend / order_book[i][0]) * (1 + alpha)):
        val += order_book[i][1]
        i += 1

    current_rate = order_book[max(i - 1, 0)][0]
    # current_rate = float(exchange.fetch_order_book(market, 100)['asks'][1][0])
    # CAN_SPEND = balance_refresh()
    can_buy = real_spend / current_rate

    log(market, """
        Current Rate - %0.8f
        By sum %0.8f %s can buy %0.8f %s
        Creating Order
        """ % (current_rate, real_spend, pair[1], can_buy, pair[0])
        )

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
            tmp_order = err_noid(main_properties, current_rate, market)
            if(tmp_order):
                order_res = tmp_order
            else:
                order_res['amount'] = current_position
                order_res['price'] = (current_balance - get_positive_accounts(exchange.fetch_balance()[pair[1]])[
                    'free']) / current_position
                order_res['id'] = "NoID"

    print(order_res)
    if order_res:
        main_properties["cursor"].execute(
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
        main_properties["conn"].commit()
        log(order_res, " - Order Created!")
    else:
        log(market, """
            Error with creating order: %s
        """ % order_res['message'])
    USE_LOG = False


# Продажа
def create_sell(main_properties, from_order, market, trand=""):
    global USE_LOG
    USE_LOG = True
    exchange = main_properties["exchange"]
    pair = market.split('/')
    buy_order_q = """
        SELECT order_spent, order_amount FROM orders WHERE order_id='%s'
    """ % from_order

    if (from_order['order_id'] != "NoID" and from_order['order_id'] != "Zero"):
        try:
            from_order = from_order['order_id']
            order_amount = exchange.fetch_order(from_order, symbol=market)['amount']
            current_balance = get_positive_accounts(exchange.fetch_balance()[pair[0]])['free']
            order_spent = exchange.fetch_order(from_order, symbol=market)['price']
        except:
            log("Error with Sell order 1")
            return
    else:
        order_amount = from_order['order_amount']
        order_spent = from_order['order_price']
        try:
            current_balance = get_positive_accounts(exchange.fetch_balance()[pair[0]])['free']
        except:
            log("Error with Sell order 2")

    if order_amount > current_balance:
        order_amount = current_balance



    new_rate = (order_spent + order_spent * main_properties["MARKUP"])
    new_rate_fee = new_rate + (new_rate * main_properties["STOCK_FEE"]) / (1 - main_properties["STOCK_FEE"])
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
            main_properties["STOCK_FEE"], (new_rate_fee * order_amount - new_rate_fee * order_amount * main_properties["STOCK_FEE"]), pair[1],
            (new_rate_fee * order_amount - new_rate_fee * order_amount * main_properties["STOCK_FEE"]) - order_spent*order_amount, pair[1],
            # MAIN MARKUP!
            current_rate,
            choosen_rate,
        )
    )

    order_res = exchange.create_order(market, 'limit', 'sell', order_amount, choosen_rate)
    if not ('price' in order_res) or not ('amount' in order_res):
        order_res = exchange.fetch_order(order_res['id'], symbol=market)

    print(from_order)
    if order_res:
        main_properties["cursor"].execute(
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
                'from_order_id': from_order['order_id']
            })
        main_properties["conn"].commit()
        log(trand, " - Reason for order.")
        log(order_res, " - Sell order created!")
    USE_LOG = False

# Принудительная продажа
def create_sell_executive(main_properties, from_order, market, trand=""):
    global USE_LOG
    USE_LOG = True
    exchange = main_properties["exchange"]
    pair = market.split('/')

    buy_order_q = """
        SELECT order_spent, order_amount FROM orders WHERE order_id='%s'
    """ % from_order

    if (from_order['order_id'] != "NoID" and from_order['order_id'] != "Zero"):
        try:
            from_order = from_order['order_id']
            order_amount = exchange.fetch_order(from_order, symbol=market)['amount']
            current_balance = get_positive_accounts(exchange.fetch_balance()[pair[0]])['free']
            order_spent = exchange.fetch_order(from_order, symbol=market)['price']
        except:
            log("Error with Sell order 1")
            return
    else:
        order_amount = from_order['order_amount']
        order_spent = from_order['order_price']
        try:
            current_balance = get_positive_accounts(exchange.fetch_balance()[pair[0]])['free']
        except:
            log("Error with Sell order 2")

    if order_amount > current_balance:
        order_amount = current_balance

    new_rate = (order_spent + order_spent * main_properties["MARKUP"])
    new_rate_fee = new_rate + (new_rate * main_properties["STOCK_FEE"]) / (1 - main_properties["STOCK_FEE"])
    # ????? ???? ??????? ????
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
            main_properties["STOCK_FEE"], (new_rate_fee * order_amount - new_rate_fee * order_amount * main_properties["STOCK_FEE"]), pair[1],
            (new_rate_fee * order_amount - new_rate_fee * order_amount * main_properties["STOCK_FEE"]) - order_spent*order_amount, pair[1],
            # MAIN MARKUP!
            current_rate,
            choosen_rate,
        )
        )
    # choosen_rate *= 10
    order_res = exchange.create_order(market, 'limit', 'sell', order_amount, choosen_rate)
    if not ('price' in order_res) or not ('amount' in order_res):
        order_res = exchange.fetch_order(order_res['id'], symbol=market)
    # ????????? ?? ?? ?????????? ??????
    if order_res:
        main_properties["cursor"].execute(
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
                'from_order_id': from_order['order_id']
            })
        main_properties["conn"].commit()
        log(trand, " - Reason for order.")
        log(order_res, " - Sell order created!")
    USE_LOG = False

# Нулевой ордер
def create_zero(main_properties):
    main_properties["cursor"].execute(
        """
            INSERT INTO orders(
                order_id,
                order_type,
                order_pair,
                order_created,
                order_price,
                order_amount,
                order_spent,
                order_filled
            ) VALUES (
              :order_id,
              'buy',
              :order_pair,
              datetime(),
              :order_price,
              :order_amount,
              :order_spent,
              datetime()
            )
        """, {
            'order_id': "Zero",
            'order_pair': main_properties["MARKETS"][0],
            'order_price': 0,
            'order_amount': main_properties["ZeroCount"],
            'order_spent': 0
        })

    main_properties["conn"].commit()
    log("Zero Order Created!")

def close_positions(main_properties):
    for market in main_properties["MARKETS"]:
        pair = market.split('/')
        balance = 0
        try:
            balance = get_positive_accounts(main_properties["exchange"].fetch_balance()[pair[0]])['free']
        except:
            pass

        if(balance):
            main_properties["cursor"].execute(
                """
                    INSERT INTO orders(
                        order_id,
                        order_type,
                        order_pair,
                        order_created,
                        order_price,
                        order_amount,
                        order_spent,
                        order_filled
                    ) VALUES (
                      :order_id,
                      'buy',
                      :order_pair,
                      datetime(),
                      :order_price,
                      :order_amount,
                      :order_spent,
                      datetime()
                    )
                """, {
                    'order_id': "Zero",
                    'order_pair': market,
                    'order_price': 0,
                    'order_amount': balance,
                    'order_spent': 0
                })

            main_properties["conn"].commit()
            log("Zero Order Created!")

    main_properties["StopFlag"] = True