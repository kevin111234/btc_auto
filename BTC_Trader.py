import os
from dotenv import load_dotenv
import pyupbit
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import pandas as pd
import time

# 환경변수 설정
load_dotenv()
UPBIT_ACCESS_KEY = os.getenv('UPBIT_ACCESS_KEY')
UPBIT_SECRET_KEY = os.getenv('UPBIT_SECRET_KEY')
SLACK_API_TOKEN = os.getenv('SLACK_API_TOKEN')
SLACK_CHANNEL_ID = os.getenv('SLACK_CHANNEL_ID')
COIN_TICKER = os.getenv('COIN_TICKER')

# 거래중인 코인 티커 목록
TICKERS = ['KRW-BTC']

# Upbit, Slack 클라이언트 초기화
upbit = pyupbit.Upbit(UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY)
slack_client = WebClient(token=SLACK_API_TOKEN)

# SLACK 메시지 전송 함수
def send_slack_message(message):
    try:
        slack_client.chat_postMessage(channel=SLACK_CHANNEL_ID, text=message)
    except SlackApiError as e:
        print(f"Error sending message: {e.response['error']}")

def calculate_indicators(df):
    delta = df['close'].diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    n = 14  # 기간 설정

    # 첫 번째 평균값 계산 (SMA)
    avg_gain = gains[:n].mean()
    avg_loss = losses[:n].mean()

    # 이후 평균값 계산 (와일더의 방법)
    avg_gain_list = [avg_gain]
    avg_loss_list = [avg_loss]

    for i in range(n, len(gains)):
        gain = gains.iloc[i]
        loss = losses.iloc[i]

        avg_gain = ((avg_gain * (n - 1)) + gain) / n
        avg_loss = ((avg_loss * (n - 1)) + loss) / n

        avg_gain_list.append(avg_gain)
        avg_loss_list.append(avg_loss)

    # RS 및 RSI 계산
    rs = pd.Series(avg_gain_list, index=delta.index[n-1:]) / pd.Series(avg_loss_list, index=delta.index[n-1:])
    rsi = 100 - (100 / (1 + rs))

    return rsi.iloc[-1]

def get_rsi(rsi):
    # 50 이상 rsi 반전
    if rsi >= 50:
        rsi = 100-rsi
    # rsi 정규화
    if rsi <= 20:
        return 20
    elif rsi <= 25:
        return 25
    elif rsi <= 30:
        return 30
    elif rsi <= 35:
        return 35
    else:
      return 50

def get_position_size(rsi):
    if rsi == 20:
        return 0.4
    elif rsi == 25:
        return 0.3
    elif rsi == 30:
        return 0.2
    elif rsi == 35:
        return 0.1
    return 0

def get_limit_amount(upbit):
    """원화 잔액을 기반으로 limit_amount를 계산"""
    try:
        balances = upbit.get_balances()
        krw_balance = float(next((balance['balance'] for balance in balances 
                                  if balance['currency'] == 'KRW'), 0))
        return krw_balance
    except Exception as e:
        print(f"Limit amount 조회 중 에러 발생: {str(e)}")
        return 0

def get_asset_info(upbit):
    try:
        balances = upbit.get_balances()
        
        krw_balance = float(next((balance['balance'] for balance in balances 
                                if balance['currency'] == 'KRW'), 0))
        
        coin_info = {}
        total_asset = krw_balance

        for ticker in TICKERS:
            currency = ticker.split('-')[1]
            current_price = pyupbit.get_current_price(ticker)
            
            coin_balance = float(next((balance['balance'] for balance in balances 
                                      if balance['currency'] == currency), 0))
            avg_buy_price = float(next((balance['avg_buy_price'] for balance in balances 
                                      if balance['currency'] == currency), 0))
            
            coin_value = coin_balance * current_price
            total_asset += coin_value
            
            profit_rate = ((current_price - avg_buy_price) / avg_buy_price * 100) if avg_buy_price > 0 else 0
            
            coin_info[currency] = {
                'balance': coin_balance,
                'avg_price': avg_buy_price,
                'current_price': current_price,
                'value': coin_value,
                'profit_rate': profit_rate
            }

        return {
            'krw_balance': krw_balance,
            'coin_info': coin_info,
            'total_asset': total_asset
        }

    except Exception as e:
        print(f"자산 정보 조회 중 에러 발생: {str(e)}")
        return None

def send_asset_info(asset_info, limit_amount):
    if asset_info is None:
        return
        
    message = f"""
📊 자산 현황 보고
──────────────
💰 보유 KRW: {asset_info['krw_balance']:,.0f}원
──────────────"""

    for currency, info in asset_info['coin_info'].items():
        message += f"""
🪙 {currency}:
수량: {info['balance']:.8f}
평균매수가: {info['avg_price']:,.0f}원
현재가격: {info['current_price']:,.0f}원
평가금액: {info['value']:,.0f}원
수익률: {info['profit_rate']:.2f}%
──────────────"""

    message += f"""
💵 총 자산: {asset_info['total_asset']:,.0f}원
⚖️ 코인 투자한도: {limit_amount:,.0f}원
"""

    send_slack_message(message)

