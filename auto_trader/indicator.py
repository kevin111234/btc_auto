import api
import pandas as pd

class Indicator:
    def __init__(self, ticker):
        self.api = api.Api()
        self.ohlcv = self.api.get_ohlcv(ticker, 'minute5', 100)
        self.current_price = self.api.get_current_price(ticker)

    def calculate_rsi(self):
        delta = self.ohlcv['close'].diff()
        gains = delta.clip(lower=0)
        losses = -delta.clip(upper=0)

        n = 14 # 기간 설정

        # 첫 번째 평균값 계산 (SMA)
        avg_gain = gains[:n].mean()
        avg_loss = losses[:n].mean()

        # 이후 평균값 계산 (와일더의 방법)
        avg_gain_list = [avg_gain]
        avg_loss_list = [avg_loss]

        for i in range(n, len(gains)):
            gain = gains.iloc[i]
            loss = losses.iloc[i]

            avg_gain = ((avg_gain * (n - 1)) + gain) / n
            avg_loss = ((avg_loss * (n - 1)) + loss) / n

            avg_gain_list.append(avg_gain)
            avg_loss_list.append(avg_loss)

        # RS 및 RSI 계산
        rs = pd.Series(avg_gain_list, index=delta.index[n-1:]) / pd.Series(avg_loss_list, index=delta.index[n-1:])
        rsi = 100 - (100 / (1 + rs))

        return rsi.iloc[-1], rsi.iloc[-2]

    def calculate_volume_profile(self, num_bins=12, time_period=100):
        """
        볼륨 프로파일을 계산하는 함수
        
        Parameters:
        - num_bins: 가격 구간의 개수 (기본값: 12)
        - time_period: 분석할 기간 (기본값: 100)
        
        Returns:
        - price_levels: 가격 구간별 거래량 정보를 담은 DataFrame
        """
        df = self.ohlcv.tail(time_period)
        
        # 가격 범위 설정
        price_high = df['high'].max()
        price_low = df['low'].min()
        price_bins = pd.interval_range(start=price_low, end=price_high, periods=num_bins)
        
        # 각 봉의 거래량을 가격 구간에 분배
        volume_profile = pd.DataFrame(columns=['volume'])
        
        for idx, row in df.iterrows():
            # 각 봉에서 거래된 구간 찾기
            candle_bins = [bin for bin in price_bins if (row['low'] <= bin.right and row['high'] >= bin.left)]
            # 거래량을 구간별로 균등 분배
            volume_per_bin = row['volume'] / len(candle_bins)
            
            for price_bin in candle_bins:
                if price_bin not in volume_profile.index:
                    volume_profile.loc[price_bin] = 0
                volume_profile.loc[price_bin, 'volume'] += volume_per_bin
        
        # 가격 구간별 거래량 비율 계산
        volume_profile['volume_ratio'] = volume_profile['volume'] / volume_profile['volume'].sum() * 100
        
        return volume_profile

    def get_new_rsi(self):
        rsi = self.calculate_rsi()
        # 50 이상 rsi 반전
        if rsi >= 50:
            rsi = 100 - rsi
        if rsi <= 20:
            return 20
        elif rsi <= 25:
            return 25
        elif rsi <= 30:
            return 30
        elif rsi <= 35:
            return 35
        else:
            return 50

    def get_volume_profile(self):
        """
        볼륨 프로파일을 기반으로 주요 가격 레벨을 반환
        
        Returns:
        - poc: Point of Control (가장 거래량이 많은 가격대)
        - support_levels: 주요 지지 레벨 리스트
        - resistance_levels: 주요 저항 레벨 리스트
        """
        volume_profile = self.calculate_volume_profile()
        
        # POC (Point of Control) - 가장 거래량이 많은 가격대
        poc = volume_profile['volume_ratio'].idxmax()
        
        # 현재가 기준으로 지지/저항 레벨 구분
        current_price = self.current_price
        
        # 거래량 비율이 10% 이상인 주요 가격대 선별
        significant_levels = volume_profile[volume_profile['volume_ratio'] >= 10].index
        
        support_levels = [level for level in significant_levels 
                          if level.mid < current_price]
        resistance_levels = [level for level in significant_levels 
                            if level.mid > current_price]
        
        # 가격 순으로 정렬
        support_levels.sort(key=lambda x: x.mid, reverse=True)
        resistance_levels.sort(key=lambda x: x.mid)
        
        return poc, support_levels, resistance_levels

    def get_position_size(self):
        # 현재 rsi 값에 따라서만 포지션 사이즈 결정
        rsi = self.get_new_rsi()
        if rsi == 20:
            return 0.2 # 20%
        elif rsi == 25:
            return 0.4 # 40%
        elif rsi == 30:
            return 0.3 # 30%
        elif rsi == 35:
            return 0.1 # 10%
        else:
            return 0
