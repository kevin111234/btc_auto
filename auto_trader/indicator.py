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

        n = 14

        avg_gain = gains[:n].mean()
        avg_loss = losses[:n].mean()

        avg_gain_list = [avg_gain]
        avg_loss_list = [avg_loss]

        for i in range(n, len(gains)):
            gain = gains.iloc[i]
            loss = losses.iloc[i]

            avg_gain = ((avg_gain * (n - 1)) + gain) / n
            avg_loss = ((avg_loss * (n - 1)) + loss) / n

            avg_gain_list.append(avg_gain)
            avg_loss_list.append(avg_loss)

        rs = pd.Series(avg_gain_list, index=delta.index[n-1:]) / pd.Series(avg_loss_list, index=delta.index[n-1:])
        rsi = 100 - (100 / (1 + rs))

        return rsi.iloc[-1]

