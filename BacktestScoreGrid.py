import os
import pyupbit
import numpy as np
import pandas as pd
import time
import requests
from dotenv import load_dotenv

load_dotenv()
ACCESS_KEY = os.getenv('UPBIT_ACCESS_KEY')
SECRET_KEY = os.getenv('UPBIT_SECRET_KEY')
SLACK_API_TOKEN = os.getenv("SLACK_API_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")
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

# 주어진 티커와 간격으로 OHLCV 데이터를 가져오는 함수
def get_data(ticker, interval='minute1', count=100):
    """
    주어진 티커와 간격에 대한 OHLCV 데이터를 가져옵니다 (기본적으로 100개의 데이터).
    """
    data = pyupbit.get_ohlcv(ticker, interval=interval, count=count)
    return data

# 볼린저 밴드를 계산하는 함수
def calculate_bollinger_bands(df, window=20, num_std=2):
    """
    주어진 데이터프레임에 대한 볼린저 밴드를 계산합니다.
    """
    rolling_mean = df['close'].rolling(window=window).mean()
    rolling_std = df['close'].rolling(window=window).std()
    upper_band = rolling_mean + (rolling_std * num_std)
    lower_band = rolling_mean - (rolling_std * num_std)
    return rolling_mean, upper_band, lower_band

# RSI를 계산하는 함수
def calculate_rsi(df, window=14):
    """
    주어진 데이터프레임에 대한 RSI (상대 강도 지수)를 계산합니다.
    """
    delta = df['close'].diff(1)
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = pd.Series(gain).rolling(window=window).mean()
    avg_loss = pd.Series(loss).rolling(window=window).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# CCI를 계산하는 함수
def calculate_cci(df, window=20):
    """
    주어진 데이터프레임에 대한 CCI (상품 채널 지수)를 계산합니다.
    """
    tp = (df['high'] + df['low'] + df['close']) / 3
    rolling_mean = tp.rolling(window=window).mean()
    rolling_std = tp.rolling(window=window).std()
    cci = (tp - rolling_mean) / (0.015 * rolling_std)
    return cci

# 스토캐스틱 오실레이터를 계산하는 함수
def calculate_stochastic_oscillator(df, k_window=14, d_window=3):
    """
    주어진 데이터프레임에 대한 스토캐스틱 오실레이터 (%K와 %D)를 계산합니다.
    """
    lowest_low = df['low'].rolling(window=k_window).min()
    highest_high = df['high'].rolling(window=k_window).max()
    k_percent = 100 * ((df['close'] - lowest_low) / (highest_high - lowest_low))
    d_percent = k_percent.rolling(window=d_window).mean()
    return k_percent, d_percent

# 가중치를 기반으로 매매 결정을 내리는 함수
def make_trade_decision(df, bollinger_weight=0.25, rsi_weight=0.25, cci_weight=0.25, stochastic_weight=0.25):
    """
    가중치를 기반으로 기술적 지표들을 사용해 매수 또는 매도 결정을 내립니다.
    """
    # 지표 계산
    rolling_mean, upper_band, lower_band = calculate_bollinger_bands(df)
    rsi = calculate_rsi(df)
    cci = calculate_cci(df)
    k_percent, _ = calculate_stochastic_oscillator(df)
    latest_close = df['close'].iloc[-1]
    score = 0

    # 볼린저 밴드 점수
    if latest_close < lower_band.iloc[-1]:
        score += bollinger_weight  # 하한선 터치 시 매수 신호
    elif latest_close > upper_band.iloc[-1]:
        score -= bollinger_weight  # 상한선 터치 시 매도 신호
    elif latest_close > rolling_mean.iloc[-1] and df['close'].iloc[-2] <= rolling_mean.iloc[-2]:
        score += bollinger_weight  # 중심선 돌파 시 매수 신호
    elif latest_close < rolling_mean.iloc[-1] and df['close'].iloc[-2] >= rolling_mean.iloc[-2]:
        score -= bollinger_weight  # 중심선 하향 돌파 시 매도 신호

    # RSI 점수
    if rsi.iloc[-1] < 30:
        score += rsi_weight  # 과매도 상태
    elif rsi.iloc[-1] > 70:
        score -= rsi_weight  # 과매수 상태

    # CCI 점수
    if cci.iloc[-1] < -100:
        score += cci_weight  # 과매도 상태
    elif cci.iloc[-1] > 100:
        score -= cci_weight  # 과매수 상태

    # 스토캐스틱 오실레이터 점수
    if k_percent.iloc[-1] < 20:
        score += stochastic_weight  # 과매도 상태
    elif k_percent.iloc[-1] > 80:
        score -= stochastic_weight  # 과매수 상태

    return score

