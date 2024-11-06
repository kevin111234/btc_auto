import time
import os
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import pyupbit
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# 환경 변수 로드 (.env 파일에서 API 키와 Slack 토큰을 불러옵니다)
load_dotenv()

# Upbit API 키
ACCESS_KEY = os.getenv('UPBIT_ACCESS_KEY')
SECRET_KEY = os.getenv('UPBIT_SECRET_KEY')

# Slack API 토큰과 채널 ID
SLACK_TOKEN = os.getenv('SLACK_API_TOKEN')
SLACK_CHANNEL = os.getenv('SLACK_CHANNEL_ID')

# 코인 티커 정보
COIN_TICKER = os.getenv('COIN_TICKER')

# 필수 환경 변수 체크
if not ACCESS_KEY or not SECRET_KEY or not SLACK_TOKEN or not SLACK_CHANNEL or not COIN_TICKER:
    raise ValueError("필수 환경 변수가 설정되지 않았습니다. .env 파일을 확인해주세요.")

# Slack 클라이언트 초기화
slack_client = WebClient(token=SLACK_TOKEN)

# Upbit API 객체 생성
upbit = pyupbit.Upbit(ACCESS_KEY, SECRET_KEY)

def send_slack_message(message):
    """
    Slack 채널로 메시지를 전송하는 함수
    """
    try:
        response = slack_client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=message
        )
    except SlackApiError as e:
        print(f"Slack API 에러 발생: {e.response['error']}")

def get_historical_data(ticker, interval, count):
    """
    과거 가격 데이터를 가져오는 함수
    """
    df = pyupbit.get_ohlcv(ticker=ticker, interval=interval, count=count)
    return df

def get_current_data(ticker):
    """
    현재 가격과 거래량 데이터를 가져오는 함수
    """
    price = pyupbit.get_current_price(ticker)
    orderbook = pyupbit.get_orderbook(ticker)
    if orderbook is None:
        raise ValueError("주문서 정보를 가져오는 데 실패했습니다.")
    volume = orderbook['total_ask_size'] + orderbook['total_bid_size']
    return price, volume

