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

        return rsi.iloc[-1]

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

