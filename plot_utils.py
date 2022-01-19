import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

df = pd.read_csv("opportunity cost.csv", index_col='Date', na_values=[0],
                 parse_dates=True).dropna(how='all').sum(axis=1)
df = -df
monthly_series = df.resample('Y').agg(lambda x: (x + 1).prod() - 1)
ax = monthly_series.plot.bar()
ax.set_xticklabels(monthly_series.index.strftime('%Y'))
plt.show()
