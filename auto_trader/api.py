import pyupbit
import slack
from config import Config

class API:
    def __init__(self):
        self.config = Config()
        self.upbit = pyupbit.Upbit(self.config.upbit_access_key, self.config.upbit_secret_key)
        self.slack = slack.WebClient(token=self.config.slack_api_token)

    def send_slack_message(self, channel_id, message):
        try:
            self.slack.chat_postMessage(channel=channel_id, text=message)
        except Exception as e:
            print(f"Error sending message: {e}")

    def get_current_price(self, ticker):
        try:
            return pyupbit.get_current_price(ticker)
        except Exception as e:
            print(f"Error getting current price: {e}")

    def get_ohlcv(self, ticker, interval, count=100):
        try:
            return pyupbit.get_ohlcv(ticker, interval, count)
        except Exception as e:
            print(f"Error getting OHLCV: {e}")
    
    def get_asset_info(self):
        try:
            balances = self.upbit.get_balances()
            if not balances:
                raise ValueError("잔액 정보를 가져올 수 없습니다")
            
            krw_balance = float(next((balance['balance'] for balance in balances 
                                    if balance['currency'] == 'KRW'), 0))
            
            current_prices = {ticker: self.get_current_price(ticker) for ticker in self.config.coin_ticker}
            
            coin_info = {}
            total_asset = krw_balance
            
            balance_dict = {b['currency']: b for b in balances}
            
            for ticker in self.config.coin_ticker:
                currency = ticker.split('-')[1]
                current_price = current_prices[ticker]
                
                if current_price is None:
                    self.send_slack_message(self.config.slack_channel_id, 
                                        f"Warning: {ticker}의 현재가를 가져올 수 없습니다")
                    continue
                    
                balance_info = balance_dict.get(currency, {})
                coin_balance = float(balance_info.get('balance', 0))
                avg_buy_price = float(balance_info.get('avg_buy_price', 0))
                
                coin_value = coin_balance * current_price
                total_asset += coin_value
                
                profit_rate = ((current_price - avg_buy_price) / avg_buy_price * 100) if avg_buy_price > 0 else 0
                
                coin_info[currency] = {
                    'balance': coin_balance,
                    'avg_price': avg_buy_price,
                    'current_price': current_price,
                    'value': coin_value,
                    'profit_rate': round(profit_rate, 2)
                }
            
            return {
                'krw_balance': krw_balance,
                'coin_info': coin_info,
                'total_asset': total_asset
            }
            
        except Exception as e:
            error_msg = f"자산 정보 조회 중 오류 발생: {str(e)}"
            self.send_slack_message(self.config.slack_channel_id, error_msg)
            print(error_msg)
            return None

if __name__ == "__main__":
    print("api 테스트")
    api = API()
