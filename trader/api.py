from config import Config
import pyupbit
from slack_sdk import WebClient

class API:
    def __init__(self):
        self.config = Config()
        self.upbit = pyupbit.Upbit(self.config.upbit_access_key, self.config.upbit_secret_key)
        self.slack = WebClient(token=self.config.slack_api_token)

    def send_slack_message(self, channel_id, message):
        try:
            self.slack.chat_postMessage(channel=channel_id, text=message)
        except Exception as e:
            print(f"Error sending message: {e}")

    def get_asset_info(self):
        try:
            balances = self.upbit.get_balances()
            krw_balance = float(next((balance['balance'] for balance in balances 
                                    if balance['currency'] == 'KRW'), 0))
            coin_info = {}
            total_asset = krw_balance

            for ticker in self.config.coin_ticker:
                currency = ticker.split('-')[1]
                current_price = pyupbit.get_current_price(ticker)

                coin_balance = float(next((balance['balance'] for balance in balances 
                                          if balance['currency'] == currency), 0))
                avg_buy_price = float(next((balance['avg_buy_price'] for balance in balances 
                                          if balance['currency'] == currency), 0))
                
                coin_value = coin_balance * current_price
                total_asset += coin_value

                profit_rate = ((current_price - avg_buy_price) / avg_buy_price * 100) if avg_buy_price > 0 else 0

                coin_info[currency] = {
                    'balance': coin_balance,
                    'avg_price': avg_buy_price,
                    'current_price': current_price,
                    'value': coin_value,
                    'profit_rate': profit_rate
                }
            
            return {
                'krw_balance': krw_balance,
                'coin_info': coin_info,
                'total_asset': total_asset
            }

        except Exception as e:
            print(f"자산 정보 조회 중 에러 발생: {str(e)}")
            return None

    def get_limit_amount(self):
        try:
            # 원화 잔액 조회
            balances = self.upbit.get_balances()
            krw_balance = float(next((balance['balance'] for balance in balances 
                                    if balance['currency'] == 'KRW'), 0))
            
            # 코인별 현재가 조회
            current_prices = {ticker: self.get_current_price(ticker) for ticker in self.config.coin_ticker}
            
            # 코인별 보유 자산 계산
            balance_dict = {b['currency']: b for b in balances}
            coin_values = {}
            total_asset = krw_balance
            
            for ticker in self.config.coin_ticker:
                currency = ticker.split('-')[1]
                current_price = current_prices[ticker]
                balance_info = balance_dict.get(currency, {})
                coin_balance = float(balance_info.get('balance', 0))
                coin_value = coin_balance * current_price
                coin_values[ticker] = coin_value
                total_asset += coin_value
            
            # 코인 개수로 분배할 금액 계산
            coin_count = len(self.config.coin_ticker)
            if coin_count == 0:
                raise ValueError("코인 개수가 0입니다")
                
            target_amount_per_coin = total_asset / coin_count
            
            # 각 코인별 매수 가능 금액 계산
            limit_amounts = {}
            negative_sum = 0
            negative_count = 0
            
            # 구매 제한이 음수인지 확인
            for ticker in self.config.coin_ticker:
                limit_amount = target_amount_per_coin - coin_values[ticker]
                if limit_amount < 0:
                    negative_sum += abs(limit_amount)
                    negative_count += 1
                    limit_amounts[ticker] = 0
                else:
                    limit_amounts[ticker] = limit_amount
            
            # 코인 보유량 > 매수가능금액 인 경우 해당 금액만큼 다른 코인들에게 분배
            if negative_count > 0 and len(self.config.coin_ticker) > negative_count:
                additional_reduction = negative_sum / (len(self.config.coin_ticker) - negative_count)
                for ticker in self.config.coin_ticker:
                    if limit_amounts[ticker] > 0:
                        limit_amounts[ticker] -= additional_reduction
                    
            return limit_amounts
            
        except Exception as e:
            error_msg = f"주문 가능 금액 조회 중 오류 발생: {str(e)}"
            self.send_slack_message(self.config.slack_error_channel, error_msg)
            print(error_msg)
            return {}
