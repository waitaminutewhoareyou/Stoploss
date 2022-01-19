import pandas as pd

from stoploss_day_low import StopLossPrimer
from backtest import BackTest


class ActiveTrader(StopLossPrimer):
    def __init__(self):
        super().__init__()
        num_positions_per_day = (1 - self.weight.astype(bool)).sum(axis=1)
        self.weight_equal_same_pos = -(1 - self.weight.astype(bool)).div(num_positions_per_day, axis=0)
        self.original_ret = self.ret.multiply(self.weight).sum(axis=1)

    def trade(self):
        self.stoploss_simulate(-1
                               )
        ret_ser = self.ret.multiply(self.weight_equal_same_pos).sum(axis=1)
        metrics = BackTest(ret_ser).compute_stat(plot=False)
        # print(metrics)
        corr = pd.concat([self.original_ret, ret_ser], axis=1).corr()
        # print("Correlation:{corr}", corr)

        return ret_ser


if __name__ == '__main__':
    trader = ActiveTrader()
    ret_short = trader.trade()
    sl = StopLossPrimer()
    sl.stoploss_simulate(1)
    weight_w_sl = sl.weight
    weighted_ret = sl.ret.multiply(weight_w_sl)
    ret_long = weighted_ret.sum(axis=1)
    metrics = BackTest(ret_long + ret_short).compute_stat(plot=False)
    print(metrics)
