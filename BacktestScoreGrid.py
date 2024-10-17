import numpy as np
import pandas as pd
from itertools import product
import pyupbit
from tqdm import tqdm
import time

# 1. 데이터 로드 (PyUpbit API로 1분 봉 데이터 수집)
def get_data(symbol='KRW-BTC', interval='minute1', count=20000000):
    step = max(1, count // 100)
    df_list = []
    with tqdm(total=count, desc="데이터 로드 중") as pbar:
        for start in range(0, count, step):
            partial_count = min(step, count - start)
            df_partial = pyupbit.get_ohlcv(symbol, interval=interval, count=partial_count)
            if df_partial is not None:
                df_list.append(df_partial)
            pbar.update(partial_count)
            time.sleep(0.1)  # API 호출 간 간격을 두어 서버 부담을 줄임
    df = pd.concat(df_list).reset_index()
    return df

data = get_data()

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

# 백테스트 전략 함수 (수정된 버전)
def backtest_strategy(data, ema_short, ema_long, rsi_period, bb_period, stop_loss, take_profit, weights):
    cash = 1000000  # 초기 자본
    initial_cash = cash
    position = None  # 현재 포지션 정보
    total_trades = 0
    win_trades = 0
    losses = []
    max_drawdown = 0
    peak_value = cash
    fee_rate = 0.0005  # 수수료 0.05%

    # 지표 계산
    data['ema_short'] = data['close'].ewm(span=ema_short, adjust=False).mean()
    data['ema_long'] = data['close'].ewm(span=ema_long, adjust=False).mean()
    data['rsi'] = compute_rsi(data['close'], rsi_period)
    data['bb_upper'], data['bb_lower'] = compute_bollinger_bands(data['close'], bb_period)

    for index, row in data.iterrows():
        current_price = row['close']

        # 총 자산 가치 계산
        total_asset = cash
        if position is not None:
            total_asset += position['quantity'] * current_price

        # MDD 계산
        if total_asset > peak_value:
            peak_value = total_asset
        drawdown = (peak_value - total_asset) / peak_value * 100
        if drawdown > max_drawdown:
            max_drawdown = drawdown

        # 매수 점수 계산
        buy_score = 0
        if row['ema_short'] > row['ema_long']:
            buy_score += weights['ema']
        if row['rsi'] < 30:
            buy_score += weights['rsi']
        if current_price <= row['bb_lower']:
            buy_score += weights['bollinger']

        # 매도 점수 계산
        sell_score = 0
        if row['ema_short'] < row['ema_long']:
            sell_score += weights['ema']
        if row['rsi'] > 70:
            sell_score += weights['rsi']
        if current_price >= row['bb_upper']:
            sell_score += weights['bollinger']

        # 매수 조건
        if buy_score >= sum(weights.values()) * 0.6 and position is None:
            # 전액 매수
            position_quantity = (cash * (1 - fee_rate)) / current_price
            position_price = current_price
            position = {
                'quantity': position_quantity,
                'price': position_price,
                'stop_price': position_price * (1 - stop_loss),
                'take_price': position_price * (1 + take_profit)
            }
            cash = 0
            total_trades += 1

        # 매도 조건
        elif sell_score >= sum(weights.values()) * 0.6 and position is not None:
            # 이익 실현 또는 손절 매도
            sell_value = position['quantity'] * current_price * (1 - fee_rate)
            if current_price >= position['take_price']:
                profit = sell_value - (position['quantity'] * position['price'])
                cash += sell_value
                win_trades += 1
                position = None
            elif current_price <= position['stop_price']:
                loss = (position['quantity'] * position['price']) - sell_value
                cash += sell_value
                if position['quantity'] > 0 and position['price'] > 0:
                    losses.append(loss / (position['quantity'] * position['price']) * 100)
                position = None

    # 최종 자산 가치 계산
    if position is not None:
        total_asset = cash + position['quantity'] * current_price
    else:
        total_asset = cash

    # 성과 지표 계산
    total_return = (total_asset - initial_cash) / initial_cash * 100
    win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0

    return data, total_asset, max_drawdown, total_trades, win_rate, total_return

# 그리드 서치 함수
def grid_search(data, ema_short_range, ema_long_range, rsi_period_range, bb_period_range, stop_loss_range, take_profit_range, ema_weight_range, rsi_weight_range, bollinger_weight_range):
    best_portfolio_value = 0  # 초기 자본 값으로 초기화
    best_params = None
    best_results = None

    total_combinations = len(ema_short_range) * len(ema_long_range) * len(rsi_period_range) * len(bb_period_range) * len(stop_loss_range) * len(take_profit_range) * len(ema_weight_range) * len(rsi_weight_range) * len(bollinger_weight_range)
    progress_bar = tqdm(total=total_combinations, desc="그리드 서치 진행 중")

    for ema_short, ema_long, rsi_period, bb_period, stop_loss, take_profit, ema_weight, rsi_weight, bollinger_weight in product(
            ema_short_range, ema_long_range, rsi_period_range, bb_period_range, stop_loss_range, take_profit_range, ema_weight_range, rsi_weight_range, bollinger_weight_range):

        weights = {
            'ema': ema_weight,
            'rsi': rsi_weight,
            'bollinger': bollinger_weight
        }

        # 백테스트 실행
        results, portfolio_value, mdd, total_trades, win_rate, total_return = backtest_strategy(
            data, ema_short, ema_long, rsi_period, bb_period, stop_loss, take_profit, weights)

        if portfolio_value > best_portfolio_value:
            best_portfolio_value = portfolio_value
            best_params = {
                'ema_short': ema_short,
                'ema_long': ema_long,
                'rsi_period': rsi_period,
                'bb_period': bb_period,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'weights': weights
            }
            best_results = {
                'portfolio_value': portfolio_value,
                'mdd': mdd,
                'total_trades': total_trades,
                'win_rate': win_rate,
                'total_return': total_return
            }
        progress_bar.update(1)

    progress_bar.close()
    return best_params, best_results

# 그리드 서치 파라미터 설정 (범위로 변경)
ema_short_range = range(10, 16, 1)
ema_long_range = range(20, 31, 1)
rsi_period_range = range(14, 22, 1)
bb_period_range = range(10, 21, 1)
stop_loss_range = np.linspace(0.01, 0.1, 10)
take_profit_range = np.linspace(0.02, 0.2, 10)
ema_weight_range = range(1, 3, 1)
rsi_weight_range = range(1, 3, 1)
bollinger_weight_range = range(1, 3, 1)

# 그리드 서치 실행
best_params, best_results = grid_search(
    data,
    ema_short_range,
    ema_long_range,
    rsi_period_range,
    bb_period_range,
    stop_loss_range,
    take_profit_range,
    ema_weight_range,
    rsi_weight_range,
    bollinger_weight_range
)

# 결과 출력
print(f"최적의 파라미터 조합: {best_params}")
print(f"최종 포트폴리오 가치: {best_results['portfolio_value']}")
print(f"최대 낙폭(MDD): {best_results['mdd']}%")
print(f"총 거래 횟수: {best_results['total_trades']}")
print(f"승률: {best_results['win_rate']}%")
print(f"총 수익률: {best_results['total_return']}%")
