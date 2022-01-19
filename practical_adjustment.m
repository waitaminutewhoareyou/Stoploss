function [lev,pos,stoploss_flag1,remainingday_flag] = practical_adjustment(ret, lev, pos,vol,voltarget,budget,dailylimit)
% This function takes a proposed lev and pos from a strategy
% consider several practical concerns and adjust them appropriately

[N,m] = size(ret); % m is # of assets, N is # of days

% ret=RETt2;lev=Ellt(1:end-1,:);pos=W2t;vol=Volt(1:end-1,:);voltarget=wsl*100;budget=0.05;dailylimit=-5;

%% 3. some assets are not trade-able on some days.
% we simply take the previous position to fill in.
% then we need to normalize those not locked positions.
mask= ret== -999;

pos(mask)=-999;

%% update the locked positions to the nearest open position of the same
% asset. This vectorization is very clever...
dummypos=[zeros(1,m);pos];
%
for i=1:m
    idx=dummypos(:,i)~=-999;
    tmp=dummypos(idx,i);
    dummypos(:,i) = tmp(cumsum(idx));
end
pos=dummypos(2:end,:);

%% find the sum of the locked and normalized the unlocked assets.
tmp1=pos;
tmp1(~mask) = 0;
tmp2=pos;
tmp2(mask)=0;
locked=sum(abs(tmp1),2);
idx=locked>1 | locked==0; % when the locked has 0

% this at least ensures that nothing is > 1
tmp2(~idx,:)=bsxfun(@times, tmp2(~idx,:),(1-locked(~idx))./sum(tmp2(~idx,:),2));  

% there is a chance that a day is < 1 but that's fine.

% normalized the unlocked assets
pos=tmp1+tmp2;


%% 4. trim risk budget
 % maximum position (unlevered position for each asset)
 % fixed budget.

positiont=pos;
positiont(positiont==-999)=0;
positiont(positiont>budget)=budget;
positiont(positiont<-budget)=-budget;


%% 5. stop loss
ret(ret==-999)=0;
% lret=ret.*lev; % leveraged return.


limit=-voltarget/52^.5;


levdaily=sign(positiont).*ret;
adjdaily=sign(positiont).*ret./vol*sqrt(252);

levdaily(levdaily<-99.9)=-99.9; % can't lose more than what we have.

loglevdaily=log(1+levdaily/100);% there are two data points that <-100.
weekly_cumsum=cumsum(loglevdaily);

tmp=kron([zeros(1,m);weekly_cumsum(5:5:end-1,:)],ones(5,1));
gap=length(tmp)-length(weekly_cumsum);
weekly_cumsum = weekly_cumsum- tmp(1:end-gap,:);
weekly_cumsum = weekly_cumsum.*lev;

%tmp=reshape(positiont,[5,N/5,m]);

gg=mod(N,5);
stoploss_flag1=adjdaily<dailylimit | weekly_cumsum*100<limit;
%tmp=reshape(stoploss_flag,[5,N/5,m]);

stoploss_flag=stoploss_flag1(1:N-gg,:);
remainingday_flag=false(N-gg,m);
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
remainingday_lastweek=false(gg,m);
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
positiont(remainingday_flag) =0;

%% output:
pos=positiont;

end