import numpy as np
import pandas as pd
import pyupbit
import time
import os
import requests
from dotenv import load_dotenv

# 환경변수 불러오기
load_dotenv()
ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY")
SECRET_KEY = os.getenv("UPBIT_SECRET_KEY")
SLACK_API_TOKEN = os.getenv("SLACK_API_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")

# Upbit api 객체 생성
upbit = pyupbit.Upbit(ACCESS_KEY, SECRET_KEY)

# Slack message 전송 함수
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

# 지표계산 함수
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

# 볼린저 범드 계산 함수
def compute_bollinger_bands(series, period, num_std=2):
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper_band = sma + num_std * std
    lower_band = sma - num_std * std
    return upper_band, lower_band

# 데이터 수집 및 지표 종합 함수
def data_collection(symbol, interval, count):
    retry_count = 10  # 최대 재시도 횟수
    for attempt in range(retry_count):
        df = pyupbit.get_ohlcv(symbol, interval=interval, count=count)
        current_price = pyupbit.get_current_price(symbol)

        if df is not None and current_price is not None:
            break
        else:
            error_message = f"데이터 수집 실패 (시도 {attempt + 1}/{retry_count}): df={df}, current_price={current_price}. API 호출 실패로 다음 루프로 재시도합니다."
            print(error_message)
            send_slack_message(error_message)
            time.sleep(1)
    else:
        raise Exception("데이터 수집 실패: 최대 재시도 횟수를 초과했습니다.")

    # 지표 계산
    df['ema_short'] = df['close'].ewm(span=10, adjust=False).mean()
    df['ema_long'] = df['close'].ewm(span=20, adjust=False).mean()
    df['rsi'] = compute_rsi(df['close'], 14)
    df['bb_upper'], df['bb_lower'] = compute_bollinger_bands(df['close'], 10)

    return df

# 매수 함수
def buy_crypto(current_price):
    balance = upbit.get_balance("KRW")  # 보유한 원화 잔고 확인
    target_price = current_price * 1.005  # 현재 가격보다 약간 높은 가격에 매수 시도
    if balance and balance > 6000:  # 최소 주문 금액 6000원 이상일 때만 매수
        # 지정가 매수 실행 및 주문 ID 저장
        order = upbit.buy_limit_order("KRW-BTC", target_price, balance * 0.9995 / target_price)
        order_uuid = order.get('uuid')  # 주문 ID 추출
        time_elapsed = 0
        time_interval = 1  # 1초마다 확인
        max_wait_time = 10  # 최대 대기 시간 10초

        # 주문 체결 여부 확인 루프
        while time_elapsed < max_wait_time:
            order_detail = upbit.get_order(order_uuid)
            if order_detail['state'] == 'done':
                # 주문 체결 완료
                position_quantity = upbit.get_balance("BTC") or 0
                avg_buy_price = upbit.get_avg_buy_price("BTC")
                message = f"매수 실행: 목표 가격 {target_price} KRW, 금액 {balance} KRW, 수량 {position_quantity} BTC"
                print(message)
                send_slack_message(message)
                return position_quantity, avg_buy_price
            elif order_detail['state'] == 'cancel':
                # 주문이 취소됨
                break
            time.sleep(time_interval)
            time_elapsed += time_interval

        # 주문 미체결 시 주문 취소
        upbit.cancel_order(order_uuid)
        message = f"매수 실패: {max_wait_time}초 내에 주문이 체결되지 않아 주문을 취소했습니다."
        print(message)
        send_slack_message(message)
        return 0, 0
    
    else: 
        message = f"매수 신호 검지되었으나 잔고 부족으로 매수하지 않음: 가격 {current_price} KRW, 금액 {balance} KRW"
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
            print(message)
            send_slack_message(message)
            return 1
        else:
            message = f"매도 실패: 가격 {current_price} KRW, 수량 {position_quantity} BTC"
            print(message)
            send_slack_message(message)
            return 0

# 실시간 트레이딩 함수
def real_time_trading(symbol='KRW-BTC', interval='minute1', count=100):
    print("매매 시작")
    stop_loss = 0.1  # 손절 비율
    take_profit = 0.02  # 이익 실현 비율
    # 기존에 보유한 비트코인 포지션 확인 및 설정
    position_quantity = upbit.get_balance("BTC") or 0
    if position_quantity > 0:
        avg_buy_price = upbit.get_avg_buy_price("BTC")
        position = {
            'quantity': position_quantity,
            'price': avg_buy_price,
            'stop_price': avg_buy_price * (1 - stop_loss),  # 손절 비율 적용
            'take_price': avg_buy_price * (1 + take_profit)  # 이익 실현 비율 적용
        }
    else:
        position = None
    print(f"포지션 정보: {position}")

    while True:
        try:
            print("자동 매수 시작")
            # 데이터 수집
            current_price = pyupbit.get_current_price(symbol)
            df = data_collection(symbol, interval, count)
            # 최신 데이터 행 가져오기
            latest = df.iloc[-1]
            # 매수 조건
            if (latest['rsi'] <= 30) and (current_price <= latest['bb_lower']):
                position_quantity, avg_buy_price = buy_crypto(current_price)
                position = None
                if position_quantity > 0:
                    position = {
                        'quantity': position_quantity,
                        'price': avg_buy_price,
                        'stop_price': avg_buy_price * (1 - stop_loss),
                        'take_price': avg_buy_price * (1 + take_profit)
                    }
                    print(position)

            # 매도 조건
            elif position is not None:
                # 기술적 지표 반전 매도
                if ((latest['rsi'] > 70) and (current_price >= latest['bb_upper'])) and current_price > position['price'] * 1.01:
                    if sell_crypto(current_price, position['quantity']) == 1:
                        message = f"기술적 지표에 따른 매도 실행: {current_price}"
                        print(message)
                        send_slack_message(message)
                        position = None
                        position_quantity = upbit.get_balance("BTC")  # 잔고 최신화
                elif current_price >= position['take_price']:
                    # 이익 실현 매도
                    if sell_crypto(current_price, position['quantity']) == 1:
                        message = f"이익실현 매도 실행: {current_price}"
                        print(message)
                        send_slack_message(message)
                        position = None
                        position_quantity = upbit.get_balance("BTC")
                elif current_price <= position['stop_price']:
                    # 손절 매도
                    if sell_crypto(current_price, position['quantity']) == 1:
                        message = f"손절 매도 실행: {current_price}"
                        print(message)
                        send_slack_message(message)
                        position = None
                        position_quantity = upbit.get_balance("BTC")
                else:
                    print("홀드")
            else:
                print("매수 진행안함")

            # interval에 맞이서 대기
            time.sleep(20)

        except Exception as e:
            import traceback
            print(f"에러 발생: {e}, 라인 번호: {traceback.format_exc()}")
            send_slack_message(f"에러 발생: {e}, 라인 번호: {traceback.format_exc()}")
            time.sleep(20)

# 실시간 매매 시작
if __name__ == "__main__":
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
