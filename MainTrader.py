import os
from dotenv import load_dotenv
import pyupbit
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import pandas as pd
import time

# 환경변수 설정
load_dotenv()
UPBIT_ACCESS_KEY = os.getenv('UPBIT_ACCESS_KEY')
UPBIT_SECRET_KEY = os.getenv('UPBIT_SECRET_KEY')
SLACK_API_TOKEN = os.getenv('SLACK_API_TOKEN')
SLACK_CHANNEL_ID = os.getenv('SLACK_CHANNEL_ID')
COIN_TICKER = os.getenv('COIN_TICKER')

# 거래중인 코인 티커 목록
TICKERS = ['KRW-BTC', 'KRW-ETH']

# Upbit, Slack 클라이언트 초기화
upbit = pyupbit.Upbit(UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY)
slack_client = WebClient(token=SLACK_API_TOKEN)

# SLACK 메시지 전송 함수
def send_slack_message(message):
    try:
        slack_client.chat_postMessage(channel=SLACK_CHANNEL_ID, text=message)
    except SlackApiError as e:
        print(f"Error sending message: {e.response['error']}")

def calculate_indicators(df):
    delta = df['close'].diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    n = 14  # 기간 설정

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
    rs = pd.Series(avg_gain_list, index=delta.index[n:]) / pd.Series(avg_loss_list, index=delta.index[n:])
    rsi = 100 - (100 / (1 + rs))

    # 볼린저 밴드 계산
    rolling_mean = df['close'].rolling(window=20).mean()
    rolling_std = df['close'].rolling(window=20).std()
    upper_band = rolling_mean + (rolling_std * 2)
    lower_band = rolling_mean - (rolling_std * 2)

    return rsi.iloc[-1], upper_band.iloc[-1], rolling_mean.iloc[-1], lower_band.iloc[-1]

def get_rsi(rsi):
    # 50 이상 rsi 반전
    if rsi >= 50:
        rsi = 100-rsi
    # rsi 정규화
    if rsi <= 20:
        return 20
    elif rsi <= 25:
        return 25
    elif rsi <= 30:
        return 30
    elif rsi <= 35:
        return 35
    else:
      return None

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
    rsi_check = []
    print(f"{COIN_TICKER} 자동투자 프로그램을 시작합니다.")
    asset_info = get_asset_info(upbit)
    send_asset_info(asset_info)
    if asset_info is None:
        print("초기 자산 정보 조회 실패. 프로그램을 종료합니다.")
        return

    while True:
        try:
            # 자산 데이터 조회
            asset_info = get_asset_info(upbit)
            if asset_info is None:
                send_slack_message("자산 정보 조회 실패, 10초 대기 후 다시 시도합니다...")
                time.sleep(10)
                continue
            
            # 가격 데이터 조회
            df = pyupbit.get_ohlcv(COIN_TICKER, interval="minute5", count=100)

            # 현재 가격 조회

            # 매매 신호 판단

            # 매수 진행

                # rsi 매매여부 체크(매수 시 추가)

            # 매도 진행

                # rsi 매매여부 체크(매도 시 삭제)
            

            # 10초간 대기
            time.sleep(10)


        except Exception as e:
            send_slack_message(f"메인 루프 에러: {str(e)}")
            time.sleep(10)

if __name__ == "__main__":
    main()