def calculate_indicators(df):
    """
    기술적 지표를 계산하는 함수
    """
    # 볼린저 밴드 계산
    df['bb_upper'] = df['close'].rolling(window=20).mean() + 2 * df['close'].rolling(window=20).std()
    df['bb_middle'] = df['close'].rolling(window=20).mean()
    df['bb_lower'] = df['close'].rolling(window=20).mean() - 2 * df['close'].rolling(window=20).std()

    # RSI 계산
    delta = df['close'].diff(1)
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # OBV 계산
    df['obv'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()

    # BBW 계산 (볼린저 밴드 폭)
    df['bb_width'] = df['bb_upper'] - df['bb_lower']

    return df

def generate_signals(df):
    """
    매매 신호를 생성하는 함수
    """
    last = df.iloc[-1]

    # 매수 조건: 가격이 볼린저 밴드 하단을 하향 돌파하고 RSI가 30 이하인 경우
    if last['close'] <= last['bb_lower'] and last['rsi'] < 30:
        print(f"가격 {last['close']} 에서 rsi {last['rsi']}")
        return 'buy'
    # 매도 조건: 가격이 볼린저 밴드 상단을 상향 돌파하고 RSI가 70 이상인 경우
    elif last['close'] >= last['bb_upper'] and last['rsi'] > 70:
        return 'sell'
    else:
        return 'hold'

def calculate_position_size(df, max_position):
    """
    변동성 스코어에 따라 포지션 크기를 결정하는 함수
    """
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
    df.loc[df.index[-1], 'bb_width'] = df.loc[df.index[-1], 'bb_upper'] - df.loc[df.index[-1], 'bb_lower']  # 현재 BBW 계산
    avg_bb_width = df['bb_width'].rolling(window=20).mean().iloc[-1]  # 20기간 평균 BBW
    bbw_level = last['bb_width'] / avg_bb_width  # BBW 수준 평가
    bbw_score = 0
    if bbw_level < 0.8:
        bbw_score = 0  # 변동성 낮음
    elif 0.8 <= bbw_level <= 1.2:
        bbw_score = 1  # 변동성 보통
    else:
        bbw_score = 2  # 변동성 높음
    total_score += bbw_score

    # 총 스코어를 기반으로 포지션 크기 결정
    score_ratio = total_score / 6  # 최대 스코어 6점
    position_size = max_position * score_ratio

    return position_size

def place_limit_order(ticker, side, price, volume):
    """
    지정가 주문을 제출하는 함수
    """
    if side == 'buy':
        order = upbit.buy_limit_order(ticker, price, volume)
    elif side == 'sell':
        order = upbit.sell_limit_order(ticker, price, volume)
    else:
        return None
    return order

def cancel_order(uuid):
    """
    주문을 취소하는 함수
    """
    result = upbit.cancel_order(uuid)
    return result

def check_order_status(uuid):
    """
    주문의 체결 여부를 확인하는 함수
    """
    order = upbit.get_order(uuid)
    return order['state'] == 'done'

def calculate_max_position():
    """
    총 자산의 50%를 재설정하는 함수
    """
    # 보유 자산의 수량 조회
    btc_balance = upbit.get_balance('KRW-BTC')
    eth_balance = upbit.get_balance('KRW-ETH')
    krw_balance = upbit.get_balance('KRW')

    if btc_balance is None or eth_balance is None or krw_balance is None:
        raise ValueError("잔액 정보를 가져오는 데 실패했습니다.")

    btc_balance = float(btc_balance)
    eth_balance = float(eth_balance)
    krw_balance = float(krw_balance)

    # 현재 가격 조회
    btc_price = pyupbit.get_current_price('KRW-BTC')
    eth_price = pyupbit.get_current_price('KRW-ETH')
    if btc_price is None or eth_price is None:
        raise ValueError("현재 가격 정보를 가져오는 데 실패했습니다.")

    # 자산 평가 금액 계산
    btc_value = btc_balance * btc_price
    eth_value = eth_balance * eth_price
    total_asset_value = btc_value + eth_value + krw_balance

    # max_position 설정 (총 자산의 48%)
    max_position = total_asset_value * 0.48

    print(f"""
    현금 보유량: {krw_balance}
    BTC 보유량:  {btc_value}
    ETH 보유량:  {eth_value}
    """)
    return max_position

def main():
    # 거래 대상 종목 설정
    ticker = COIN_TICKER

    print("프로그램을 시작합니다.")

    # 초기 max_position 설정
    max_position = calculate_max_position()

    # 슬랙으로 자산 평가 금액 및 max_position 알림
    message = f"""총 자산 평가 금액: {max_position * 2:,.0f}원
    투자 한도(max_position): {max_position:,.0f}원"""
    send_slack_message(message)

    # 초기 데이터 수집
    df = get_historical_data(ticker, interval='minute1', count=200)
    if df is None or df.empty:
        raise ValueError("과거 데이터를 가져오는 데 실패했습니다.")
    df = calculate_indicators(df)

    # 매수한 포지션 정보를 저장할 변수
    position = {
        'avg_buy_price': 0,  # 평균 매수가
        'volume': 0,         # 보유 수량
        'stop_loss_price': 0,    # 손절매 가격
        'take_profit_price': 0   # 이익 실현 가격
    }

    while True:
        try:
            # 실시간 데이터 추가
            current_price, current_volume = get_current_data(ticker)
            new_data = {
                'close': current_price,
                'volume': current_volume
            }
            df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
            df = calculate_indicators(df)

            # 매매 신호 생성
            signal = generate_signals(df)

            # 매수 신호 처리
            if signal == 'buy' and position['volume'] == 0:
                # 포지션 크기 결정
                position_size = calculate_position_size(df, max_position)
                # 희망 가격 설정 (현재가)
                desired_price = current_price
                # 지정가 주문 가격 계산 (0.5% 상향)
                order_price = desired_price * 1.005
                # 주문 수량 계산 (소수점 8자리까지 표현)
                volume = round(position_size / order_price, 8)
                if volume == 0:
                    send_slack_message("주문 수량이 0으로 계산되어 매수를 진행하지 않습니다.")
                    continue
                # 매수 주문 실행
                order = place_limit_order(ticker, 'buy', order_price, volume)
                if order is not None:
                    order_uuid = order['uuid']
                    send_slack_message(f"매수 주문 제출: {order}")

                    # 20초 대기 후 주문 체결 확인
                    time.sleep(20)
                    if not check_order_status(order_uuid):
                        cancel_order(order_uuid)
                        send_slack_message("매수 주문 미체결로 취소됨")
                    else:
                        send_slack_message("매수 주문 체결 완료")
                        # 평균 매수가 및 보유 수량 업데이트
                        position['avg_buy_price'] = float(upbit.get_avg_buy_price(ticker))
                        position['volume'] = float(upbit.get_balance(ticker))
                        # 손절매 및 이익 실현 가격 설정
                        position['stop_loss_price'] = position['avg_buy_price'] * 0.99  # 1% 손실 시 손절
                        position['take_profit_price'] = position['avg_buy_price'] * 1.02  # 2% 이익 시 매도
                else:
                    send_slack_message("매수 주문 실패")

            # 매도 신호 처리
            elif signal == 'sell' and position['volume'] > 0:
                # 현재 가격이 평균 매수가 대비 1% 이상 상승한 경우에만 매도
                if current_price >= position['avg_buy_price'] * 1.01:
                    # 지정가 주문 가격 계산 (0.5% 상향)
                    order_price = current_price * 1.005
                    # 매도 주문 실행
                    order = place_limit_order(ticker, 'sell', order_price, position['volume'])
                    if order is not None:
                        order_uuid = order['uuid']
                        send_slack_message(f"매도 주문 제출: {order}")

                        # 20초 대기 후 주문 체결 확인
                        time.sleep(20)
                        if not check_order_status(order_uuid):
                            cancel_order(order_uuid)
                            send_slack_message("매도 주문 미체결로 취소됨")
                        else:
                            send_slack_message("매도 주문 체결 완료")
                            # 포지션 정보 초기화
                            position = {'avg_buy_price': 0, 'volume': 0, 'stop_loss_price': 0, 'take_profit_price': 0}
                            # 매도 후 max_position 재설정
                            max_position = calculate_max_position()
                            send_slack_message(f"매도 후 max_position 재설정: {max_position:,.0f}원")
                    else:
                        send_slack_message("매도 주문 실패")
                else:
                    send_slack_message("현재 가격이 평균 매수가 대비 1% 이상 상승하지 않아 매도하지 않음")

            # 손절매 및 이익 실현 조건 확인
            if position['volume'] > 0:
                # 손절매 조건
                if current_price <= position['stop_loss_price']:
                    send_slack_message("손절매 조건 충족, 시장가 매도 진행")
                    upbit.sell_market_order(ticker, position['volume'])
                    # 포지션 정보 초기화
                    position = {'avg_buy_price': 0, 'volume': 0, 'stop_loss_price': 0, 'take_profit_price': 0}
                    # 손절매 후 max_position 재설정
                    max_position = calculate_max_position()
                    send_slack_message(f"손절매 후 max_position 재설정: {max_position:,.0f}원")

                # 이익 실현 조건
                elif current_price >= position['take_profit_price']:
                    send_slack_message("이익 실현 조건 충족, 시장가 매도 진행")
                    upbit.sell_market_order(ticker, position['volume'])
                    # 포지션 정보 초기화
                    position = {'avg_buy_price': 0, 'volume': 0, 'stop_loss_price': 0, 'take_profit_price': 0}
                    # 이익 실현 후 max_position 재설정
                    max_position = calculate_max_position()
                    send_slack_message(f"이익 실현 후 max_position 재설정: {max_position:,.0f}원")

            else:
                print("매매 신호 없음")

            # 데이터 프레임 관리 (최대 행 수 제한)
            if len(df) > 200:
                df = df.iloc[-200:].reset_index(drop=True)

            # 10초 대기
            time.sleep(10)

        except Exception as e:
            # 에러 발생 시 슬랙으로 알림 전송
            send_slack_message(f"에러 발생: {e}")
            # 에러 메시지 출력
            print(f"에러 발생: {e}")
            # 60초 대기 후 재시도
            time.sleep(60)

if __name__ == "__main__":
    main()
