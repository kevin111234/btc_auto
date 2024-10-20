import numpy as np
import pandas as pd
import pyupbit
import time
import os
import requests
from dotenv import load_dotenv
from itertools import product

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
        time.sleep(10)
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

# 실시간 매매 알고리즘 (변경된 파라미터 적용 가능)
def real_time_trading(params):
    print("매매 시작")
    symbol = params.get('symbol', 'KRW-BTC')
    interval = params.get('interval', 'minute5')
    count = params.get('count', 200)
    ema_short = params.get('ema_short', 10)
    ema_long = params.get('ema_long', 20)
    rsi_period = params.get('rsi_period', 14)
    bb_period = params.get('bb_period', 10)
    stop_loss = params.get('stop_loss', 0.1)
    take_profit = params.get('take_profit', 0.05)
    weights = params.get('weights', {'ema': 1, 'rsi': 1, 'bollinger': 1})

    # 기존에 보유한 비트코인 포지션 확인 및 설정
    position_quantity = upbit.get_balance("BTC") or 0
    if position_quantity > 0:
        avg_buy_price = upbit.get_avg_buy_price("BTC")
        position = {
            'quantity': position_quantity,
            'price': avg_buy_price,
            'stop_price': avg_buy_price * (1 - stop_loss),
            'take_price': avg_buy_price * (1 + take_profit)
        }
    else:
        position = None
    print(f"포지션 정보: {position}")

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
            df['ema_short'] = df['close'].ewm(span=ema_short, adjust=False).mean()
            df['ema_long'] = df['close'].ewm(span=ema_long, adjust=False).mean()
            df['rsi'] = compute_rsi(df['close'], rsi_period)
            df['bb_upper'], df['bb_lower'] = compute_bollinger_bands(df['close'], bb_period)

            # 가장 최신 데이터 행 가져오기
            latest = df.iloc[-1]

            # 매수 점수 계산
            buy_score = 0
            if latest['ema_short'] > latest['ema_long']:
                buy_score += weights['ema']
            if latest['rsi'] < 30:
                buy_score += weights['rsi']
            if current_price <= latest['bb_lower']:
                buy_score += weights['bollinger']
            print(f"buy_score = {buy_score}")

            # 매도 점수 계산
            sell_score = 0
            if latest['ema_short'] < latest['ema_long']:
                sell_score += weights['ema']
            if latest['rsi'] > 70:
                sell_score += weights['rsi']
            if current_price >= latest['bb_upper']:
                sell_score += weights['bollinger']
            print(f"sell_score = {sell_score}")

            # 매수 조건
            if buy_score >= sum(weights.values()) * 0.6 and position is None:
                position_quantity, avg_buy_price = buy_crypto(current_price)
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
                if sell_score >= sum(weights.values()) * 0.6:
                  sell_crypto(current_price, position['quantity'])
                  position = None
                else:
                    print("매도 진행안함")
                    time.sleep(10)
            else:
                print("매수 진행안함")
                time.sleep(10)

            # 대기 시간 설정 (interval에 맞춰서 대기)
            time.sleep(140)

        except Exception as e:
            import traceback
            print(f"에러 발생: {e}, 라인 번호: {traceback.format_exc()}")
            send_slack_message(f"에러 발생: {e}, 라인 번호: {traceback.format_exc()}")
            time.sleep(60)

# 실시간 매매 시작 (사용자가 원하는 파라미터 설정 가능)
params = {
    'symbol': 'KRW-BTC',
    'interval': 'minute5',
    'count': 200,
    'ema_short': 10,
    'ema_long': 20,
    'rsi_period': 14,
    'bb_period': 20,
    'stop_loss': 0.1,
    'take_profit': 0.02,
    'weights': {'ema': 1, 'rsi': 1, 'bollinger': 1.5}
}
print("매매 준비")
balance = upbit.get_balance("KRW")
position_quantity = upbit.get_balance("BTC") or 0
avg_buy_price = upbit.get_avg_buy_price("BTC")

print(f"""
  시작잔고: {balance}
  비트코인: {position_quantity}
  평균단가: {avg_buy_price}
  """)
print(f"""현재 설정값 안내
    symbol = {params.get('symbol')}
    interval = {params.get('interval')}
    count = {params.get('count')}
    ema_short = {params.get('ema_short')}
    ema_long = {params.get('ema_long')}
    rsi_period = {params.get('rsi_period')}
    bb_period = {params.get('bb_period')}
    stop_loss = {params.get('stop_loss')}
    take_profit = {params.get('take_profit')}
    weights = {params.get('weights')}""")
real_time_trading(params)