# 백테스팅 함수
def backtest(data, initial_balance=1000000):
    """
    주어진 데이터를 이용하여 전략을 백테스팅합니다.
    """
    balance = initial_balance
    btc_balance = 0
    buy_count = 0
    sell_count = 0
    trades = []
    max_balance = initial_balance

    for i in range(len(data) - 1):
        df = data.iloc[:i + 1]
        score = make_trade_decision(df)

        # 매수 로직
        if score > 0.5:
            amount_to_buy = balance / 2 if buy_count == 0 else balance
            if amount_to_buy > 5000:  # 최소 매수 금액 조건
                btc_balance += amount_to_buy / df['close'].iloc[-1]
                balance -= amount_to_buy
                buy_count += 1
                trades.append(("buy", df['close'].iloc[-1]))
                print(f"매수: {amount_to_buy}원, BTC 잔액: {btc_balance}, 남은 현금: {balance}")

        # 매도 로직
        elif score < -0.5:
            amount_to_sell = btc_balance / 2 if sell_count == 0 else btc_balance
            if amount_to_sell > 0:
                balance += amount_to_sell * df['close'].iloc[-1]
                btc_balance -= amount_to_sell
                sell_count += 1
                trades.append(("sell", df['close'].iloc[-1]))
                print(f"매도: {amount_to_sell} BTC, BTC 잔액: {btc_balance}, 남은 현금: {balance}")

        # 최대 자산 갱신
        current_balance = balance + (btc_balance * df['close'].iloc[-1])
        if current_balance > max_balance:
            max_balance = current_balance

    # 최종 자산 평가
    final_balance = balance + (btc_balance * data['close'].iloc[-1])
    profit = final_balance - initial_balance
    returns = (profit / initial_balance) * 100

    # MDD (Maximum Drawdown) 계산
    mdd = 0
    peak = initial_balance
    for _, price in trades:
        current_value = balance + (btc_balance * price)
        if current_value > peak:
            peak = current_value
        drawdown = (peak - current_value) / peak * 100
        if drawdown > mdd:
            mdd = drawdown

    # 승률 계산
    wins = 0
    total_trades = 0
    for j in range(1, len(trades)):
        if trades[j - 1][0] == "buy" and trades[j][0] == "sell":
            total_trades += 1
            if trades[j][1] > trades[j - 1][1]:
                wins += 1
    win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0

    # 결과 출력
    print(f"최종 자산: {final_balance}원")
    print(f"수익률: {returns:.2f}%")
    print(f"MDD: {mdd:.2f}%")
    print(f"승률: {win_rate:.2f}%")

# 자산 조회 및 포지션 저장 함수
def get_balance():
    """
    현재 자산 정보를 조회하여 포지션을 저장합니다.
    """
    balances = upbit.get_balances()
    for balance in balances:
        print(f"자산: {balance['currency']}, 잔액: {balance['balance']}, 평단가: {balance['avg_buy_price']}")
    return balances

if __name__ == "__main__":
    # 백테스팅 실행
    historical_data = get_data("KRW-BTC", interval='minute1', count=200000)
    backtest(historical_data)