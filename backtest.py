import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

pd.set_option('display.max_columns', None)


class BackTest:
    def __init__(self, data, start_time=None, end_time=None):

        data = data.squeeze()
        data = data[start_time:end_time]
        self.data = data.dropna(
        )
        self.time_freq = pd.infer_freq(data.index)
        if self.time_freq == 'B' or self.time_freq == 'D' or self.time_freq is None:
            self.T = 250
            self.monthly_return = data.resample('M').agg(lambda x: (x + 1).prod() - 1)
            self.time_freq = 'D'  # reset business day frequency to daily frequency

        elif self.time_freq == 'M':
            self.T = 12
            self.monthly_return = data

        # else:
        #     raise Exception("Can't detect time frequency")

        self.AUM = (1 + self.monthly_return).cumprod()
        self.dd = 1 - self.AUM / np.maximum.accumulate(self.AUM)

    def total_return(self):
        return np.prod(1 + self.data.values) - 1

    def annualized_return(self):
        return (1 + self.total_return()) ** (self.T / len(self.data)) - 1

    def annualized_volatility(self):
        return np.std(self.data.values) * np.sqrt(self.T)

    def information_ratio(self):
        ret = self.annualized_return()
        vol = self.annualized_volatility()
        return ret / vol

    def compute_drawdown_duration_peaks(self, dd: pd.Series):
        iloc = np.unique(np.r_[(dd == 0).values.nonzero()[0], len(dd) - 1])
        iloc = pd.Series(iloc, index=dd.index[iloc])
        df = iloc.to_frame('iloc').assign(prev=iloc.shift())
        df = df[df['iloc'] > df['prev'] + 1].astype(int)


        # If no drawdown since no trade, avoid below for pandas sake and return nan series
        if not len(df):
            return (dd.replace(0, np.nan),) * 2

        df['duration'] = df['iloc'].map(dd.index.__getitem__) - df['prev'].map(dd.index.__getitem__)
        df['peak_dd'] = df.apply(lambda row: dd.iloc[row['prev']:row['iloc'] + 1].max(), axis=1)
        df = df.reindex(dd.index)
        return df['duration'], df['peak_dd']

    def under_water_time(self):
        df = self.data.to_frame()
        df['Return'] = df.values
        df['cummax'] = df['Return'].cummax()

        df['underwater'] = pd.to_timedelta((df['Return'] < df['cummax']).astype(int), unit=self.time_freq)
        total_time_under_water = df['underwater'].sum()

        time_under_water, max_time_under_water = 0, 0

        # loop through an Boolean series
        for val in (df['Return'] < df['cummax']).astype(int).values:
            for val in (df['Return'] < df['cummax']).astype(int).values:
                if val:
                    time_under_water += 1
                else:
                    time_under_water = 0
            max_time_under_water = max(time_under_water, max_time_under_water)

        # for display purpose
        max_time_under_water = pd.to_timedelta(max_time_under_water, unit=self.time_freq)

        return max_time_under_water, total_time_under_water

    def max_drawdown_one_month(self):
        monthly_negative_return = self.monthly_return[self.monthly_return < 0]
        return monthly_negative_return.min()

    def compute_stat(self, plot=True):
        equity = self.AUM.values
        index = self.data.index
        dd = self.dd
        dd = 1 - equity / np.maximum.accumulate(self.AUM)
        # dd_dur, dd_peaks = self.compute_drawdown_duration_peaks(pd.Series(dd, index=index))
        dd_dur, dd_peaks = self.compute_drawdown_duration_peaks(dd)

        s = pd.Series(dtype=object)
        s.loc['Start'] = index[0]
        s.loc['End'] = index[-1]
        s.loc['Duration'] = s.End - s.Start

        s.loc['Return (Ann.) [%]'] = self.annualized_return() * 100
        s.loc['Volatility (Ann.) [%]'] = self.annualized_volatility() * 100
        s.loc['Information Ratio'] = self.information_ratio()

        s.loc['Final AUM [unitless]'] = equity[-1]
        s.loc['AUM Peak [$]'] = equity.max()
        s.loc['Final Return [%]'] = (equity[-1] - equity[0]) / equity[0] * 100
        max_dd = -np.nan_to_num(dd.max())
        s.loc['Max. Drawdown [%]'] = max_dd * 100
        s.loc['Max. Drawdown Duration'] = dd_dur.max()
        s.loc['Avg. Drawdown Duration'] = dd_dur.mean()

        max_time_under_water, total_time_under_water = self.under_water_time()
        s.loc['Max. Underwater Duration'] = max_time_under_water
        s.loc['Total Underwater Duration'] = total_time_under_water
        if plot:
            self.AUM.plot()
            plt.grid(True)
            plt.show()
        return s


