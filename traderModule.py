import os
import time
import pandas as pd
import numpy as np
import pandas_ta as ta
import pyupbit
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()
UPBIT_ACCESS_KEY = os.getenv('UPBIT_ACCESS_KEY')
UPBIT_SECRET_KEY = os.getenv('UPBIT_SECRET_KEY')
SLACK_API_TOKEN = os.getenv('SLACK_API_TOKEN')
SLACK_CHANNEL_ID = os.getenv('SLACK_CHANNEL_ID')

# 업비트와 슬랙 클라이언트 초기화
upbit = pyupbit.Upbit(UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY)
slack_client = WebClient(token=SLACK_API_TOKEN)

# 거래 심볼 및 타임프레임 설정
symbol = "KRW-BTC"
timeframe = "minute1"  # 1분봉
higher_timeframe = "minute15"  # 15분봉 또는 "minute60"으로 변경 가능

# 포지션 관리 변수 초기화
position = None  # "long" 또는 "short"
entry_price = 0
stop_loss = 0
take_profit = 0
trade_count = 0  # 매매 횟수

def post_message(text):
    try:
        slack_client.chat_postMessage(channel=SLACK_CHANNEL_ID, text=text)
    except SlackApiError as e:
        print(f"슬랙 메시지 전송 실패: {e.response['error']}")

def get_macd(df):
    macd = ta.macd(df['close'])
    return macd

def get_rsi(df):
    rsi = ta.rsi(df['close'], length=14)
    return rsi

def get_bollinger_bands(df):
    bb = ta.bbands(df['close'], length=20)
    return bb

def get_percent_b(df):
    bb = get_bollinger_bands(df)
    percent_b = (df['close'] - bb['BBL_20_2.0']) / (bb['BBU_20_2.0'] - bb['BBL_20_2.0'])
    return percent_b

def get_atr(df):
    atr = ta.atr(df['high'], df['low'], df['close'], length=14)
    return atr

def calculate_obv(df):
    obv = ta.obv(df['close'], df['volume'])
    return obv

def get_volume_score(current_volume, avg_volume):
    if current_volume < avg_volume:
        return 0
    elif current_volume == avg_volume:
        return 1
    else:
        return 2

def get_obv_score(obv):
    if obv.diff().iloc[-1] > 0:
        return 2
    elif obv.diff().iloc[-1] == 0:
        return 1
    else:
        return 0

def get_position_size(total_balance, score):
    return total_balance * (score * 0.25)

def get_total_balance():
    balances = upbit.get_balances()
    krw_balance = float([x for x in balances if x['currency'] == 'KRW'][0]['balance'])
    btc_balance = 0
    for x in balances:
        if x['currency'] == 'BTC':
            btc_balance = float(x['balance'])
            break
    btc_price = pyupbit.get_current_price("KRW-BTC")
    total_balance = krw_balance + btc_balance * btc_price
    return total_balance, krw_balance, btc_balance

def place_buy_order(price, amount):
    return upbit.buy_limit_order(symbol, price, amount)

def place_sell_order(price, amount):
    return upbit.sell_limit_order(symbol, price, amount)

def cancel_order(uuid):
    return upbit.cancel_order(uuid)

def get_current_price():
    return pyupbit.get_current_price(symbol)

def main():
    global position, entry_price, stop_loss, take_profit, trade_count

    while True:
        try:
            # 1. 자산 확인 및 포지션 정보 출력
            total_balance, krw_balance, btc_balance = get_total_balance()
            print(f"총 자산: {total_balance} KRW, 현금: {krw_balance} KRW, 보유 BTC: {btc_balance} BTC")
            post_message(f"총 자산: {total_balance} KRW, 현금: {krw_balance} KRW, 보유 BTC: {btc_balance} BTC")

            # 2. 데이터 수집
            df = pyupbit.get_ohlcv(symbol, interval=timeframe, count=100)
            higher_df = pyupbit.get_ohlcv(symbol, interval=higher_timeframe, count=100)

            # 3. 지표 계산
            macd = get_macd(higher_df)
            rsi = get_rsi(df)
            bb = get_bollinger_bands(df)
            percent_b = get_percent_b(df)
            atr = get_atr(df)
            obv = calculate_obv(df)
            avg_volume = df['volume'].rolling(window=20).mean().iloc[-1]
            current_volume = df['volume'].iloc[-1]

            # 4. 추세 판단
            current_macd = macd['MACD_12_26_9'].iloc[-1]
            current_macd_signal = macd['MACDs_12_26_9'].iloc[-1]
            current_hist = macd['MACDh_12_26_9'].iloc[-1]

            if current_macd > current_macd_signal and current_macd > 0 and current_hist > 0:
                trend = "up"
            elif current_macd < current_macd_signal and current_macd < 0 and current_hist < 0:
                trend = "down"
            else:
                trend = "sideways"

            # 5. 매매 조건 판단
            last_price = df['close'].iloc[-1]
            prev_rsi = rsi.iloc[-2]
            current_rsi = rsi.iloc[-1]
            prev_percent_b = percent_b.iloc[-2]
            current_percent_b = percent_b.iloc[-1]

            volume_score = get_volume_score(current_volume, avg_volume)
            obv_score = get_obv_score(obv)
            total_score = volume_score + obv_score

            # 매수 조건
            buy_cond = (
                trend == "up" and
                prev_rsi <= 30 and current_rsi > 30 and
                last_price <= bb['BBL_20_2.0'].iloc[-1] and
                prev_percent_b <= 0 and current_percent_b > 0
            )

            # 매도 조건
            sell_cond = (
                trend == "down" and
                prev_rsi >= 70 and current_rsi < 70 and
                last_price >= bb['BBU_20_2.0'].iloc[-1] and
                prev_percent_b >= 1 and current_percent_b < 1
            )

            # 6. 포지션 크기 결정
            total_balance, krw_balance, btc_balance = get_total_balance()
            if trade_count % 2 == 0:
                position_size = get_position_size(total_balance, total_score)
            else:
                position_size = get_position_size(total_balance, total_score) / 2

            # 7. 매매 실행
            if buy_cond and position is None and krw_balance > 5000:
                # 매수 주문
                price = last_price * 1.005  # 희망가격의 1.005배
                amount = position_size / price
                order = place_buy_order(price, amount)
                time.sleep(10)
                # 주문 체결 확인
                order_result = upbit.get_order(order['uuid'])
                if order_result['state'] == 'done':
                    position = "long"
                    entry_price = float(order_result['price'])
                    stop_loss = entry_price - atr.iloc[-1]
                    take_profit = entry_price + (entry_price - stop_loss) * 2
                    trade_count += 1
                    post_message(f"매수 주문 체결: 가격 {entry_price}, 수량 {amount}")
                else:
                    cancel_order(order['uuid'])
                    post_message("매수 주문 미체결로 취소되었습니다.")

            elif sell_cond and position == "long":
                # 매도 주문
                amount = btc_balance
                order = upbit.sell_market_order(symbol, amount)
                time.sleep(10)
                position = None
                entry_price = 0
                stop_loss = 0
                take_profit = 0
                trade_count += 1
                post_message(f"매도 주문 체결: 가격 {last_price}, 수량 {amount}")

            else:
                post_message("홀드 상태입니다.")
                time.sleep(10)

            time.sleep(20)

        except Exception as e:
            print(f"에러 발생: {e}")
            post_message(f"에러 발생: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
