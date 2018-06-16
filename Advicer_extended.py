import talib
import numpy
from Additionals import get_ticks, log

def get_macd_advice(market, timeframe, main_properties, fastperiod = 12, slowperiod = 26, signalperiod = 9):
    chart_data = get_ticks(main_properties, market, timeframe)
    macd, macdsignal, macdhist = talib.MACD(numpy.asarray([chart_data[item]['close'] for item in sorted(chart_data)]),
                                            fastperiod, slowperiod, signalperiod)

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
        if ((macd[offset] > macdsignal[offset] and perc * 100 > main_properties["BULL_PERC"])  # ?????????? ?????
                or (
                        macd[offset] < macdsignal[offset] and perc * 100 < (100 - main_properties["BEAR_PERC"])
                )
        ):
            activity_time = True
            growing = True
        if offset in idx and not numpy.isnan(elem):
            # ????? ?????????
            max_v = curr_v = 0  # ???????? ??? ?????? ????? ???????
    return ({'trand': trand, 'growing': growing, 'maxv': max_v})


# ????????? Parabolic SAR
def get_parSAR_advice(chart_data, client_acceleration = 0.02, client_maximum = 0.2):                # Обычно принято брать acceleration = 0.02, maximum = 0.2
    parabolicsar = talib.SAR(numpy.asarray([chart_data[item]['high'] for item in sorted(chart_data)]), \
                                           numpy.asarray([chart_data[item]['low'] for item in sorted(chart_data)]), \
                                                         acceleration=client_acceleration, maximum=client_maximum)

    close = numpy.asarray([chart_data[item]['close'] for item in sorted(chart_data)])
    open = numpy.asarray([chart_data[item]['open'] for item in sorted(chart_data)])

    if parabolicsar[-2] >= max(open[-2], close[-2]):
        print(str(parabolicsar[-2]) + " " + str(open[-2]) + " " + str(close[-2]))
        trand = 'BEAR'
    elif parabolicsar[-2] <= min(open[-2], close[-2]):
        print(str(parabolicsar[-2]) + " " + str(open[-2]) + " " + str(close[-2]))
        trand = 'BULL'

    trandchange = False
    growing = False
    for offset, elem in enumerate(parabolicsar):
        trandchange = False
        growing = False
        if (parabolicsar[offset-1] >= max(open[offset-1], close[offset-1]) and \
            parabolicsar[offset-2] < min(open[offset-2],close[offset-2])) or\
                (parabolicsar[offset-1] <= min(open[offset-1], close[offset-1]) and \
            parabolicsar[offset-2] > max(open[offset-2], close[offset-2]))    :
            trandchange = True                                                                                 # Принимает True, когда парСАР поменял положение относительно цен
        if parabolicsar[offset-1] < min(open[offset-1], close[offset-1]):
            growing = True                                                                                     # Тренд вверх, пока парСАР находится ниже цен
    #print(str(trandchange) + str(trand) + str(growing) + str(offset) + str(open[offset-1]))
    parSARjump = numpy.diff(parabolicsar) * 100000                                                             # Наибольшие и наименьшие скачки соответствуют моментам, когда парСАР поменяло положение относительно цен
    return ({'trand': trand, 'growing': growing, 'trandchange': trandchange, 'parSAR': parabolicsar, 'parSARjump': parSARjump})


 # ??????????????      Сглаженная скользящая средняя
def smoothedmovingaverage(values, period):
    smmas = []
    ma = talib.SMA(values, timeperiod = period)
    i= 0
    while i < len(values):
        if i < period:
            smmas.append(ma[i])
        else:
            temp=(smmas[i-1]*(period-1)+values[i])/period
            smmas.append(temp)
        i = i+1
    return smmas

def sign(value):
    if value > 0:
        return 1
    elif value < 0:
        return -1
    else:
        return 0

  # ?????????????     Alligator
