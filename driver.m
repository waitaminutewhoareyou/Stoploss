low_ret = readtable('low_ret.csv');
ret = readtable('ret.csv');
position = readtable('ind_lev_pos_before_stop.csv');

convservative_stoploss(ret, position)