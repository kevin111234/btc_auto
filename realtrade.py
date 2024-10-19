import numpy as np
import pandas as pd
import pyupbit
import time
import os
import requests
from dotenv import load_dotenv

# .env 파일에서 API 키 불러오기
load_dotenv()
ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY")
SECRET_KEY = os.getenv("UPBIT_SECRET_KEY")
SLACK_API_TOKEN = os.getenv("SLACK_API_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")

# Upbit 객체 생성
upbit = pyupbit.Upbit(ACCESS_KEY, SECRET_KEY)

# Slack 메시지 전송 함수
def send_slack_message(message):
    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {SLACK_API_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "channel": SLACK_CHANNEL_ID,
        "text": message
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        print(f"슬랙 메시지 전송 실패: {response.status_code}, {response.text}")

# RSI 계산 함수
def compute_rsi(series, period):
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# 볼린저 밴드 계산 함수
def compute_bollinger_bands(series, period, num_std=2):
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper_band = sma + num_std * std
    lower_band = sma - num_std * std
    return upper_band, lower_band

# 매수 함수
def buy_crypto(current_price):
    balance = upbit.get_balance("KRW")  # 보유한 원화 잔고 확인
    if balance and balance > 6000:  # 최소 주문 금액 6000원 이상일 때만 매수
        upbit.buy_market_order("KRW-BTC", balance * 0.9995)  # 수수료 고려하여 매수
        time.sleep(10)  # 매수 후 잔고 업데이트를 위한 대기 시간 추가
        position_quantity = upbit.get_balance("BTC") or 0  # 매수 후 잔고 업데이트 확인
        avg_buy_price = upbit.get_avg_buy_price("BTC")  # 매수 후 평균 매수 금액 확인
        if position_quantity > 0:
            message = f"매수 실행: 가격 {current_price} KRW, 금액 {balance} KRW, 수량 {position_quantity} BTC"
        else:
            message = f"매수 실패: 가격 {current_price} KRW, 금액 {balance} KRW"
        print(message)
        send_slack_message(message)
        return position_quantity, avg_buy_price
    else: 
        message = f"매수 신호 감지되었으나 잔고 부족으로 매수하지 않음: 가격 {current_price} KRW, 금액 {balance} KRW"
        print(message)
        send_slack_message(message)
        return 0, 0

# 매도 함수
def sell_crypto(current_price, position_quantity):
    if position_quantity and position_quantity > 0:
        upbit.sell_market_order("KRW-BTC", position_quantity)
        time.sleep(10)  # 매도 후 잔고 업데이트를 위한 대기 시간 추가
        remaining_quantity = upbit.get_balance("BTC") or 0  # 매도 후 잔고 업데이트 확인
        if remaining_quantity < position_quantity:
            message = f"매도 실행: 가격 {current_price} KRW, 수량 {position_quantity} BTC"
        else:
            message = f"매도 실패: 가격 {current_price} KRW, 수량 {position_quantity} BTC"
        print(message)
        send_slack_message(message)

# 실시간 매매 알고리즘
def real_time_trading(symbol='KRW-BTC', interval='minute5', count=200):
    print("매매 시작")
    # 기존에 보유한 비트코인 포지션 확인 및 설정
    position_quantity = upbit.get_balance("BTC") or 0
    if position_quantity > 0:
        avg_buy_price = upbit.get_avg_buy_price("BTC")
        position = {
            'quantity': position_quantity,
            'price': avg_buy_price,
            'stop_price': avg_buy_price * (1 - 0.1),  # 손절 비율 적용
            'take_price': avg_buy_price * (1 + 0.05)  # 이익 실현 비율 적용
        }
    else:
        position = None
    print(f"포지션 정보: {position}")

    stop_loss = 0.1  # 손절 비율
    take_profit = 0.02  # 이익 실현 비율

    while True:
        try:
            # 최신 데이터 수집
            df = pyupbit.get_ohlcv(symbol, interval=interval, count=count)
            current_price = pyupbit.get_current_price(symbol)

            if df is None or current_price is None:
              error_message = f"데이터 수집 실패: df={df}, current_price={current_price}. API 호출 실패로 다음 루프로 재시도합니다."
              print(error_message)
              send_slack_message(error_message)
              time.sleep(10)
              continue

            # 지표 계산
            df['ema_short'] = df['close'].ewm(span=10, adjust=False).mean()
            df['ema_long'] = df['close'].ewm(span=20, adjust=False).mean()
            df['rsi'] = compute_rsi(df['close'], 14)
            df['bb_upper'], df['bb_lower'] = compute_bollinger_bands(df['close'], 10)

            # 가장 최신 데이터 행 가져오기
            latest = df.iloc[-1]

            # 매수 조건
            if (latest['ema_short'] > latest['ema_long']) and (latest['rsi'] < 30) and (current_price <= latest['bb_lower']):
                position_quantity, avg_buy_price = buy_crypto(current_price)
                message=f"기술적 지표에 따른 매수 실행: {current_price}"
                print(message)
                send_slack_message(message)
                position = None
                if position_quantity > 0:
                    position = {
                        'quantity': position_quantity,
                        'price': avg_buy_price,
                        'stop_price': avg_buy_price * (1 - stop_loss),
                        'take_price': avg_buy_price * (1 + take_profit)
                    }

            # 매도 조건
            elif position is not None:
                # 매도 조건: 이익 실현 또는 기술적 지표 반전
                if ((latest['ema_short'] < latest['ema_long']) and (latest['rsi'] > 70)):
                    sell_crypto(current_price, position['quantity'])
                    message=f"기술적 지표에 따른 매도 실행: {current_price}"
                    print(message)
                    send_slack_message(message)
                    position = None
                elif (current_price >= position['take_price']):
                    # 이익 실현 매도
                    sell_crypto(current_price, position['quantity'])
                    message=f"이익실현 매도 실행: {current_price}"
                    print(message)
                    send_slack_message(message)
                    position = None
                elif current_price <= position['stop_price'] or ((latest['ema_short'] < latest['ema_long']) and (latest['rsi'] > 70)):
                    # 손절 매도
                    sell_crypto(current_price, position['quantity'])
                    message=f"손절 매도 실행: {current_price}"
                    print(message)
                    send_slack_message(message)
                    position = None
                else:
                    print("매도 진행안함")
            else:
                print("매수 진행안함")
                time.sleep(10)

            # 5분 대기 (interval에 맞춰서 대기)
            time.sleep(140)

        except Exception as e:
            import traceback
            print(f"에러 발생: {e}, 라인 번호: {traceback.format_exc()}")
            send_slack_message(f"에러 발생: {e}, 라인 번호: {traceback.format_exc()}")
            time.sleep(60)

# 실시간 매매 시작
print("매매 준비")
balance = upbit.get_balance("KRW")
position_quantity = upbit.get_balance("BTC") or 0
avg_buy_price = upbit.get_avg_buy_price("BTC")
print(f"""
  시작잔고: {balance}
  비트코인: {position_quantity}
  평균단가: {avg_buy_price}
  """)
real_time_trading()