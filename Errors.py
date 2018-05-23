from time import time

## Обработка NoID
def err_noid(main_properties, current_rate, market):
    if(main_properties['MarketPlace'] == 'bittrex'):
        old_order = main_properties["exchange"].fetch_orders(symbol = market, since = (time() - 300), limit = 1)
        length = len(old_order)
        if(length == 0):
            return 0
        else:
            return old_order[0]
    elif(main_properties['MarketPlace'] == 'hitbtc2'):
        old_order = main_properties["exchange"].fetch_open_orders(symbol = market, since = (time() - 300), limit = 1)
        if(old_order):
            return old_order
        else:
            old_order = main_properties["exchange"].fetch_closed_orders(symbol = market, since = (time() - 300), limit = 1)
            if(old_order):
                return old_order
            else:
                return 0
