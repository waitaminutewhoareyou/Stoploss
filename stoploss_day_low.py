import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import datetime as dt
from dateutil.relativedelta import relativedelta, FR, MO
from backtest import BackTest
from tqdm import tqdm
import seaborn as sns

tqdm.pandas()

ret_dir = './data/' + 'consolidated_table_wo_features_SL_low_open'
weight_dir = './data/' + 'ind_lev_pos_before_stop.csv'
output_dir = './result/'
PROGRAM_NAME = 'Early Sl priced at sl level low and open'


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
        self.weight = self.weight[(self.weight.index.year >= 1999)]

        start_year = 1999
        self.ret = pd.read_pickle(ret_dir).xs("ret", level='Features').replace(np.nan, 0)
        # self.ret.to_csv("ret.csv")
        self.count_dict = {'i': 0, 'f': 0, 'u': 0, 'c': 0, 'k': 0}
        self.ret.columns = self.ret.columns.astype(str)
        self.ret = self.ret[(self.ret.index.year >= start_year) & (self.ret.index <= self.weight.index.max())]

        self.sl_ret = self.ret.copy()

        self.low_ret = pd.read_pickle(ret_dir).xs("low ret", level='Features').replace(np.nan, 0)
        # self.low_ret.to_csv("low_ret.csv")
        self.low_ret.columns = self.low_ret.columns.astype(str)
        self.low_ret = self.low_ret[
            (self.low_ret.index.year >= start_year) & (self.low_ret.index <= self.weight.index.max())]

        self.open_ret = pd.read_pickle(ret_dir).xs("open ret", level='Features').replace(np.nan, 0)
        # self.open_ret.to_csv("open_ret.csv")
        self.open_ret.columns = self.open_ret.columns.astype(str)
        self.open_ret = self.open_ret[
            (self.open_ret.index.year >= start_year) & (self.open_ret.index <= self.weight.index.max())]

        # Record stats
        self.sl_counter = 0
        self.opportunity_cost = pd.Series(dtype=np.float64)

        self.stopped_assets = []

        self.asset = self.ret.columns

    def stoploss_detect(self, daily_low_data, num_shocks):
        today = daily_low_data.name

        if today.isoweekday() == 1:
            self.stopped_assets = []
            return

        current_monday = today - relativedelta(weekday=MO(-1))
        next_monday = today + relativedelta(weekday=MO(1))
        assert current_monday <= today <= next_monday
        assert (next_monday - current_monday).days == 7, (next_monday - current_monday).days

        # Current day return check
        look_back_end_date = current_monday
        look_back_start_date = look_back_end_date - dt.timedelta(days=252)
        look_back_data = self.ret[(self.ret.index >= look_back_start_date) & (self.ret.index <= look_back_end_date)]
        sl_day_ret = look_back_data.std() * (-num_shocks)
        # Open return check
        sl_open_day_indicator = self.open_ret.loc[today] <= sl_day_ret
        # Intraday  return check
        sl_day_indicator = daily_low_data <= sl_day_ret

        # Check skewness
        # sl_skew_indicator = self.ret[(self.ret.index >= look_back_end_date - dt.timedelta(days=252)) & (
        #         self.ret.index <= look_back_end_date)].skew(axis=0) >= num_shocks

        # Current week return check
        current_week_start_day = current_monday + dt.timedelta(days=1)
        current_week_ret = self.ret[(self.ret.index >= current_week_start_day) & (self.ret.index < today)]
        current_week_cum_ret = (1 + current_week_ret).prod()
        sl_cum_ret = look_back_data.std() * (-np.sqrt((today - current_week_start_day).days + 1) * num_shocks)
        # Open return check
        current_week_cum_open_ret = current_week_cum_ret * (1 + self.open_ret.loc[today]) - 1
        sl_open_cum_indicator = current_week_cum_open_ret <= sl_cum_ret
        # Intraday cumulative return check
        current_week_cum_intraday_ret = current_week_cum_ret * (1 + daily_low_data) - 1
        sl_cum_indicator = current_week_cum_intraday_ret <= sl_cum_ret

        # sl_asset = daily_low_data.index[sl_day_indicator | sl_cum_indicator ]
        sl_asset = daily_low_data.index[
            sl_day_indicator | sl_cum_indicator | sl_open_day_indicator | sl_open_cum_indicator]
        # Consolidate stoploss signals
        if not sl_asset.empty:
            sl_data = daily_low_data[sl_asset]
            sl_asset = sl_data[sl_data != 0].index

            sl_asset = [asset for asset in sl_asset if asset not in self.stopped_assets]
            self.stopped_assets.extend(sl_asset)
            self.stopped_assets = list(set(self.stopped_assets))
            sl_asset = pd.Index(sl_asset)

        if not sl_asset.empty:
            self.sl_counter += len(sl_asset)

            # set the stop-loss return
            sl_ret = pd.Series(index=sl_asset, dtype=np.float64)
            for asset in sl_asset:
                # if asset in self.asset[sl_skew_indicator]:
                #     self.count_dict['i'] += 1
                #    sl_ret[asset] = self.open_ret.loc[today, asset]
                if asset in self.asset[sl_open_day_indicator] or asset in self.asset[sl_open_cum_indicator]:
                    self.count_dict['f'] += 1
                    sl_ret[asset] = self.open_ret.loc[today, asset]
                elif (asset in self.asset[sl_day_indicator]) and (asset not in self.asset[sl_cum_indicator]):
                    self.count_dict['u'] += 1
                    sl_ret[asset] = sl_day_ret[asset]
                elif (asset not in self.asset[sl_day_indicator]) and (asset in self.asset[sl_cum_indicator]):
                    self.count_dict['c'] += 1
                    sl_ret[asset] = sl_cum_ret[asset]
                elif (asset in self.asset[sl_day_indicator]) and (asset in self.asset[sl_cum_indicator]):
                    self.count_dict['k'] += 1
                    sl_ret[asset] = max(sl_day_ret[asset], sl_cum_ret[asset])
                else:
                    raise Exception("You are fucked.")

            current_dat_missing_cost = self.weight.loc[today, sl_asset] * (self.ret.loc[today, sl_asset] - sl_ret)

            self.opportunity_cost = self.opportunity_cost.append(
                pd.Series(data=current_dat_missing_cost.sum(), index=[today]))

            missing_ret = self.weight.loc[today + dt.timedelta(days=1):next_monday + dt.timedelta(days=1),
                          sl_asset].multiply(
                self.ret.loc[today + dt.timedelta(days=1):next_monday + dt.timedelta(days=1),
                sl_asset]).sum(axis=1)

            self.opportunity_cost = self.opportunity_cost.append(missing_ret)

            self.weight.loc[today + dt.timedelta(days=1):next_monday + dt.timedelta(days=1), sl_asset] = 0

            # self.ret.loc[today, sl_asset] = sl_ret[sl_asset]
            self.sl_ret.loc[today, sl_asset] = sl_ret[sl_asset]

        return

    def stoploss_simulate(self, num_shocks=3):
        self.low_ret.progress_apply(lambda daily_low_ret: self.stoploss_detect(daily_low_ret, num_shocks), axis=1)
        return self.weight


