import time
from pprint import pprint
import sys
sys.path.append("/home/null/Body")
from Additionals import profit, init_exchange, log
from Trades import create_sell_executive, create_buy, create_sell, create_zero, close_positions, stop_orders
from Advicer_extended import get_advice
from datetime import datetime

def Runing(main_properties):
    print("!")
    conn = main_properties["conn"]
    cursor = main_properties["cursor"]
    Working = True

    while Working:
        try:
            for market in main_properties["MARKETS"]:
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
                orders_info = {}
                try:
                    for row in cursor.execute(orders_q):
                        orders_info[str(row[0])] = {'order_id': row[0], 'order_type': row[1], 'order_price': row[2],
                                                'order_amount': row[3], 'order_filled': row[4], 'order_created': row[5],
                                                'partially_filled': False, 'order_cancelled': False
                                                }
                except:
                    print("DB is empty")
                if orders_info:
                    for order in orders_info:
                        if not orders_info[order]['order_filled'] and (orders_info[order]["order_id"]).find("Zero") == -1:
                            print("Hello there!")
                            order_info = main_properties["exchange"].fetch_order(orders_info[order]['order_id'],
                                                                                 symbol=market)
                            if order_info['status'] == 'closed':
                                if (order_info['fee'] == None) or not ('fee' in order_info):
                                    order_info['fee'] = {}
                                    order_info['fee']['cost'] = main_properties["STOCK_FEE"]
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
                                        order_info['fee']['cost'] = main_properties["STOCK_FEE"]
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
                                elif(main_properties['CloseOrders']):
                                    try:
                                        main_properties['exchange'].close_order(orders_info[order]['order_id'])
                                    except:
                                        print("Can't Cancel order for ", market)
                                else:
                                    if (order_info['fee'] == None) or not ('fee' in order_info):
                                        order_info['fee'] = {}
                                        order_info['fee']['cost'] = main_properties["STOCK_FEE"]
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
                                if order_info['remaining'] != order_info['amount']:
                                    orders_info[order]['partially_filled'] = True
                    for order in orders_info:
                        if orders_info[order]['order_type'] == 'buy':
                            if orders_info[order]['order_filled']:
                                if main_properties["USE_MACD"]:
                                    advice = get_advice(main_properties, market, '5m', 'sell', orders_info[order]['order_amount'])
                                    if (advice == 'SELL'):
                                        create_sell(main_properties, from_order=orders_info[order], market=market,
                                                trand = advice)
                                    elif(profit(main_properties, from_order=orders_info[order], market=market) <= -0.02):
                                        create_sell_executive(main_properties, from_order=orders_info[order],
                                            market=market,
                                            trand="Executive")
                                    elif(profit(main_properties, from_order=orders_info[order], market=market) >= 0.035) and \
                                            not (advice == 'POH'):
                                        create_sell(main_properties, from_order=orders_info[order], market=market,
                                                    trand = advice)
                                else:
                                    log(market, "Start to create Sell order")
                                    create_sell(main_properties, from_order=orders_info[order], market=market)
                            else:

                                print("NOT FILLED")
                                # not orders_info[order]['partially_filled'] and
                                time_passed = int((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()) - int(
                                    time.mktime(datetime.strptime(orders_info[order]['order_created'],
                                                                  "%Y-%m-%d %H:%M:%S").timetuple()))
                                if not orders_info[order]['partially_filled'] and not orders_info[order][
                                    'order_cancelled']:
                                    if time_passed > main_properties["ORDER_LIFE_TIME"] * 60:
                                        cancel_res = main_properties["exchange"].cancel_order(order, symbol=market)
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
                                        cancel_res = main_properties["exchange"].cancel_order(order, symbol=market)
                        else:
                            print("!")
                            if not orders_info[order]['partially_filled'] and not orders_info[order]['order_cancelled']:
                                time_passed = int((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()) - int(
                                    time.mktime(datetime.strptime(orders_info[order]['order_created'],
                                                                  "%Y-%m-%d %H:%M:%S").timetuple()))
                                if time_passed > 600:
                                    cancel_res = main_properties["exchange"].cancel_order(order, symbol=market)
                                    create_sell_executive(main_properties, from_order=orders_info[order], market=market,
                                                          trand="Executive")
                else:
                    if(not main_properties["StopFlag"]):
                        if main_properties["USE_MACD"]:
                            advice = get_advice(main_properties, market, '5m', 'buy')
                            if advice == 'BUY':
                                #log(market,"MAXV: ", macd_advice['maxv'])
                                if (market not in main_properties['maxv']) or \
                                        (abs(main_properties['curr_maxv']) >= main_properties['maxv'][market]):
                                    create_buy(main_properties, market=market)
                        else:
                            create_buy(main_properties, market=market)
                    else:
                        main_properties["MARKETS"].remove(market)
            time.sleep(5)
            if(not main_properties["MARKETS"]):
                Working = False
        except Exception as e:
            print("Exit bot")
            print(e)

    log("The bot's work is end.")
    return 0

def start_robot():
    main_properties = init_exchange()

    if(main_properties["ClosePositions"]):
        conn = main_properties["conn"]
        cursor = main_properties["cursor"]
        cursor.execute("DROP TABLE orders")
        close_positions(main_properties)
        Runing(main_properties)
    elif(main_properties["ZeroFlag"]):
        create_zero(main_properties)
        conn = main_properties["conn"]
        cursor = main_properties["cursor"]
        Runing(main_properties)
    elif(main_properties["StopOrders"]):
        main_properties["StopFlag"] = True
        stop_orders(main_properties)
    else:
        conn = main_properties["conn"]
        cursor = main_properties["cursor"]
        Runing(main_properties)

start_robot()