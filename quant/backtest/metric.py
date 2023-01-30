import numpy as np
import pandas as pd
from typing import *
from itertools import groupby, chain

import yfinance as yf

class Metric:
    def __init__(self, portfolio: Union[pd.DataFrame, pd.Series],
                 freq: str='day'):
        """Metric class

        Args:
            portfolio (Union[pd.DataFrame, pd.Series]): 포트폴리오 자산별 가격 혹은 총자산 가격표.
            freq (str, optional): 데이터 수집 주기. Defaults to 'day'.
        """
        if isinstance(portfolio, pd.DataFrame):
            self.portfolio = portfolio.sum(axis=1)
        elif isinstance(portfolio, pd.Series):
            self.portfolio = portfolio
        else:
            raise TypeError()
        
        self.param = self.annualize_scaler(freq)
        self.freq2day = int(252 / self.param)
        
        self.rets = self.portfolio.pct_change().fillna(0)
        self.cum_rets = (1 + self.rets).cumprod()
    
    def annualize_scaler(self, param: str) -> int:
        # 주기에 따른 연율화 파라미터 반환해주는 함수
        annualize_scale_dict = {
            'day': 252,
            'week': 52,
            'month': 12,
            'quarter': 4,
            'half-year': 2,
            'year': 1
        }
        try:
            scale: int = annualize_scale_dict[param]
        except:
            raise Exception("freq is only ['day', 'week', 'month', \
                'quarter', 'half-year', 'year']")
        
        return scale
    
    def calc_lookback(self, lookback, scale) -> int:
        # lookback을 주기에 맞게 변환해주는 함수
        if isinstance(lookback, int):
            return lookback * scale
        elif isinstance(lookback, float):
            return int(lookback * scale)
    
    def rolling(func):
        # 옵션 활용을 위한 데코레이터
        def wrapper(self, returns=None, rolling=False, lookback=1, *args, **kwargs):
            if returns is None:
                rets = self.rets.copy()
            else:
                try:
                    rets = returns.copy()
                except AttributeError:
                    rets = returns
            
            lookback = self.calc_lookback(lookback, self.param)
            
            if rolling:
                rets = rets.rolling(lookback)
            
            result = func(self, returns=rets, *args, **kwargs)
            return result.fillna(0) if isinstance(result, pd.Series) else result
        return wrapper
    
    def external(func):
        # 옵션 활용을 위한 데코레이터
        def wrapper(self, returns=None, *args, **kwargs):
            if returns is None:
                rets = self.rets.copy()
            else:
                try:
                    rets = returns.copy()
                except AttributeError:
                    rets = returns
            
            result = func(self, returns=rets, *args, **kwargs)
            return result
        return wrapper
    
    @external
    def annualized_return(self, returns: pd.Series=None) -> float:
        return returns.add(1).prod() ** (self.param / len(returns)) - 1
    
    @external
    def annualized_volatility(self, returns: pd.Series=None) -> float:
        return returns.std() * np.sqrt(self.param)
    
    @rolling
    def sharp_ratio(self, returns: pd.Series,
                    rolling: bool=False,
                    lookback: Union[float, int]=1,
                    yearly_rfr: float=0.04) -> Union[pd.Series, float]:
        '''Sharp ratio method

        Args:
            price (Union[pd.DataFrame, pd.Series]):
                - DataFrame -> 포트폴리오 테이블
                - Series -> 개별종목 시계열 데이터
            freq (str, optional):
                포트폴리오 시간 간격 -> ['day', 'week', 'month', 'quarter', 'half-year', 'year'] 중 택1. 
                Defaults to 'day'.
            yearly_rfr (float, optional): 무위험자산 수익률(예금 이자). Defaults to 0.04.
            rolling (bool, optional):
                False - 전체 연율화 샤프지수
                Ture - (lookback)년 롤링 연율화 샤프지수
                Defaults to False.
            lookback (int, optional): 수익률 롤링 윈도우(단위: 년). Defaults to 1.
        
        Returns:
            Union[pd.Series, float]:
                - Series -> (lookback)년 롤링 연율화 샤프지수
                - float -> 연율화 샤프지수
        '''
        return (self.annualized_return(returns) - yearly_rfr)/self.annualized_volatility(returns)
    
    @rolling
    def sortino_ratio(self, returns: pd.Series=None,
                      rolling: bool=False,
                      lookback: Union[float, int]=1,
                      yearly_rfr: float=0.03) -> Union[pd.Series, float]:
        """Sortino ratio calculation method

        Args:
            price (Union[pd.DataFrame, pd.Series]):
                - DataFrame -> 포트폴리오 테이블
                - Series -> 개별종목 시계열 데이터
            freq (str, optional):
                포트폴리오 시간 간격 -> ['day', 'week', 'month', 'quarter', 'half-year', 'year'] 중 택1. 
                Defaults to 'day'.
            yearly_rfr (float, optional): 무위험자산 수익률(예금 이자). Defaults to 0.04.
            rolling (bool, optional):
                False - 전체 연율화 소르티노 지수
                Ture - (lookback)년 롤링 연율화 소르티노 지수
                Defaults to False.
            lookback (int, optional): 수익률 롤링 윈도우(단위: 년). Defaults to 1.

        Returns:
            Union[pd.Series, float]:
                - Series -> (lookback)년 롤링 연율화 소르티노 지수
                - float -> 연율화 소르티노 지수
        """
        def downside_std(returns):
            returns[returns >= 0] = 0
            return returns.std() * np.sqrt(self.param)
        
        return self.annualized_return(returns) - yearly_rfr / downside_std(returns)

    @rolling
    def calmar_ratio(self, returns: pd.Series=None,
                     rolling: bool=False,
                     lookback: Union[float, int]=1,
                     MDD_lookback: Union[float, int]=3
                     ) -> Union[pd.Series, float]:
        '''Calmar ratio calculation method
        
        Args:
            price (Union[pd.DataFrame, pd.Series]):
                - DataFrame -> 포트폴리오 테이블
                - Series -> 개별종목 시계열 데이터
            freq (str, optional):
                포트폴리오 시간 간격 -> ['day', 'week', 'month', 'quarter', 'half-year', 'year'] 중 택1. 
                Defaults to 'day'.
            rolling (bool, optional):
                False - 전체 연율화 칼머 지수
                Ture - (lookback)년 롤링 연율화 칼머 지수
                Defaults to False.
            lookback (Union[float, int], optional): 수익률 롤링 윈도우(단위: 년). Defaults to 1.
            MDD_lookback (Union[float, int], optional): MDD 롤링 윈도우(단위: 년). Defaults to 3.

        Returns:
            Union[pd.Series, float]:
                - Series -> (lookback)년 롤링 연율화 칼머 지수
                - float -> 연율화 칼머 지수
        '''
        dd = self.drawdown(returns)
        MDD_lookback = self.calc_lookback(MDD_lookback, self.param)
        
        if rolling:
            dd = dd.rolling(MDD_lookback)
        
        calmar = - self.annualized_return(returns) / dd.min()
        return calmar
    
    @external
    def VaR(self, returns: pd.Series=None, delta: float=0.01):
        return returns.quantile(delta)
    
    @rolling
    def VaR_ratio(self, returns: pd.Series=None, 
                  rolling: bool=False, lookback: int=1,
                  delta: float=0.01) -> Union[pd.Series, float]:
        """VaR ratio calculation method

        Args:
            price (Union[pd.DataFrame, pd.Series]):
                - DataFrame -> 포트폴리오 테이블
                - Series -> 개별종목 시계열 데이터
            freq (str, optional):
                포트폴리오 시간 간격 -> ['day', 'week', 'month', 'quarter', 'half-year', 'year'] 중 택1. 
                Defaults to 'day'.
            rolling (bool, optional):
                False - 전체 연율화 VaR 지수
                Ture - (lookback)년 롤링 연율화 VaR 지수
                Defaults to False.
            lookback (Union[float, int], optional): 수익률 롤링 윈도우(단위: 년). Defaults to 1.
            delta (float, optional): 위험구간(z-value corresponding to %VaR). Defaults to 0.01.

        Returns:
            Union[pd.Series, float]:
                - Series -> (lookback)년 롤링 연율화 VaR 지수
                - float -> 연율화 VaR 지수
        """
        ratio = -returns.mean() / self.VaR(returns, delta=delta)
        return ratio

    @external
    def CVaR(self, returns: pd.Series=None, delta=0.01):
        return returns[returns <= self.VaR(returns, delta=delta)].mean()

    @rolling
    def CVaR_ratio(self, returns: pd.Series=None, 
                   rolling: bool=False, lookback: int=1, 
                   delta=0.01) -> Union[pd.Series, float]:
        """CVaR ratio calculation method

        Args:
            price (Union[pd.DataFrame, pd.Series]):
                - DataFrame -> 포트폴리오 테이블
                - Series -> 개별종목 시계열 데이터
            freq (str, optional):
                포트폴리오 시간 간격 -> ['day', 'week', 'month', 'quarter', 'half-year', 'year'] 중 택1. 
                Defaults to 'day'.
            rolling (bool, optional):
                False - 전체 연율화 CVaR 지수
                Ture - (lookback)년 롤링 연율화 CVaR 지수
                Defaults to False.
            lookback (Union[float, int], optional): 수익률 롤링 윈도우(단위: 년). Defaults to 1.
            delta (float, optional): 위험구간(z-value corresponding to %VaR). Defaults to 0.01.

        Returns:
            Union[pd.Series, float]:
                - Series -> (lookback)년 롤링 연율화 CVaR 지수
                - float -> 연율화 CVaR 지수
        """
        if rolling:
            ratio = -returns.mean() / returns.apply(lambda x: self.CVaR(x, delta=delta))
        else:
            ratio = -returns.mean() / self.CVaR(returns, delta=delta)
            
        return ratio

    @rolling
    def hit_ratio(self, returns: pd.Series=None,
                  rolling: bool=False, lookback: int=1,
                  delta=0.01) -> Union[pd.Series, float]:
        """Hit ratio calculation method

        Args:
            price (Union[pd.DataFrame, pd.Series]):
                - DataFrame -> 포트폴리오 테이블
                - Series -> 개별종목 시계열 데이터
            freq (str, optional):
                포트폴리오 시간 간격 -> ['day', 'week', 'month', 'quarter', 'half-year', 'year'] 중 택1. 
                Defaults to 'day'.
            rolling (bool, optional):
                False - 전체 연율화 HR
                Ture - (lookback)년 롤링 연율화 HR
                Defaults to False.
            lookback (Union[float, int], optional): 수익률 롤링 윈도우(단위: 년). Defaults to 1.
            delta (float, optional): 위험구간(z-value corresponding to %VaR). Defaults to 0.01.

        Returns:
            Union[pd.Series, float]:
                - Series -> (lookback)년 롤링 연율화 HR
                - float -> 연율화 HR
        """
        hit = lambda rets: len(rets[rets > 0.0]) / len(rets[rets != 0.0])
        return returns.apply(hit) if rolling else hit(returns)

    @rolling
    def GtP_ratio(self, returns: pd.Series=None,
                  rolling: bool=False, lookback: int=1,
                  delta=0.01) -> Union[pd.Series, float]:
        """Gain-to-Pain ratio(GPR) calculation method

        Args:
            price (Union[pd.DataFrame, pd.Series]):
                - DataFrame -> 포트폴리오 테이블
                - Series -> 개별종목 시계열 데이터
            freq (str, optional):
                포트폴리오 시간 간격 -> ['day', 'week', 'month', 'quarter', 'half-year', 'year'] 중 택1. 
                Defaults to 'day'.
            rolling (bool, optional):
                False - 전체 연율화 GPR
                Ture - (lookback)년 롤링 연율화 GPR
                Defaults to False.
            lookback (Union[float, int], optional): 수익률 롤링 윈도우(단위: 년). Defaults to 1.
            delta (float, optional): 위험구간(z-value corresponding to %VaR). Defaults to 0.01.

        Returns:
            Union[pd.Series, float]:
                - Series -> (lookback)년 롤링 연율화 GPR
                - float -> 연율화 GPR
        """
        GPR = lambda rets: rets[rets > 0.0].mean() / -rets[rets < 0.0].mean()
        return returns.apply(GPR) if rolling else GPR(returns)
    
    @external
    def skewness(self, returns: pd.Series=None) -> float:
        # skewness 계산 메서드
        return self.rets.skew()
    
    @external
    def kurtosis(self, returns: pd.Series=None) -> float:
        # kurtosis 계산 메서드
        return self.rets.kurtosis()
    
    @external
    def drawdown(self, returns: pd.Series=None) -> pd.Series:
        """기간내 최고점 대비 수익하락율(drawdown) 계산 메서드

        Args:
            returns (pd.Series, optional): 시간에 따른 수익률 리스트(Series). Defaults to None.

        Returns:
            - pd.Series: 주기에 따른 drawdown 리스트(Series)
        """
        cum_rets = (1 + returns).cumprod()
        return cum_rets.div(cum_rets.cummax()).sub(1)
    
    @external
    def drawdown_duration(self, returns: pd.Series=None) -> pd.Series:
        
        """drawdown 지속기간 계산 메서드(일 단위)

        Args:
            returns (pd.Series, optional): 시간에 따른 수익률 리스트(Series). Defaults to None.

        Returns:
            - pd.Series: 주기에 따른 drawdown 지속시간 리스트(Series, 일 단위)
        """
        dd = self.drawdown(returns=returns)
        
        ddur_count = list(chain.from_iterable((np.arange(len(list(j))) + 1).tolist() if i==1 else [0] * len(list(j)) for i, j in groupby(dd != 0)))
        ddur_count = pd.Series(ddur_count, index=dd.index)
        temp_df= ddur_count.reset_index()
        temp_df.columns = ['date', 'counts']
        
        count_0 = temp_df.counts.apply(lambda x: 0 if x > 0 else 1)
        cumdays = temp_df.date.diff().dt.days.fillna(0).astype(int).cumsum()
        ddur = cumdays - (count_0 * cumdays).replace(0, np.nan).ffill().fillna(0).astype(int)
        ddur.index = dd.index
        return ddur
    
    @external
    def MDD(self, returns: pd.Series=None) -> float:
        # MDD 계산 메서드
        return self.drawdown(returns).min()
    
    @external
    def MDD_duration(self, returns: pd.Series=None) -> float:
        """MDD 지속기간 계산 메서드

        Args:
            timeseries (bool, optional): _description_. Defaults to False.

        Returns:
            - pd.Series: 모든 시간에 따른 MDD 지속기간 값
            - float: 총 MDD 지속기간 값
        """
        return self.drawdown_duration().max()
        
    def get_rets(self):
        return self.rets
    
    def total_returns(self, returns: pd.Series=None) -> float:
        return (1 + returns).prod()
    
    @external
    def print_report(self, returns: pd.Series=None, delta: float=0.01):
        print(f'Annualized Return: {self.annualized_return(returns):.2%}')
        print(f'Annualized Volatility: {self.annualized_volatility(returns):.2%}')
        print(f'Skewness: {self.skewness(returns):.2f}')
        print(f'Kurtosis: {self.kurtosis(returns):.2f}')
        print(f'Max Drawdown: {self.MDD(returns):.2%}')
        print(f'Max Drawdown Duration: {self.MDD_duration(returns):.0f} days')
        print(f'Annualized Sharp Ratio: {self.sharp_ratio(returns):.2f}')
        print(f'Annualized Sortino Ratio: {self.sortino_ratio(returns):.2f}')
        print(f'Annualized Calmar Ratio: {self.calmar_ratio(returns):.2f}')
        print(f'Annualized VaR: {self.VaR(returns, delta=delta):.2f}')
        print(f'Annualized VaR Ratio: {self.VaR_ratio(returns, delta=delta):.2f}')
        print(f'Annualized CVaR: {self.CVaR(returns, delta=delta):.2f}')
        print(f'Annualized CVaR Ratio: {self.CVaR_ratio(returns, delta=delta):.2f}')
        print(f'Annualized hit Ratio: {self.hit_ratio(returns, delta=delta):.2f}')
        print(f'Annualized GtP Ratio: {self.GtP_ratio(returns, delta=delta):.2f}')
    
    @external
    def rolling_metric_report(self, returns: pd.Series=None,
                              lookback: Union[float, int]=1, delta: float=0.01):
        rolling = True
        
        dd = self.drawdown(returns)
        ddur = self.drawdown_duration(returns)
        sharp = self.sharp_ratio(returns, rolling=rolling, lookback=lookback)
        sortino = self.sortino_ratio(returns, rolling=rolling, lookback=lookback)
        calmar = self.calmar_ratio(returns, rolling=rolling, lookback=lookback)
        VaR = self.VaR(returns, delta=delta)
        VaR_ratio = self.VaR_ratio(returns, rolling=rolling,
                                   lookback=lookback, delta=delta)
        CVaR = self.CVaR(returns, delta=delta)
        CVaR_ratio = self.CVaR_ratio(returns, rolling=rolling,
                                     lookback=lookback, delta=delta)
        hit = self.hit_ratio(returns, rolling=rolling,
                             lookback=lookback, delta=delta)
        GtP = self.GtP_ratio(returns, rolling=rolling,
                             lookback=lookback, delta=delta)
        
if __name__ == '__main__':
    data = yf.download('SPY TLT', start='2002-07-30')['Adj Close']
    test = Metric(data)
    test.print_report()
    test.rolling_metric_report()