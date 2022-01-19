import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import datetime as dt
from dateutil.relativedelta import relativedelta, FR, MO
from backtest import BackTest
from tqdm import tqdm

tqdm.pandas()

ret_dir = './data/' + 'consolidated_table_wo_features_SL'
weight_dir = './data/' + 'ind_lev_pos_before_stop.csv'
output_dir = './result/'


def get_last_friday(date: dt.date) -> dt.date:
    while date.isoweekday() != 5:
        date -= dt.timedelta(days=1)
    return date


def get_current_monday(date):
    while date.isoweekday() != 1:
        date -= dt.timedelta(days=1)
    return date


def get_next_monday(date):
    while date.isoweekday() != 1:
        date += dt.timedelta(days=1)
    return date


class StopLossPrimer:
    def __init__(self):
        self.weight = pd.read_csv(weight_dir,
                                  parse_dates={'Date': ['Year', 'Month', 'Day']},
                                  infer_datetime_format=True,
                                  keep_date_col=False,
                                  na_values=[-999, '-999'],
                                  index_col='Date')

        self.ret = pd.read_pickle(ret_dir).xs("ret", level='Features').replace(np.nan, 0)
        self.ret.columns = self.ret.columns.astype(str)

        self.ret = self.ret[(self.ret.index.year >= 1999)]
        # assert set(self.weight.index) <= set(self.ret.index)
        # self.weighted_ret = self.ret.multiply(self.weight)
        #
        # self.ret_ser = self.ret.multiply(self.weight).sum(axis=1)
        #
        # self.ret_ser = self.ret_ser[self.ret_ser != 0].dropna()
        #
        # cum_ret = (1 + self.ret_ser).cumprod()
        # np.log(cum_ret).plot()
        # plt.show()

    def stoploss_detect(self, daily_data, num_shocks=3):
        today = daily_data.name

        if today.isoweekday() == 1:
            return

        # last_friday = today - relativedelta(weekday=FR(-1))
        current_monday = today - relativedelta(weekday=MO(-1))
        next_monday = today + relativedelta(weekday=MO(1))

        # if daily_data.name.year < 1999:
        #     pass

        # Look back periods ends at current Monday
        look_back_end_date = current_monday
        look_back_start_date = look_back_end_date - dt.timedelta(days=252)
        look_back_data = self.ret[(self.ret.index >= look_back_start_date) & (self.ret.index <= look_back_end_date)]
        sl_indicator = np.abs(daily_data / look_back_data.std()) >= num_shocks

        # Cumulative return starts from Tuesday
        current_week_start_day = current_monday + dt.timedelta(days=1)
        current_week_ret = self.ret[(self.ret.index >= current_week_start_day) & (self.ret.index <= today)]
        current_week_cum_ret = (1 + current_week_ret).prod() - 1

        sl_cum_indicator = np.abs(current_week_cum_ret / look_back_data.std()) >= np.sqrt(
            (today - current_week_start_day).days + 1) * num_shocks

        sl_asset = daily_data.index[sl_indicator | sl_cum_indicator]

        self.weight.loc[today + dt.timedelta(days=1):next_monday + dt.timedelta(days=1), sl_asset] = 0

        return

    def stoploss_simulate(self, num_shocks=3):
        self.ret.progress_apply(lambda daily_ret: self.stoploss_detect(daily_ret, num_shocks), axis=1)
        return self.weight


def convert_return_to_plot(ret_ser):
    ret_ser = ret_ser[ret_ser != 0].dropna()
    cum_ret = (1 + ret_ser).cumprod()
    return np.log(cum_ret)


if __name__ == '__main__':

    result = []
    # fig, ax = plt.subplots(dpi=500)

    sl = StopLossPrimer()
    weight_wo_sl = sl.weight
    weighted_ret = sl.ret.multiply(weight_wo_sl)

    ret_ser = weighted_ret.sum(axis=1)
    log_ret = convert_return_to_plot(ret_ser)
    plt.plot(log_ret)
    metrics = BackTest(ret_ser, '1999-1-1').compute_stat(plot=False).rename('Original')
    result.append(metrics)

    for n in range(6):
        print(f'n={n}')
        sl = StopLossPrimer()
        sl.stoploss_simulate(n)
        weight_w_sl = sl.weight
        weighted_ret = sl.ret.multiply(weight_w_sl)
        ret_ser = weighted_ret.sum(axis=1)
        log_ret = convert_return_to_plot(ret_ser)
        plt.plot(log_ret)
        metrics = BackTest(ret_ser, '1999-1-1').compute_stat(plot=False).rename(f'{n}shocks')
        result.append(metrics)

    plt.legend(['Original', '0 shock', '1 shock', '2 shocks', '3 shocks', '4 shocks', '5 shocks'])
    plt.savefig(output_dir + 'img/' + "tp and sl result.jpg")
    plt.show()
    print(pd.concat(result, axis=1).round(2).to_csv(output_dir + 'data/' + "Takeprofit and Stoploss.csv"))