# 주기적 상태점검 보고서 발송
def send_status_update(limit_amount):
    # 자산 정보 조회
    asset_info = get_asset_info(upbit)
    if asset_info is None:
        send_slack_message("자산 정보를 가져오는 데 실패했습니다.")
        return

    # 상태 메시지 작성
    message = f"""
    📈 상태 점검 보고서
    ──────────────
    💰 보유 KRW: {asset_info['krw_balance']:,.0f}원
    💵 총 자산: {asset_info['total_asset']:,.0f}원
    ⚖️ 코인당 투자한도: {limit_amount:,.0f}원
    ──────────────
    """
    
    # 각 코인 정보 추가
    for currency, info in asset_info['coin_info'].items():
        message += f"""
        🪙 {currency}:
        수량: {info['balance']:.8f}
        평균매수가: {info['avg_price']:,.0f}원
        현재가격: {info['current_price']:,.0f}원
        평가금액: {info['value']:,.0f}원
        수익률: {info['profit_rate']:.2f}%
        ──────────────
        """

    # Slack으로 메시지 전송
    send_slack_message(message)


def main():
    rsi_check = []
    position_tracker = {}
    sendStatusTime = 180
    print(f"{COIN_TICKER} 자동투자 프로그램을 시작합니다.")
    initial_asset_info = get_asset_info(upbit)
    limit_amount = get_limit_amount(upbit)
    send_asset_info(initial_asset_info, limit_amount)
    if initial_asset_info is None:
        print("초기 자산 정보 조회 실패. 프로그램을 종료합니다.")
        return
    # 초기 자산의 BTC 보유 여부를 기준으로 매도 조건 설정
    initial_btc_balance = initial_asset_info['coin_info'].get('BTC', {}).get('balance', 0)
    has_initial_btc = initial_btc_balance > 0

    while True:
        try:
            # 매 시간 경과 보고 전송
            sendStatusTime -= 1
            if sendStatusTime == 0:
                send_status_update(limit_amount)
                sendStatusTime = 180

            # 현재 구매한 자산이 없을때 자산 데이터 조회 후 구매한도 재설정
            if len(rsi_check) == 0:
                limit_amount = get_limit_amount(upbit)
                asset_info = get_asset_info(upbit)
                if asset_info is None:
                    send_slack_message("자산 정보 조회 실패, 10초 대기 후 다시 시도합니다...")
                    time.sleep(10)
                    continue
            
            # 가격 데이터 조회
            df = pyupbit.get_ohlcv(COIN_TICKER, interval="minute5", count=100)

            # 현재 가격 조회
            currency = COIN_TICKER.split('-')[1]
            rsi = calculate_indicators(df)
            current_price = pyupbit.get_current_price(COIN_TICKER)
            new_rsi = get_rsi(rsi)

            # 매매 신호 판단
            buy_signal = (rsi <= 35)
            sell_signal = (rsi >= 65 and 
                          current_price > asset_info['coin_info'][currency]['avg_price']*1.01)

            # 초기 자산 정리
            if has_initial_btc and rsi >= 70 and current_price > asset_info['coin_info'][currency]['avg_price']*1.01 :
                order = upbit.sell_market_order(COIN_TICKER, initial_btc_balance)
                message = f"매도 주문 완료. 현재가격: {current_price}"
                print(message)
                send_slack_message(message)
                time.sleep(10)
                if order:
                  message = f"초기 자산 매도 주문 체결\n수량: {initial_btc_balance:.8f}\nRSI: {rsi:.2f}"
                  print(message)
                  send_slack_message(message)
                  has_initial_btc = False  # 초기 자산 정리 완료 후 재실행 방지

            # 매수 진행
            if buy_signal and new_rsi not in rsi_check:
                asset_info = get_asset_info(upbit)
                position_size = get_position_size(new_rsi)*limit_amount
                if position_size > 0 and asset_info['krw_balance'] >= position_size:
                    order = upbit.buy_market_order(COIN_TICKER, position_size)
                    message = f"매수 주문 완료. 현재가격: {current_price}"
                    print(message)
                    send_slack_message(message)
                    time.sleep(10)
                    if order:
                        message = f"[{COIN_TICKER}] 매수 주문 체결\n금액: {position_size:,.0f}원\nRSI: {rsi:.2f}"
                        send_slack_message(message)
                        asset_info = get_asset_info(upbit)
                        send_asset_info(asset_info, limit_amount)

                        # rsi 매매여부 체크(매수 시 추가)
                        buy_amount = float(order['executed_volume'])
                        position_tracker[new_rsi] = buy_amount
                        rsi_check.append(new_rsi)

                        print(position_tracker)
                        print(rsi_check)

            # 매도 진행
            elif sell_signal and new_rsi in rsi_check:
                asset_info = get_asset_info(upbit)
                currency = COIN_TICKER.split('-')[1]
                
                # 해당 RSI 레벨에서 매수했던 수량 계산
                sell_amount = position_tracker[new_rsi]
                
                if sell_amount > 0:
                    order = upbit.sell_market_order(COIN_TICKER, sell_amount)
                    message = f"매도 주문 완료. 현재가격: {current_price}"
                    print(message)
                    send_slack_message(message)
                    time.sleep(10)
                    if order:
                        message = f"[{COIN_TICKER}] 매도 주문 체결\n수량: {sell_amount:.8f}\nRSI: {rsi:.2f}"
                        send_slack_message(message)
                        asset_info = get_asset_info(upbit)
                        send_asset_info(asset_info, limit_amount)

                        # rsi 매매여부 체크(매도 시 삭제)
                        del position_tracker[new_rsi]
                        rsi_check.remove(new_rsi)

                        print(position_tracker)
                        print(rsi_check)
            else:
                print("매수/매도 신호가 없습니다. 기회 탐색중...")

            # 10초간 대기
            time.sleep(10)


        except Exception as e:
            send_slack_message(f"메인 루프 에러: {str(e)}")
            time.sleep(10)

if __name__ == "__main__":
    main()