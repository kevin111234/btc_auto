from api import API
from notifier import Notifier
from indicator import Indicator

class Trader:
    def __init__(self, currency):
        self.currency = currency
        self.api = API()
        self.notifier = Notifier()
        self.indicator = Indicator(currency)

    def signal_check(self, asset_info):
        data = self.api.get_ohlcv(self.currency, interval='minute5')
        current_rsi, previous_rsi = self.indicator.calculate_rsi(data)

        buy_signal = (current_rsi <= 35 and previous_rsi <= current_rsi)
        sell_signal = (current_rsi >= 65 and previous_rsi >= current_rsi and
                      asset_info['coin_info'][self.currency]['profit_rate'] >= 0.5)
        
        new_rsi = self.indicator.get_new_rsi(data)

        return buy_signal, sell_signal, new_rsi, current_rsi

