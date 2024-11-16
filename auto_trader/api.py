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
                    'balance': coin_balance, # type: float
                    'avg_price': avg_buy_price, # type: float
                    'current_price': current_price, # type: float
                    'value': coin_value, # type: float
                    'profit_rate': round(profit_rate, 2) # type: float
                }
            
            return {
                'krw_balance': krw_balance, # type: float
                'coin_info': coin_info,
                'total_asset': total_asset # type: float
            }
            
        except Exception as e:
            error_msg = f"자산 정보 조회 중 오류 발생: {str(e)}"
            self.send_slack_message(self.config.slack_channel_id, error_msg)
            print(error_msg)
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

    def create_asset_report(self, asset_info, limit_amounts):
        message = """
📊 자산 현황 보고
──────────────
💰 보유 KRW: {asset_info['krw_balance']:,.0f}원
──────────────"""

        for currency, info in asset_info['coin_info'].items():
            message += f"""
🪙 {currency}:
수량: {info['balance']:.8f}
평균매수가: {info['avg_price']:,.0f}원
현재가격: {info['current_price']:,.0f}원
평가금액: {info['value']:,.0f}원
수익률: {info['profit_rate']:.2f}%
코인별 투자한도: {limit_amounts[currency]:,.0f}원
──────────────
"""
        message += f"""
💵 총 자산: {asset_info['total_asset']:,.0f}원
💵 전체 수익률: {((asset_info['total_asset'] - 200000) / 200000 * 100):.2f}%
──────────────
"""
        return message
    
    def report_asset_info(self):
        asset_info = self.get_asset_info()
        limit_amounts = self.get_limit_amount()
        if asset_info and limit_amounts:
            message = self.create_asset_report(asset_info, limit_amounts)
            self.send_slack_message(self.config.slack_asset_channel, message)

if __name__ == "__main__":
    print("api 테스트")
    api = API()
