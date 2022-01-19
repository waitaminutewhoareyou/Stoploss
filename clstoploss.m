function position = clstoploss(ret, lev, pos,class,clstop)
% This function takes a proposed lev and pos from a strategy
% consider several practical concerns and adjust them appropriately
% [lev2,pos2,stop,remain] = practical_adjustment(RETt2, Ellt(1:end-1,:), W2t,Volt(1:end-1,:),wsl*100,0.05,-5);
% ret=RETt2;
% lev=lev2;
% pos=pos2;
% clstop=-0.05;
% portstop=-0.05;

[N,m] = size(ret); % m is # of assets, N is # of days
[a,b] = size(class); % a is # of assets, b is # of classes

%% asset class stop loss
ret(ret==-999)=0;
lret=ret.*lev.*pos; % leveraged return.
clret=lret*class./(pos*class); % asset class return.
clret(isnan(clret))=0;

loglevdaily=log(1+clret/100);% there are two data points that <-100.
weekly_cumsum=cumsum(loglevdaily);

tmp=kron([zeros(1,b);weekly_cumsum(5:5:end-1,:)],ones(5,1));
gap=length(tmp)-length(weekly_cumsum);
weekly_cumsum = weekly_cumsum- tmp(1:end-gap,:);


%tmp=reshape(positiont,[5,N/5,m]);

gg=mod(N,5);
stoploss_flag1= weekly_cumsum<clstop;
%tmp=reshape(stoploss_flag,[5,N/5,m]);

stoploss_flag=stoploss_flag1(1:N-gg,:);
remainingday_flag=false(N-gg,b);
for i=1:4
    idx=stoploss_flag(i:5:end,:)==1;
    remainingday_flag(i+1:5:end,:)=idx;
    tmp=stoploss_flag(i+1:5:end,:);
    tmp(idx)=1;
    stoploss_flag(i+1:5:end,:)=tmp;
end

% force out if stop loss is triggered on the last day of week
% stoploss_flag2=adjdaily<dailylimit;
% 
% for i=5:5:N-gg-5
%     for j=1:m
%         if stoploss_flag1(i-1,j)==0 && stoploss_flag1(i,j)==1
%             remainingday_flag(i+1:i+5,j)=1;
%         end
%     end
% end

% handle the last week separately
stoploss_lastweek=stoploss_flag1(N-gg+1:N,:);
remainingday_lastweek=false(gg,b);
if gg>=2 % if gg = 1, there is no way to react.
for i=1:gg-1
    idx=stoploss_lastweek(i,:)==1;
    remainingday_lastweek(i+1,:)=idx;
    tmp=stoploss_lastweek(i+1,:);
    tmp(idx)=1;
    stoploss_lastweek(i+1,:)=tmp;     
end
end

% for j=1:m
%     if stoploss_flag1(N-gg-1,j)==0 && stoploss_flag1(N-gg,j)==1
%         remainingday_flag(N-gg+1:N,j)=1;
%     end
% end


remainingday_flag=[remainingday_flag;remainingday_lastweek];
positiont=pos;
asset_flag=remainingday_flag(:,1:4)*class(:,1:4)';
positiont(asset_flag>0) =0;

%% output:
position=positiont;

end