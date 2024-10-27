import pandas as pd
import pandas_ta as ta
import pyupbit
import matplotlib.pyplot as plt
import time

# 거래 심볼 및 타임프레임 설정
symbol = "KRW-BTC"
timeframe = "minute1"  # 1분봉
higher_timeframe = "minute15"  # 15분봉 또는 "minute60"으로 변경 가능

# 데이터 수집 함수
def get_historical_data(symbol, interval, count):
    df_list = []
    to = None  # 마지막 데이터의 시간

    while count > 0:
        fetch_count = min(count, 200)
        df = pyupbit.get_ohlcv(symbol, interval=interval, count=fetch_count, to=to)
        if df is None or df.empty:
            break
        df_list.append(df)
        # to 파라미터를 1초 이전으로 설정하여 중복 방지
        last_timestamp = df.index[0]
        to = last_timestamp - pd.Timedelta(seconds=1)
        count -= fetch_count
        time.sleep(0.1)  # API 호출 간 딜레이

    df = pd.concat(df_list)
    df = df.sort_index()
    # 인덱스 중복 제거
    df = df[~df.index.duplicated(keep='first')]
    return df

# 지표 계산 함수
def calculate_indicators(df):
    # MACD
    macd = ta.macd(df['close'])
    df = pd.concat([df, macd], axis=1)
    
    # RSI
    rsi = ta.rsi(df['close'], length=14)
    df['RSI'] = rsi
    
    # Bollinger Bands
    bb = ta.bbands(df['close'], length=20)
    df = pd.concat([df, bb], axis=1)
    
    # %B
    df['%B'] = (df['close'] - df['BBL_20_2.0']) / (df['BBU_20_2.0'] - df['BBL_20_2.0'])
    
    # ATR
    atr = ta.atr(df['high'], df['low'], df['close'], length=14)
    df['ATR'] = atr
    
    # OBV
    obv = ta.obv(df['close'], df['volume'])
    df['OBV'] = obv
    
    return df

# 전략 구현 함수
def apply_strategy(df, higher_df):
    # 포지션 관리 변수 초기화
    position = None  # "long" 또는 None
    entry_price = 0
    stop_loss = 0
    take_profit = 0
    trade_count = 0
    positions = []
    returns = []

    # 보조 지표 스코어링 함수
    def get_volume_score(current_volume, avg_volume):
        if current_volume < avg_volume:
            return 0
        elif current_volume == avg_volume:
            return 1
        else:
            return 2

    def get_obv_score(current_obv, prev_obv):
        diff = current_obv - prev_obv
        if diff > 0:
            return 2
        elif diff == 0:
            return 1
        else:
            return 0

    # 메인 루프
    for i in range(1, len(df)):
        # 현재 시점의 데이터 선택
        current_data = df.iloc[i]
        prev_data = df.iloc[i - 1]
        
        # 상위 타임프레임 데이터 선택 (인덱스 초과 방지)
        higher_idx = min(i, len(higher_df) - 1)
        current_higher_data = higher_df.iloc[higher_idx]
        
        # 추세 판단 (상위 타임프레임)
        current_macd = current_higher_data['MACD_12_26_9']
        current_macd_signal = current_higher_data['MACDs_12_26_9']
        current_hist = current_higher_data['MACDh_12_26_9']

        if current_macd > current_macd_signal and current_macd > 0 and current_hist > 0:
            trend = "up"
        elif current_macd < current_macd_signal and current_macd < 0 and current_hist < 0:
            trend = "down"
        else:
            trend = "sideways"
        
        # 매매 조건 판단
        prev_rsi = prev_data['RSI']
        current_rsi = current_data['RSI']
        prev_percent_b = prev_data['%B']
        current_percent_b = current_data['%B']
        last_price = current_data['close']
        avg_volume = df['volume'].rolling(window=20).mean().iloc[i]
        current_volume = current_data['volume']
        current_obv = current_data['OBV']
        prev_obv = prev_data['OBV']
        
        volume_score = get_volume_score(current_volume, avg_volume)
        obv_score = get_obv_score(current_obv, prev_obv)
        total_score = volume_score + obv_score
        
        # 포지션 크기 (단순히 총 자산의 비율로 가정)
        position_size = 1  # 백테스트에서는 자산의 비율 대신 1 단위로 거래
        
        # 매수 조건 (조건 완화)
        buy_cond = (
            trend == "up" and
            prev_rsi <= 40 and current_rsi > 40 and
            last_price <= current_data['BBL_20_2.0'] and
            prev_percent_b <= 0 and current_percent_b > 0
        )
        
        # 매도 조건 (조건 완화)
        sell_cond = (
            trend == "down" and
            prev_rsi >= 60 and current_rsi < 60 and
            last_price >= current_data['BBU_20_2.0'] and
            prev_percent_b >= 1 and current_percent_b < 1
        )
        
        # 매매 실행
        if buy_cond and position is None:
            position = "long"
            entry_price = last_price
            stop_loss = entry_price - current_data['ATR']
            take_profit = entry_price + (entry_price - stop_loss) * 2
            trade_count += 1
            positions.append({'type': 'buy', 'price': entry_price, 'time': current_data.name})
            print(f"[매수] 시간: {current_data.name}, 가격: {entry_price}")
        
        elif position == "long":
            # 손절매 또는 이익 실현 조건
            if last_price <= stop_loss or last_price >= take_profit or sell_cond:
                exit_price = last_price
                profit = (exit_price - entry_price) / entry_price
                returns.append(profit)
                positions.append({'type': 'sell', 'price': exit_price, 'time': current_data.name})
                print(f"[매도] 시간: {current_data.name}, 가격: {exit_price}, 수익률: {profit*100:.2f}%")
                position = None
                entry_price = 0
                stop_loss = 0
                take_profit = 0
                trade_count += 1
        
    return positions, returns

# 백테스팅 실행 함수
def backtest():
    # 데이터 수집
    df = get_historical_data(symbol, interval=timeframe, count=5000)
    higher_df = get_historical_data(symbol, interval=higher_timeframe, count=5000)
    
    # 지표 계산
    df = calculate_indicators(df)
    higher_df = calculate_indicators(higher_df)
    
    # 전략 적용
    positions, returns = apply_strategy(df, higher_df)
    
    # 성과 분석
    total_return = sum(returns)
    total_trades = len(returns)
    win_trades = len([r for r in returns if r > 0])
    loss_trades = len([r for r in returns if r <= 0])
    win_rate = win_trades / total_trades * 100 if total_trades > 0 else 0
    average_return = total_return / total_trades if total_trades > 0 else 0

    print("\n백테스트 결과")
    print(f"총 거래 횟수: {total_trades}")
    print(f"승리 거래 횟수: {win_trades}")
    print(f"패배 거래 횟수: {loss_trades}")
    print(f"승률: {win_rate:.2f}%")
    print(f"총 수익률: {total_return*100:.2f}%")
    print(f"평균 수익률: {average_return*100:.2f}%")
    
    # 자본 곡선 그리기
    capital = 1  # 초기 자본 1 (단위 자본)
    capital_list = [capital]
    for r in returns:
        capital *= (1 + r)
        capital_list.append(capital)
    
    plt.figure(figsize=(12, 6))
    plt.plot(capital_list)
    plt.title('자본 곡선')
    plt.xlabel('거래 횟수')
    plt.ylabel('자본')
    plt.grid(True)
    plt.show()
    
backtest()
