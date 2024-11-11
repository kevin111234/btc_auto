import os
import time
import numpy as np
import pandas as pd
from datetime import datetime
import pyupbit
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

# 환경변수 설정
load_dotenv()
ACCESS_KEY = os.getenv('UPBIT_ACCESS_KEY')
SECRET_KEY = os.getenv('UPBIT_SECRET_KEY')
SLACK_TOKEN = os.getenv('SLACK_API_TOKEN')
SLACK_CHANNEL = os.getenv('SLACK_CHANNEL_ID')

# 거래할 코인 티커 설정
TICKERS = ['KRW-BTC', 'KRW-ETH']

# Upbit, Slack 클라이언트 초기화
upbit = pyupbit.Upbit(ACCESS_KEY, SECRET_KEY)
slack_client = WebClient(token=SLACK_TOKEN)

def send_slack_message(message):
    try:
        slack_client.chat_postMessage(channel=SLACK_CHANNEL, text=message)
    except SlackApiError as e:
        print(f"Error sending message: {e.response['error']}")

class CoinTrader:
    def __init__(self, ticker):
        self.ticker = ticker
        self.currency = ticker.split('-')[1]

    def calculate_indicators(self, df):
        # RSI 계산
        delta = df['close'].diff()
        gains = delta.where(delta > 0, 0)
        losses = -delta.where(delta < 0, 0)
        
        avg_gain = gains.rolling(window=14).mean()
        avg_loss = losses.rolling(window=14).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        # 볼린저 밴드 계산
        rolling_mean = df['close'].rolling(window=20).mean()
        rolling_std = df['close'].rolling(window=20).std()
        
        upper_band = rolling_mean + (rolling_std * 2)
        lower_band = rolling_mean - (rolling_std * 2)

        return rsi.iloc[-1], upper_band.iloc[-1], rolling_mean.iloc[-1], lower_band.iloc[-1]

    def get_position_size(self, rsi, limit_amount):
        if rsi <= 20:
            return limit_amount * 0.4
        elif rsi <= 25:
            return limit_amount * 0.3
        elif rsi <= 30:
            return limit_amount * 0.2
        elif rsi <= 35:
            return limit_amount * 0.1
        return 0

def get_asset_info(upbit):
    try:
        balances = upbit.get_balances()
        
        krw_balance = float(next((balance['balance'] for balance in balances 
                                if balance['currency'] == 'KRW'), 0))
        
        coin_info = {}
        total_asset = krw_balance

        for ticker in TICKERS:
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

        limit_amount_per_coin = total_asset * 0.48
        
        return {
            'krw_balance': krw_balance,
            'coin_info': coin_info,
            'total_asset': total_asset,
            'limit_amount_per_coin': limit_amount_per_coin
        }

    except Exception as e:
        print(f"자산 정보 조회 중 에러 발생: {str(e)}")
        return None

def send_asset_info(asset_info):
    if asset_info is None:
        return
        
    message = f"""
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
──────────────"""

    message += f"""
💵 총 자산: {asset_info['total_asset']:,.0f}원
⚖️ 코인당 투자한도: {asset_info['limit_amount_per_coin']:,.0f}원
"""

    send_slack_message(message)

def main():
    print("프로그램을 시작합니다.")
    traders = {ticker: CoinTrader(ticker) for ticker in TICKERS}
    
    # 초기 자산 정보 조회
    asset_info = get_asset_info(upbit)
    send_asset_info(asset_info)
    if asset_info is None:
        print("초기 자산 정보 조회 실패. 프로그램을 종료합니다.")
        return
    
    while True:
        try:
            # 각 코인별 매매 신호 확인 및 주문 실행
            for ticker, trader in traders.items():
                try:
                    # 가격 데이터 조회
                    df = pyupbit.get_ohlcv(ticker, interval="minute5", count=100)
                    
                    # 지표 계산
                    rsi, upper_band, middle_band, lower_band = trader.calculate_indicators(df)
                    current_price = pyupbit.get_current_price(ticker)
                    
                    # 매매 신호 판단
                    buy_signal = (rsi <= 35 and current_price <= lower_band)
                    sell_signal = (rsi >= 65 and current_price >= upper_band)
                    
                    limit_amount = asset_info['limit_amount_per_coin']
                    
                    if asset_info is None:
                        continue
                    
                    if buy_signal:
                        asset_info = get_asset_info(upbit)
                        position_size = trader.get_position_size(rsi, limit_amount)
                        if position_size > 0 and asset_info['krw_balance'] >= position_size:
                            order = upbit.buy_market_order(ticker, position_size)
                            time.sleep(10)
                            if order:
                                message = f"[{ticker}] 매수 주문 체결\n금액: {position_size:,.0f}원\nRSI: {rsi:.2f}"
                                send_slack_message(message)
                                asset_info = get_asset_info(upbit)
                                send_asset_info(asset_info)
                    
                    elif sell_signal:
                        asset_info = get_asset_info(upbit)
                        coin_balance = asset_info['coin_info'][trader.currency]['balance']
                        position_size = trader.get_position_size(100-rsi, limit_amount)
                        sell_amount = min(position_size / current_price, coin_balance)
                        if sell_amount > 0:
                            order = upbit.sell_market_order(ticker, sell_amount)
                            time.sleep(10)
                            if order:
                                message = f"[{ticker}] 매도 주문 체결\n수량: {sell_amount:.8f}\nRSI: {rsi:.2f}"
                                send_slack_message(message)
                                asset_info = get_asset_info(upbit)
                                send_asset_info(asset_info)
                    else:
                      print("매수/매도 신호가 없습니다. 기회 탐색중...")
                
                except Exception as e:
                    send_slack_message(f"{ticker} 매매 처리 중 에러 발생: {str(e)}")
                    
            time.sleep(10)
            
        except Exception as e:
            send_slack_message(f"메인 루프 에러: {str(e)}")
            time.sleep(10)

if __name__ == "__main__":
    main()