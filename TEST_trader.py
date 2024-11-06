import os
import time
import pandas as pd
import numpy as np
import pyupbit
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import ta  # 기술적 지표를 계산하기 위한 라이브러리

# 1. 환경변수 설정
UPBIT_ACCESS_KEY = os.environ.get('UPBIT_ACCESS_KEY')
UPBIT_SECRET_KEY = os.environ.get('UPBIT_SECRET_KEY')
SLACK_API_TOKEN = os.environ.get('SLACK_API_TOKEN')
SLACK_CHANNEL_ID = os.environ.get('SLACK_CHANNEL_ID')
COIN_TICKER = os.environ.get('COIN_TICKER')

# 환경변수 유효성 검사
if not all([UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY, SLACK_API_TOKEN, SLACK_CHANNEL_ID, COIN_TICKER]):
    raise EnvironmentError("환경변수가 올바르게 설정되지 않았습니다.")

# Upbit 클라이언트 초기화
upbit = pyupbit.Upbit(UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY)

# Slack 클라이언트 초기화
slack_client = WebClient(token=SLACK_API_TOKEN)

# 포지션 관련 변수 초기화
position = None  # 현재 포지션 상태 ('LONG' 또는 None)
entry_price = 0  # 진입 가격
stop_loss = 0    # 손절매 가격
take_profit = 0  # 이익 실현 가격
position_size = 0  # 포지션 크기
average_buy_price = 0  # 평균 구매가

# 추가된 매도 조건 설정 (평균 구매가 대비 최소 이익률)
MIN_PROFIT_PERCENT = 0.01  # 1% 이상의 이익이어야 매도

def log_to_slack(message):
    """Slack 채널에 메시지 전송."""
    try:
        slack_client.chat_postMessage(channel=SLACK_CHANNEL_ID, text=message)
    except SlackApiError as e:
        print(f"Slack API 에러: {e.response['error']}")

def get_recent_data(ticker, interval='minute1', count=200):
    """최근 시장 데이터를 가져옵니다."""
    df = pyupbit.get_ohlcv(ticker, interval=interval, count=count)
    if df is None:
        # 데이터가 없을 경우 예외 발생
        raise ValueError(f"데이터를 가져올 수 없습니다. 티커를 확인하세요: {ticker}")
    return df

def calculate_indicators(df):
    """기술적 지표를 계산합니다."""
    if df is None or df.empty:
        raise ValueError("데이터프레임이 비어있거나 None입니다. 데이터를 가져오는 데 문제가 발생했습니다.")
    df = df.copy()
    # RSI 계산
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    # 볼린저 밴드 계산
    bb_indicator = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
    df['bb_middle'] = bb_indicator.bollinger_mavg()   # 중간선
    df['bb_upper'] = bb_indicator.bollinger_hband()   # 상단 밴드
    df['bb_lower'] = bb_indicator.bollinger_lband()   # 하단 밴드
    df['percent_b'] = bb_indicator.bollinger_pband()  # %B 지표
    df['bb_width'] = bb_indicator.bollinger_wband()   # 볼린저 밴드 폭 (BBW)
    # BBW 이동평균 계산
    df['bb_width_ma'] = df['bb_width'].rolling(window=20).mean()
    # OBV 계산
    df['obv'] = ta.volume.OnBalanceVolumeIndicator(df['close'], df['volume']).on_balance_volume()
    # ATR 계산
    df['atr'] = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close'], window=14).average_true_range()
    return df

def check_core_conditions(df):
    """핵심 매수/매도 조건을 확인합니다."""
    last = df.iloc[-1]  # 가장 최근 데이터
    prev = df.iloc[-2]  # 이전 데이터

    # 매수 조건 확인
    buy = (
        prev['rsi'] <= 30 and last['rsi'] > prev['rsi'] and  # RSI가 30 이하에서 상승 반전
        prev['close'] <= prev['bb_lower'] and last['close'] > prev['close'] # 가격이 볼린저 밴드 하단을 터치 또는 하향 돌파 후 반등
    )

    # 매도 조건 확인
    sell = (
        prev['rsi'] >= 70 and last['rsi'] < prev['rsi'] and  # RSI가 70 이상에서 하락 반전
        prev['close'] >= prev['bb_upper'] and last['close'] < prev['close'] # 가격이 볼린저 밴드 상단을 터치 또는 상향 돌파 후 하락
    )

    return buy, sell

