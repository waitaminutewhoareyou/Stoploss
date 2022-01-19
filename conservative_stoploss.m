% Set the number of shocks to trigger stoploss, this can be any real number
num_shocks = 1;


%File processing
ret = readtimetable("ret.csv",'ReadVariableNames',true); % orginal return
pos = readtimetable('ind_lev_pos_before_stop.csv','ReadVariableNames', true); % postion information 
low_ret = readtimetable('low_ret.csv','ReadVariableNames', true); % px_close to px_low return
open_ret = readtimetable('open_ret.csv','ReadVariableNames', true); % px_close to px_open return


% call the function and  output modified postion and modified return
[pos, ret_updated] = intradaystoploss(pos, ret, low_ret, open_ret, num_shocks );
writetimetable(pos,'pos_with_sl.csv')
writetimetable(ret_updated,'result/ret_with_sl.csv')


function [pos, ret_updated] = intradaystoploss(pos, ret, low_ret, open_ret, num_shocks )

ret_updated = ret ; % this is a copy of the original return later on stoploss return will be updated in this copy

% Align all tables within the same time range
datetime_index = intersect(intersect(ret.Date, pos.Date), low_ret.Date);
ret = ret(datetime_index, :);
pos = pos(datetime_index, :);
low_ret = low_ret(datetime_index, :);
[m, ndims] = size(ret);


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%% fuck data

% Parameter Declaration
start_trading = false; % a flag that trading period is not active yet, this flag will be set to true once we encounter the first Monday
% num_shocks = 1;
assets = ret.Properties.VariableNames;

for i = 1:m
    
   
    today = low_ret.Date(i);
    
    % save simulation time
    if today < datetime(1999,1,1)
        continue
    end

    [DayNumber,DayName] = weekday(today);

    % no stoploss procedure on Monday, but need to initiate a new stoploss
    % checklist for the new week
    if strcmp(DayName, 'Mon')
        % this array will store assets which were already stopped earlier this week
        % so don't check thier stoploss in the current week anymore.
        stopped_assets = {};
        current_monday = today;
        next_monday = today + days(7);
        start_trading = true;
        continue

    elseif ~start_trading
        % Be patient until we meet the first Monday
        continue
    end

    % sanity check
    assert((current_monday<= today) & (today <= next_monday), "Error in weekday conversion")



   %%%%%%%%%%%%%%%%%%%%%% Check Intraday Stoploss %%%%%%%%%%%%%%%%
    
   % subset return at close within lookback period
   look_back_end_date = current_monday;
   look_back_start_date = look_back_end_date - days(252);
   look_back_data = ret{(ret.Date > look_back_start_date) & (ret.Date < look_back_end_date), :}; 
   
   %%%%%%%%%%%%%%%%%% Check current day return %%%%%%%%%%%%%%%%%%
   % calculate stoploss level return if triggered
   sl_day_ret = std(look_back_data) * (-num_shocks);
   % check at market open
   sl_open_day_indicator =  open_ret{today, :} <= sl_day_ret;
   % check intraday
   sl_day_indicator = low_ret{today, :} <= sl_day_ret;

   
   %%%%%%%%%%%%%%%%%% Check current week cumulative return breach %%%%%%%%%%%%%%%%%%
   current_week_start_day = current_monday + days(1);
   current_week_ret = ret{(ret.Date >= current_week_start_day) & (ret.Date < today), :}; % return series since current Tuedsay
   current_week_cum_ret = prod(1 + current_week_ret) ; % cumulative return since this week's Tuesday
   num_days_passed_in_current_week = days(today - current_monday);
   sl_cum_ret = std(look_back_data) * (-sqrt(num_days_passed_in_current_week) * num_shocks);

   % check return at market open
   current_week_cum2open_ret = current_week_cum_ret .* (1 + open_ret{today, :}) - 1;
   sl_open_cum_indicator = current_week_cum2open_ret <= sl_cum_ret;
   % similarly, check return intraday
   current_week_cum2low_ret = current_week_cum_ret .* (1 + low_ret{today, :}) - 1;
   sl_cum_indicator = current_week_cum_ret <= sl_cum_ret;

   % Asset that triggered any of the four stoploss conditioned will be
   % stored in sl_asset
   sl_assets = assets(sl_open_day_indicator | sl_day_indicator | sl_open_cum_indicator | sl_cum_indicator);

   if ~isempty(sl_assets)
       sl_assets = sl_assets(low_ret{today,sl_assets} ~= 0); % clean the data a little bit

       % remove those assets that were already stopped earlier this week to
       % avoid double counting
       temp_sl_assets = [];
       for asset_idx = 1:length(sl_assets)

           if ~ismember(sl_assets(asset_idx), stopped_assets)
               temp_sl_assets = [temp_sl_assets, sl_assets(asset_idx)];
           end
       end
       sl_assets = temp_sl_assets;
       % Include today's stopped assets in this week's stopped asset
       stopped_assets = [stopped_assets, sl_assets];
   end


   % Since we just remove some assets (that are stopped earlier this week)
   % from today's stopped assets, we proceed to check if there is any stopped
   % asset left, if so, update their stoploss return to the ret_updated, 
   % and set their position in the remaining week as 0
   if ~isempty(sl_assets)
       sl_ret = []; % record stoploss return, this will be loaded into ret_updated 
        
       % iterate through all assets
       for asset_idx = 1:length(assets)
        asset = assets(asset_idx);
        
        % if no stoploss is triggered for this asset, let it go
        if ~ismember(asset, sl_assets)
            continue
        end
        
        % If its cumulative return or current day return is breached at
        % market open,  then we sell it and record market open as our
        % return
        if ismember(asset, assets(sl_open_day_indicator | sl_open_cum_indicator))
            sl_ret =  [sl_ret, open_ret{today, asset}];
        
        % If current day return is breached but cumulative return is fine,
        % then set the stoploss return at the intrday stop level
        elseif ismember(asset,  assets(sl_day_indicator & ~sl_cum_indicator))
            sl_ret = [sl_ret, sl_day_ret(asset_idx)];
        % similar to the above branch
        elseif ismember(asset,  assets(~sl_day_indicator & sl_cum_indicator))
            sl_ret = [sl_ret, sl_cum_ret(asset_idx)];
        % If both current day return and cumulative return is breached,
        % then set the stoploss return to whichever is higher, because the
        % higher one would trigged stoploss signal prior to the lower one.
        elseif ismember(asset,  assets(sl_day_indicator & sl_cum_indicator))
            sl_ret = [sl_ret, max(sl_day_ret(asset_idx), sl_cum_ret(asset_idx))];
        % This can't happen unless we miss any stoploss scenario
        else
            disp(['This cannot occur.'])
        end
       end

       %  Starting from next trading day onwards, position of stoploss
       %  assets would be set to 0
       pos{(pos.Date > today) & (pos.Date <= next_monday),sl_assets } = 0;
       % Update the realized stoploss return
       ret_updated{today, sl_assets} = sl_ret;

       
   end


   
   % disp(['today is' num2str(weekday(low_ret.Date(i)))])
end
end