import pandas as pd

class Indicator:
    def __init__(self, df):
        self.df = df

    def calculate_rsi(self):
        data = self.df
        delta = data['close'].diff()
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

    def get_new_rsi(self):
        rsi, previous_rsi = self.calculate_rsi()
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