def score_auxiliary_indicators(df):
    """보조 지표를 스코어링합니다."""
    last = df.iloc[-1]
    total_score = 0

    # 거래량 스코어링
    avg_volume = df['volume'].rolling(window=20).mean().iloc[-1]  # 20기간 평균 거래량
    volume_score = 0
    if last['volume'] < avg_volume:
        volume_score = 0  # 평균 거래량보다 낮음
    elif avg_volume <= last['volume'] <= 1.2 * avg_volume:
        volume_score = 1  # 평균 거래량과 비슷
    else:
        volume_score = 2  # 평균 거래량보다 높음
    total_score += volume_score

    # OBV 스코어링
    obv_change = df['obv'].diff().iloc[-1]  # OBV 변화량
    avg_obv_change = df['obv'].diff().abs().rolling(window=20).mean().iloc[-1]  # OBV 변화의 평균
    obv_score = 0
    if obv_change <= 0:
        obv_score = 0  # 추세 변화 없음 또는 불리한 방향
    elif 0 < obv_change <= avg_obv_change:
        obv_score = 1  # 약간의 추세 변화
    else:
        obv_score = 2  # 유리한 방향으로 강한 추세 변화
    total_score += obv_score

    # BBW 스코어링
    bbw_level = last['bb_width'] / last['bb_width_ma']  # BBW 수준 평가
    bbw_score = 0
    if bbw_level < 0.8:
        bbw_score = 0  # 변동성 낮음
    elif 0.8 <= bbw_level <= 1.2:
        bbw_score = 1  # 변동성 보통
    else:
        bbw_score = 2  # 변동성 높음
    total_score += bbw_score

    return total_score  # 총합 스코어 반환

def determine_position_size(total_score, total_assets):
    """총 스코어에 따라 포지션 크기를 결정합니다."""
    max_score = 6  # 최대 스코어
    if total_score <= 1:
        return 0  # 포지션 진입 보류 또는 최소 크기로 진입
    elif 2 <= total_score <= 3:
        return (total_score / max_score) * 0.5 * total_assets  # 전체 자산의 (총 스코어 / 6) × 50%
    else:
        return (total_score / max_score) * total_assets  # 전체 자산의 (총 스코어 / 6) × 100%

def set_stop_loss_take_profit(entry_price, atr, bbw_level):
    """손절매와 이익 실현 지점을 설정합니다."""
    # 변동성에 따라 손절매와 이익 실현 지점 계산
    if bbw_level > 1.2:
        sl_distance = atr * 1.5  # 변동성 높음
        tp_distance = atr * 3
    elif bbw_level < 0.8:
        sl_distance = atr * 0.75  # 변동성 낮음
        tp_distance = atr * 1.5
    else:
        sl_distance = atr  # 변동성 보통
        tp_distance = atr * 2

    # 최소 및 최대 손절매 거리 설정 (진입 가격의 5% ~ 15%)
    min_sl_distance = entry_price * 0.05  # 최소 손절매 거리 (5%)
    max_sl_distance = entry_price * 0.15  # 최대 손절매 거리 (15%)

    # 실제 손절매 거리를 최소/최대로 제한
    sl_distance = max(min_sl_distance, min(sl_distance, max_sl_distance))

    # 손절매 가격 계산
    stop_loss = entry_price - sl_distance

    # 최소 및 최대 이익 실현 거리 설정 (진입 가격의 5% ~ 15%)
    min_tp_distance = entry_price * 0.05  # 최소 이익 실현 거리 (5%)
    max_tp_distance = entry_price * 0.15  # 최대 이익 실현 거리 (15%)

    # 실제 이익 실현 거리를 최소/최대로 제한
    tp_distance = max(min_tp_distance, min(tp_distance, max_tp_distance))

    # 이익 실현 가격 계산
    take_profit = entry_price + tp_distance

    return stop_loss, take_profit

def check_existing_position():
    """현재 자산과 포지션 정보를 조회합니다."""
    coin_balance = upbit.get_balance(COIN_TICKER)  # 해당 코인 보유 수량 조회
    if coin_balance > 0:
        position = 'LONG'  # 현재 포지션은 매수 상태
        position_size = coin_balance
        entry_price = upbit.get_avg_buy_price(COIN_TICKER)  # 평균 매수가를 가져옴
        average_buy_price = entry_price  # 평균 구매가 저장
        # 초기 손절매와 이익 실현 가격 설정
        df_initial = get_recent_data(COIN_TICKER)
        df_initial = calculate_indicators(df_initial)
        bbw_level_initial = df_initial['bb_width'].iloc[-1] / df_initial['bb_width_ma'].iloc[-1]
        atr_initial = df_initial['atr'].iloc[-1]
        stop_loss, take_profit = set_stop_loss_take_profit(entry_price, atr_initial, bbw_level_initial)
        log_to_slack(f"기존 포지션 발견: 진입 가격={entry_price}, 손절매={stop_loss}, 이익 실현={take_profit}")
    else:
        log_to_slack("현재 포지션이 없습니다.")
        position = None  # 포지션 없음
        position_size = 0
        entry_price = 0
        average_buy_price = 0
        stop_loss = 0
        take_profit = 0
    return position, position_size, entry_price, average_buy_price, stop_loss, take_profit