def convert_return_to_plot(ret_ser):
    ret_ser = ret_ser[ret_ser != 0].dropna()
    cum_ret = (1 + ret_ser).cumprod()
    return cum_ret


# def visualize_opportunity_cost(df, path, title):
#     df = -df[df != 0].dropna()
#     df = df.groupby(level=0).sum()
#     plt.figure()
#     plt.hist(df.values, bins=100, density=True)
#     plt.title(
#         f'mean={100 * df.mean():.2f} %, # sl days = {len(df)}, max={100 * df.max():.2f},min={100 * df.min():.2f}, skew={df.skew():.2f}')
#     plt.savefig(path)

# monthly_series = df.resample('Y').agg(lambda x: x.sum())
# ax = monthly_series.plot.bar()
# ax.set_xticklabels(monthly_series.index.strftime('%Y-%m'))
# ax.set_ylim(-1, 1)
# ax.set_ylabel("Salvaged return ")
# ax.set_title(title)
# plt.savefig(path)


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

    OG = ret_ser
    for n in [1]:
        print(f'n={n}')
        sl = StopLossPrimer()
        sl.stoploss_simulate(n)
        print(sl.count_dict)
        print(f'# of sl {sl.sl_counter}')
        # visualize_opportunity_cost(sl.opportunity_cost,
        #                            output_dir + 'img/' + f"{PROGRAM_NAME} n={n} salvaed ret distribution .jpg",
        #                            f'# sl = {sl.sl_counter} n={n}')

        weight_w_sl = sl.weight
        # if n <= 1:
        #     weight_w_sl.to_csv(f"ind_lev_pos_{n}_shock_stop.csv")
        weight_w_sl.to_csv("Modified weight py.csv")
        weighted_ret = sl.sl_ret.multiply(weight_w_sl)

        ret_ser = weighted_ret.sum(axis=1)
        log_ret = convert_return_to_plot(ret_ser)
        plt.plot(log_ret)
        if n == 1:
            YG = ret_ser

        metrics = BackTest(ret_ser, '1999-1-1').compute_stat(plot=False).rename(f'{n}shocks')
        result.append(metrics)

    plt.legend(['Original', '0 shock', '0.5 shock', '1 shocks', '1.5 shocks', '2 shocks'])
    plt.savefig(output_dir + 'img/' + f"{PROGRAM_NAME}.jpg")
    plt.show()
    print(pd.concat(result, axis=1).round(2).to_csv(output_dir + 'data/' + f"{PROGRAM_NAME}.csv"))
    print("Correlation")
    print(pd.concat([OG, YG], axis=1).corr())
