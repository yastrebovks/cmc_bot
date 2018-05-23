import talib
import numpy
from Additionals import get_ticks

# ?????????? ???????? ?? ?????? MACD
def get_macd_advice(main_properties, market, timeframe):
    chart_data = get_ticks(main_properties, market, timeframe)

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