def get_alligator_advice(chart_data, long_period = 13, long_shift = 8, mid_period = 8, mid_shift = 5, short_period = 5,\
                         short_shift = 3):
    high = numpy.asarray([chart_data[item]['high'] for item in sorted(chart_data)])
    low = numpy.asarray([chart_data[item]['low'] for item in sorted(chart_data)])

    median_price = talib.MEDPRICE(high, low)

    jaws  = smoothedmovingaverage(median_price, long_period)    # Обычно long_period = 13
    teeth = smoothedmovingaverage(median_price, mid_period)     #        mid_period  = 8
    lips  = smoothedmovingaverage(median_price, short_period)   #        short_period= 5

    jaws  = [jaws[0]] * long_shift  + jaws                      #        long_shift  = 8
    teeth = [teeth[0]]* mid_shift   + teeth                     #        mid_shift   = 5
    lips  = [lips[0]] * short_shift + lips                      #        shirt_shift = 3

    growing = False
    for offset, elem in enumerate(high):
        strong_trand = False

        if jaws[offset-1] > teeth[offset-1] > lips[offset-1]:
            trand = 'BEAR'
        elif lips[offset-1] > teeth[offset-1] > jaws[offset-1]:
            trand = 'BULL'
        else:
            trand = 'Alligator is sleeping'                     # Когда не соблюден порядок линии или пересекаются

        if sign(jaws[offset-1] - teeth[offset-1]) != sign(teeth[offset-1] - lips[offset-1]) or (sign(jaws[offset-1] - teeth[offset-1]) == 0 and \
                                                                                        sign(teeth[offset-1] - lips[
                                                                                            offset-1]) == 0):
            growing = False                                     # Линии в "плохом" порядке или просто пересекаются => нет тренда
        else:
            if sign(jaws[offset-1] - teeth[offset-1]) > 0:
                growing = False                                 # Линии в порядке: Челюсти > Зубы > Губы => Тренд вниз
                if jaws[offset-1] - teeth[offset-1] >= jaws[offset-2] - teeth[offset-2] or \
                        teeth[offset-1] - lips[offset-1] >= teeth[offset-2] - lips[offset-2]:
                    strong_trand =True
            elif sign(jaws[offset-1] - teeth[offset-1]) < 0:
                growing = True                                  #  Тренд вверх, когда порядок линии (сверху вниз): Губы > Зубы > Челюсти
                if teeth[offset-1] - jaws[offset-1] > teeth[offset-2] - jaws[offset-2] or \
                        lips[offset-1] - teeth[offset-1] > lips[offset-2] - teeth[offset-2]:    # Если линии расходятся друг от друга, то
                    strong_trand =True                                                       # тренд должен быть долгим
    #print(str(strong_trand) + str(trand) + str(growing) + str(offset-1) + " " + str(jaws[-2]) + " " + str(teeth[-2]) + " " + str(lips[-2]))
    return ({'trand': trand, 'growing': growing, 'strong_trand': strong_trand, 'jaws': jaws, 'teeth': teeth, 'lips': lips})

def get_advice(main_properties, market, timeframe, position, order_amount = ""):
    chart_data = get_ticks(main_properties, market, timeframe)

    macd = get_macd_advice(market, timeframe, main_properties)
    alligator = get_alligator_advice(chart_data)
    parSAR = get_parSAR_advice(chart_data)

    close = numpy.asarray([chart_data[item]['close'] for item in sorted(chart_data)])
    print(1)
    middle = talib.SMA(close, timeperiod = 20)
    print(2)


    #log('alligator: ', alligator)
    #log('parSAR: ', parSAR)

    #log('macd: ', macd)

    if(position == 'buy'):
        order_book = main_properties['exchange'].fetch_order_book(market, 100)['asks']

        i = 0
        val = 0
        alpha = 0.1
        while (val < (main_properties['CAN_SPEND'] / order_book[i][0]) * (1 + alpha)):
            val += order_book[i][1]
            i += 1

        current_rate = order_book[max(i - 1, 0)][0]
        print("Current: ", current_rate, "Middle: ", middle[-1])
        if(current_rate >= middle[-1]):
            return

        if(parSAR['trand'] == 'BULL' and
                ((alligator['trand'] == 'BULL' and alligator['strong_trand'])
                 or (not alligator['trand'] == 'BEAR'))
                and macd['growing']):
            main_properties['curr_maxv'] = macd['maxv']
            return 'BUY'
    else:
        order_book = main_properties['exchange'].fetch_order_book(market, 100)['bids']

        i = 0
        val = 0
        alpha = 0.2
        while (val < order_amount * (1 + alpha)):
            val += order_book[i][1]
            i += 1

        current_rate = order_book[max(i - 1, 0)][0]
        print("Current: ", current_rate, "Middle: ", middle[-1])
        if (current_rate <= middle[-1]):
            return

        if(parSAR['trand'] == 'BEAR' and
                ((alligator['trand'] == 'BEAR' and alligator['strong_trand']) or
                 (not alligator['trand'] == 'BEAR' and not alligator['trand'] == 'BULL'))
                and not macd['growing']):
            return 'SELL'
        elif(not alligator['trand'] == 'BEAR' and not alligator['trand'] == 'BULL' and not macd['growing']):
            return 'POH'
