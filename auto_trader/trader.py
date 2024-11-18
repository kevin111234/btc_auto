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
        try:
            data = self.api.get_ohlcv(self.currency, interval='minute5')
            if data is None or data.empty:
                raise ValueError(f"{self.currency}의 OHLCV 데이터를 가져오는데 실패했습니다")

            current_rsi, previous_rsi = self.indicator.calculate_rsi(data)

            # currency에서 'KRW-' 접두어 제거
            currency = self.currency.split('-')[1] if '-' in self.currency else self.currency
            
            # asset_info에서 해당 코인 정보 안전하게 접근
            coin_info = asset_info.get('coin_info', {}).get(currency, {})
            profit_rate = coin_info.get('profit_rate', 0)

            buy_signal = (current_rsi <= 35 and previous_rsi <= current_rsi)
            sell_signal = (current_rsi >= 65 and previous_rsi >= current_rsi and
                          profit_rate >= 0.5)
            
            new_rsi = self.indicator.get_new_rsi(data)

            return buy_signal, sell_signal, new_rsi, current_rsi

        except Exception as e:
            raise Exception(f"Signal check failed for {self.currency}: {str(e)}\n"
                            f"Asset info structure: {asset_info}")