# A. 기존 자산 확인 (함수 호출로 대체)
try:
    position, position_size, entry_price, average_buy_price, stop_loss, take_profit = check_existing_position()
except Exception as e:
    log_to_slack(f"초기화 중 에러 발생: {e}")
    raise e

# B. 반복문 시작
while True:
    try:
        # B. 데이터 수집
        df = get_recent_data(COIN_TICKER)
        df = calculate_indicators(df)
        current_price = df['close'].iloc[-1]  # 현재 가격

        # C. 매수/매도 조건 판단
        buy_signal, sell_signal = check_core_conditions(df)

        if position == 'LONG':
            # 손절매와 이익 실현 가격 모니터링
            if current_price <= stop_loss:
                # G. 손절매 실행
                amount = upbit.get_balance(COIN_TICKER)
                upbit.sell_market_order(COIN_TICKER, amount)
                log_to_slack(f"손절매 발동. {COIN_TICKER} {amount}개를 {current_price}원에 매도했습니다.")
                position = None  # 포지션 종료
            elif current_price >= take_profit:
                # G. 이익 실현 실행
                amount = upbit.get_balance(COIN_TICKER)
                upbit.sell_market_order(COIN_TICKER, amount)
                log_to_slack(f"이익 실현 지점 도달. {COIN_TICKER} {amount}개를 {current_price}원에 매도했습니다.")
                position = None
            elif sell_signal and (current_price >= average_buy_price * (1 + MIN_PROFIT_PERCENT)):
                # G. 매도 신호 발생 및 평균 구매가 대비 일정 % 이상 상승한 경우 매도
                amount = upbit.get_balance(COIN_TICKER)
                upbit.sell_market_order(COIN_TICKER, amount)
                profit_percent = ((current_price - average_buy_price) / average_buy_price) * 100
                log_to_slack(f"매도 신호 감지 및 최소 이익 달성. {COIN_TICKER} {amount}개를 {current_price}원에 매도했습니다. 이익률: {profit_percent:.2f}%")
                position = None
            else:
                # I. 포지션 유지
                print("포지션을 유지합니다.")
                time.sleep(10)
                continue
        else:
            if buy_signal:
                # D. 포지션 크기 결정
                total_score = score_auxiliary_indicators(df)
                total_assets = upbit.get_balance('KRW')  # 보유 현금 조회
                position_size = determine_position_size(total_score, total_assets)
                if position_size > 0:
                    # E. 매수 주문 실행
                    desired_price = current_price  # 희망 가격 설정
                    order_price = desired_price * 1.005  # 지정가 주문 가격 설정 (희망 가격의 1.005배)
                    amount = position_size / order_price  # 매수 수량 계산
                    upbit.buy_limit_order(COIN_TICKER, order_price, amount)  # 지정가 매수 주문
                    log_to_slack(f"{COIN_TICKER} {amount}개를 {order_price}원에 지정가 매수 주문했습니다.")
                    # F. 주문 체결 확인
                    time.sleep(10)
                    orders = upbit.get_order(COIN_TICKER)
                    open_orders = [o for o in orders if o['side'] == 'bid']
                    if not open_orders:
                        # 주문 체결됨
                        position = 'LONG'
                        entry_price = upbit.get_avg_buy_price(COIN_TICKER)  # 평균 매수가 가져오기
                        average_buy_price = entry_price  # 평균 구매가 저장
                        bbw_level = df['bb_width'].iloc[-1] / df['bb_width_ma'].iloc[-1]
                        atr = df['atr'].iloc[-1]
                        stop_loss, take_profit = set_stop_loss_take_profit(entry_price, atr, bbw_level)
                        log_to_slack(f"매수 주문 체결됨. 진입 가격={entry_price}, 손절매={stop_loss}, 이익 실현={take_profit}")
                    else:
                        # 주문 미체결, 주문 취소
                        for order in open_orders:
                            upbit.cancel_order(order['uuid'])
                        log_to_slack("매수 주문이 체결되지 않아 취소되었습니다.")
                else:
                    print("총합 스코어가 낮아 포지션에 진입하지 않습니다.")
            else:
                # I. 매수 조건 미충족, 대기
                print("매수 신호가 없습니다. 대기합니다.")
                time.sleep(10)
                continue

        # J. 반복문 지연
        time.sleep(20)

    except Exception as e:
        log_to_slack(f"에러 발생: {e}")
        time.sleep(20)
