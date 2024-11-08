import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests
from datetime import datetime, timedelta
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
from itertools import product

# 1. 데이터 수집 함수
def get_historical_data(market, interval, to, count):
    url = f"https://api.upbit.com/v1/candles/{interval}"
    headers = {"Accept": "application/json"}
    params = {
        "market": market,
        "to": to,
        "count": count
    }
    res = requests.get(url, headers=headers, params=params)
    data = res.json()
    df = pd.DataFrame(data)
    
    # 날짜 형식 지정
    df['candle_date_time_kst'] = pd.to_datetime(df['candle_date_time_kst'], format='%Y-%m-%dT%H:%M:%S')
    
    df = df[['candle_date_time_kst', 'opening_price', 'high_price', 'low_price', 'trade_price', 'candle_acc_trade_volume']]
    df.rename(columns={
        'candle_date_time_kst': 'datetime',
        'opening_price': 'open',
        'high_price': 'high',
        'low_price': 'low',
        'trade_price': 'close',
        'candle_acc_trade_volume': 'volume'
    }, inplace=True)
    df.sort_values('datetime', inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df

# 2. 전체 데이터 수집 함수
def collect_data(market, interval, start_date, end_date):
    df_list = []
    to = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
    while True:
        df = get_historical_data(market, interval, to.strftime("%Y-%m-%d %H:%M:%S"), 200)
        if df.empty:
            break
        df_list.append(df)
        oldest = df['datetime'].min()
        if oldest <= datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S"):
            break
        to = oldest - timedelta(seconds=1)
    total_df = pd.concat(df_list)
    total_df.drop_duplicates(subset='datetime', inplace=True)
    total_df.sort_values('datetime', inplace=True)
    total_df = total_df[total_df['datetime'] >= datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")]
    total_df.reset_index(drop=True, inplace=True)
    return total_df

# 3. 지표 계산 함수
def calculate_indicators(df, rsi_period, bb_period, bb_std_dev):
    df['rsi'] = RSIIndicator(close=df['close'], window=rsi_period).rsi()
    bb_indicator = BollingerBands(close=df['close'], window=bb_period, window_dev=bb_std_dev)
    df['bb_middle'] = bb_indicator.bollinger_mavg()
    df['bb_upper'] = bb_indicator.bollinger_hband()
    df['bb_lower'] = bb_indicator.bollinger_lband()
    return df

# 4. 매매 전략 함수
def generate_signals(df_1m, df_5m, params):
    # 매개변수 추출
    rsi_period = params['rsi_period']
    rsi_buy = params['rsi_buy']
    rsi_sell = params['rsi_sell']
    bb_period = params['bb_period']
    bb_std_dev = params['bb_std_dev']
    
    # 지표 계산
    df_1m = calculate_indicators(df_1m, rsi_period, bb_period, bb_std_dev)
    df_5m = calculate_indicators(df_5m, rsi_period, bb_period, bb_std_dev)
    
    # 5분봉의 RSI를 1분봉에 매핑
    df_5m.set_index('datetime', inplace=True)
    df_1m['rsi_5m'] = df_1m['datetime'].map(df_5m['rsi'])
    df_5m.reset_index(inplace=True)
    
    # 매매 신호 생성
    df_1m['signal'] = 0
    for i in range(len(df_1m)):
        # 매수 신호
        if (df_1m.loc[i, 'rsi'] <= rsi_buy and
            df_1m.loc[i, 'close'] <= df_1m.loc[i, 'bb_lower'] and
            df_1m.loc[i, 'rsi_5m'] <= rsi_buy + 5):
            df_1m.loc[i, 'signal'] = 1  # 매수 신호
        # 매도 신호
        elif (df_1m.loc[i, 'rsi'] >= rsi_sell and
              df_1m.loc[i, 'close'] >= df_1m.loc[i, 'bb_upper'] and
              df_1m.loc[i, 'rsi_5m'] >= rsi_sell - 5):
            df_1m.loc[i, 'signal'] = -1  # 매도 신호
    return df_1m

# 5. 백테스트 함수
def backtest(df, initial_cash, fee):
    cash = initial_cash
    holding = 0
    portfolio_values = []
    trade_history = []
    last_signal = 0  # 중복 거래 방지

    for i in range(len(df)):
        price = df.loc[i, 'close']
        signal = df.loc[i, 'signal']
        
        # 매수 신호
        if signal == 1 and cash > 0 and last_signal != 1:
            # 비율 투자 (자산의 10%)
            amount = cash * 0.1
            if amount < 5000:
                continue  # 최소 거래 금액 미만이면 거래하지 않음
            quantity = (amount * (1 - fee)) / price
            cash -= amount
            holding += quantity
            trade_history.append({'datetime': df.loc[i, 'datetime'], 'type': 'buy', 'price': price, 'quantity': quantity, 'cash': cash, 'holding': holding})
            last_signal = 1  # 최근 신호 업데이트
        
        # 매도 신호
        elif signal == -1 and holding > 0 and last_signal != -1:
            amount = holding * price * (1 - fee)
            cash += amount
            trade_history.append({'datetime': df.loc[i, 'datetime'], 'type': 'sell', 'price': price, 'quantity': holding, 'cash': cash, 'holding': 0})
            holding = 0
            last_signal = -1  # 최근 신호 업데이트

        # 포트폴리오 가치 계산
        portfolio_value = cash + holding * price
        portfolio_values.append({'datetime': df.loc[i, 'datetime'], 'portfolio_value': portfolio_value})

    # 결과 DataFrame 생성
    portfolio_df = pd.DataFrame(portfolio_values)
    trade_df = pd.DataFrame(trade_history)
    return portfolio_df, trade_df

# 6. 그리드 서치를 통한 최적의 매개변수 탐색
def grid_search(df_1m, df_5m, param_grid, initial_cash, fee):
    # 매개변수 조합 생성
    keys = param_grid.keys()
    values = (param_grid[key] for key in keys)
    param_combinations = [dict(zip(keys, combination)) for combination in product(*values)]
    
    results = []
    for idx, params in enumerate(param_combinations):
        print(f"진행 중: {idx+1}/{len(param_combinations)} - 매개변수: {params}")
        # 매매 신호 생성
        df_with_signals = generate_signals(df_1m.copy(), df_5m.copy(), params)
        # 백테스트 실행
        portfolio_df, trade_df = backtest(df_with_signals, initial_cash, fee)
        # 성과 지표 계산
        total_return = (portfolio_df['portfolio_value'].iloc[-1] - initial_cash) / initial_cash
        max_drawdown = (portfolio_df['portfolio_value'].cummax() - portfolio_df['portfolio_value']).max() / portfolio_df['portfolio_value'].cummax().max()
        results.append({
            'params': params,
            'total_return': total_return,
            'max_drawdown': max_drawdown
        })
    # 결과를 DataFrame으로 변환
    results_df = pd.DataFrame(results)
    return results_df

# 7. 메인 함수
def main():
    # 데이터 수집 기간 설정
    start_date = "2024-01-01 00:00:00"
    end_date = "2024-01-10 23:59:59"  # 예시를 위해 10일치 데이터 사용 (실제 사용 시 기간을 늘리세요)
    
    # 코인 마켓 코드
    market_code = "KRW-BTC"
    
    # 1분봉 데이터 수집
    print("1분봉 데이터 수집 중...")
    data_1m = collect_data(market_code, "minutes/1", start_date, end_date)
    
    # 5분봉 데이터 수집
    print("5분봉 데이터 수집 중...")
    data_5m = collect_data(market_code, "minutes/5", start_date, end_date)
    
    # 매개변수 그리드 설정
    param_grid = {
        'rsi_period': [14],
        'rsi_buy': [25, 30, 35],
        'rsi_sell': [65, 70, 75],
        'bb_period': [20],
        'bb_std_dev': [2]
    }
    
    # 초기 자본금 및 거래 비용 설정
    initial_cash = 1000000  # 1,000,000원
    fee = 0.001  # 거래 비용 0.1%
    
    # 그리드 서치 실행
    print("그리드 서치 시작...")
    results_df = grid_search(data_1m, data_5m, param_grid, initial_cash, fee)
    
    # 결과 정렬 및 최적의 매개변수 선택
    results_df.sort_values('total_return', ascending=False, inplace=True)
    best_result = results_df.iloc[0]
    best_params = best_result['params']
    print(f"\n최적의 매개변수: {best_params}")
    print(f"총 수익률: {best_result['total_return'] * 100:.2f}%")
    print(f"최대 낙폭: {best_result['max_drawdown'] * 100:.2f}%")
    
    # 최적의 매개변수로 다시 백테스트 실행
    df_with_signals = generate_signals(data_1m.copy(), data_5m.copy(), best_params)
    portfolio_df, trade_df = backtest(df_with_signals, initial_cash, fee)
    
    # 포트폴리오 가치 시각화
    plt.figure(figsize=(14, 7))
    plt.plot(portfolio_df['datetime'], portfolio_df['portfolio_value'])
    plt.title('포트폴리오 가치 변화')
    plt.xlabel('날짜')
    plt.ylabel('포트폴리오 가치')
    plt.show()
    
    # 거래 내역 시각화
    plt.figure(figsize=(14, 7))
    plt.plot(df_with_signals['datetime'], df_with_signals['close'], label='가격')
    
    buy_signals = df_with_signals[df_with_signals['signal'] == 1]
    sell_signals = df_with_signals[df_with_signals['signal'] == -1]
    
    plt.scatter(buy_signals['datetime'], buy_signals['close'], marker='^', color='g', label='매수 신호')
    plt.scatter(sell_signals['datetime'], sell_signals['close'], marker='v', color='r', label='매도 신호')
    
    plt.title('가격 및 매매 신호')
    plt.xlabel('날짜')
    plt.ylabel('가격')
    plt.legend()
    plt.show()
    
    # 거래 내역 출력
    print("\n거래 내역:")
    print(trade_df)
    
    # 포트폴리오 가치 출력
    final_portfolio_value = portfolio_df['portfolio_value'].iloc[-1]
    total_return = (final_portfolio_value - initial_cash) / initial_cash
    print(f"\n최종 포트폴리오 가치: {final_portfolio_value:.0f}원")
    print(f"총 수익률: {total_return * 100:.2f}%")
    
if __name__ == "__main__":
    main()
