import indicator
import notifier
import api
import config

class Trader:
    def __init__(self):
        self.config = config.Config()
        self.api = api.API(self.config)
        self.notifier = notifier.Notifier(self.config, self.api)
        self.indicator = indicator.Indicator(self.config, self.api)

    def signal_check(self, asset_info, currency):
        rsi, previous_rsi = self.indicator.calculate_rsi()

        buy_signal = (rsi <= 35 and previous_rsi <= rsi)
        sell_signal = (rsi >= 65 and previous_rsi >= rsi and
                      asset_info['coin_info'][currency]['profit_rate'] >= 0.5)