class Gross2Net:
    def __init__(self, data, fixed_fee=0.015, cost=0.005, perf_fee=0.2):

        self.data = data.dropna()
        self.fixed_fee = fixed_fee
        self.perf_fee = perf_fee
        self.cost = cost
        self.time_freq = pd.infer_freq(data.index)

        if self.time_freq == 'B' or self.time_freq == 'D':
            self.T = 250
            self.monthly_return = data.resample('M').agg(lambda x: (x + 1).prod() - 1)
            self.time_freq = 'D'  # reset business day frequency to daily frequency

        elif self.time_freq == 'M':
            self.T = 12
            self.monthly_return = data

        else:
            raise Exception("Can't detect time frequency")

        self.df = pd.DataFrame(self.monthly_return.values,
                               index=self.monthly_return.index,
                               columns=['Raw Ret'])

    def main(self):
        # split year and month
        self.df['Year'] = self.monthly_return.index.year
        self.df['Month'] = self.monthly_return.index.month

        # total after fixed fee ret
        self.df['Total after fixed fee ret'] = 1 + self.df['Raw Ret'] - self.fixed_fee / 12

        # YTD after fee ret
        val = np.zeros(len(self.df))

        val[0] = self.df['Total after fixed fee ret'].iloc[0]
        for ix in range(1, len(val)):
            if self.df['Month'].iloc[ix] == 1:
                val[ix] = self.df['Total after fixed fee ret'].iloc[ix]
            else:
                val[ix] = self.df['Total after fixed fee ret'].iloc[ix] * val[ix - 1]
        self.df['YTD after fee ret'] = val

        # Year end(0) + previous year end NAV(1) + Val after fee(2)   + high water mark(3) +
        # accrued perf fee(4) + NAV(5)
        min_year = self.df['Year'].min()
        val = np.zeros((len(self.df), 6))

        for ix in range(len(val)):

            if self.df['Year'].iloc[ix] == min_year:
                val[ix, 1] = 1  # previous year end nav
                val[ix, 2] = self.df['YTD after fee ret'].iloc[ix]  # Value after fee
                val[ix, 3] = 1  # high water mark
            else:

                val[ix, 1] = max(val[max(ix - 12, 0):ix, 0])  # previous year end nav
                val[ix, 2] = self.df['YTD after fee ret'].iloc[ix] * val[ix, 1]  # Value after fee
                val[ix, 3] = max(val[:ix, 0])  # high water mark

            val[ix, 4] = max(0, val[ix, 2] - val[ix, 3]) * self.perf_fee  # accrued perf fee
            val[ix, 5] = val[ix, 2] - val[ix, 4]  # NAV
            val[ix, 0] = int(self.df['Month'].iloc[ix] == 12) * val[ix, 5]  # Year end

        self.df[['Year end', 'Previous year end NAV', 'Value after fee', 'High water mark',
                 'Accrued performance fee', 'NAV']] = val
        self.df['Net ret'] = self.df['NAV'] - 1
        return self.df.head(30)


if __name__ == '__main__':
    data = pd.read_excel("daily return.xlsx", index_col=0, parse_dates=True, na_values=[0, '0'])
    data = data.asfreq('B')
    test = BackTest(data, '2009-12-30', '2022-01-01')
    print(test.compute_stat())

    # data = pd.read_excel("Monthly Return.xlsx", index_col=0, parse_dates=True)
    # data = data.asfreq('M')
    # test = Gross2Net(data)
    # print(test.main())
