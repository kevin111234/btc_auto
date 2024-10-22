import os
import pyupbit
import numpy as np
import pandas as pd
import time

# 환경 변수에서 API 키를 가져오는 함수
def get_env_var(var_name):
    return os.getenv(var_name)

ACCESS_KEY = get_env_var('UPBIT_ACCESS_KEY')
SECRET_KEY = get_env_var('UPBIT_SECRET_KEY')
upbit = pyupbit.Upbit(ACCESS_KEY, SECRET_KEY)

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

    # 점수를 기반으로 매매 결정
    if score > 0.5:
        # 매수 카운트 속성을 사용하여 첫 매수와 두 번째 매수를 구분
        if not hasattr(make_trade_decision, 'buy_count'):
            make_trade_decision.buy_count = 0  # 첫 매수 이전에는 카운트를 0으로 설정
        if not hasattr(make_trade_decision, 'sell_count'):
            make_trade_decision.sell_count = 0  # 첫 매도 이전에는 카운트를 0으로 설정

        print("매수 신호")
        balances = get_balance()
        krw_balance = float(next(b['balance'] for b in balances if b['currency'] == 'KRW'))
        # 첫 매수는 잔액의 절반, 이후 매수는 전체 잔액으로 매수
        amount_to_buy = krw_balance / 2 if make_trade_decision.buy_count == 0 else krw_balance
        if make_trade_decision.buy_count == 0:
            make_trade_decision.buy_count = 1  # 첫 매수 후 카운트를 1로 설정
        else:
            make_trade_decision.buy_count += 1  # 이후 매수 시 카운트 증가
        if amount_to_buy > 5000:  # 최소 매수 금액 조건 (Upbit에서 5000원 이상 매수 필요)
            upbit.buy_market_order("KRW-BTC", amount_to_buy)
    elif score < -0.5:
        print("매도 신호")
        balances = get_balance()
        btc_balance = float(next(b['balance'] for b in balances if b['currency'] == 'BTC'))
        # 첫 매도는 자산의 절반, 이후 매도는 전체 자산으로 매도
        amount_to_sell = btc_balance / 2 if make_trade_decision.sell_count == 0 else btc_balance
        if make_trade_decision.sell_count == 0:
            make_trade_decision.sell_count = 1  # 첫 매도 후 카운트를 1로 설정
        else:
            make_trade_decision.sell_count += 1  # 이후 매도 시 카운트 증가
        if amount_to_sell > 0.00008:  # 최소 매도 수량 조건 (Upbit에서 최소 매도 수량 필요)
            upbit.sell_market_order("KRW-BTC", amount_to_sell)
    else:
        print("매매 신호 없음")

# 자산 조회 및 포지션 저장 함수
def get_balance():
    """
    현재 자산 정보를 조회하여 포지션을 저장합니다.
    """
    balances = upbit.get_balances()
    for balance in balances:
        print(f"자산: {balance['currency']}, 잔액: {balance['balance']}, 평단가: {balance['avg_buy_price']}")
    return balances

# 메인 실행 루프
def main():
    ticker = "KRW-BTC"
    print("1분 단위로 매매 시작")
    while True:
        df = get_data(ticker)
        get_balance()  # 자산 조회 및 포지션 저장
        make_trade_decision(df)
        # 매 결정 후 포지션 정보를 초기화하여 최신 데이터를 보장
        print("포지션 초기화 및 다음 반복 대기 중...")
        time.sleep(60)  # 1분마다 실행

if __name__ == "__main__":
    main()
