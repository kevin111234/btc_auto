from config import Config
from api import API
from trade import Trader
from indicator import Indicator
from notifier import Notifier
from datetime import datetime
import pyupbit
import time

def main():
    config = Config() 
    slack_trade_channel = config.slack_trade_channel
    slack_error_channel = config.slack_error_channel
    """
    UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY, 
    SLACK_API_TOKEN, SLACK_TRADE_CHANNEL, SLACK_ERROR_CHANNEL, SLACK_ASSET_CHANNEL, 
    COIN_TICKER
    """
    api = API()
    """
    upbit, slack, get_asset_info
    """

    upbit = api.upbit
    slack = api.slack
    notifier = Notifier()
    TICKERS = config.coin_ticker
    trader = Trader(upbit, slack, TICKERS)

    position_tracker = trader.position_tracker()
    rsi_check = trader.rsi_check()

    print(f"자동투자 프로그램을 시작합니다. {TICKERS}를 모니터링합니다.")
    initial_asset_info = api.get_asset_info()
    if initial_asset_info is None:
        print("초기 자산 정보 조회 실패. 프로그램을 종료합니다.")
        return
    """
    형식: {'krw_balance': 1000000, 
    'coin_info': {'KRW-BTC': {'balance': 1.0, 'avg_price': 100000000, 'current_price': 100000000, 'value': 1000000, 'profit_rate': 0}, 
    'KRW-ETH': {'balance': 1.0, 'avg_price': 100000000, 'current_price': 100000000, 'value': 1000000, 'profit_rate': 0}}, 
    'total_asset': 1000000}
    """
    limit_amount = api.get_limit_amount() # 형식: {'KRW-BTC': 10000, 'KRW-ETH': 10000}
    notifier.send_asset_info(initial_asset_info, limit_amount)

    # 초기자산 데이터를 기준으로 매도 조건 설정
    initial_coin_balance = trader.initial_coin_balance(initial_asset_info)
    has_initial_coin = trader.has_initial_coin(initial_coin_balance)

    status_sent = False

    while True:
        try:
            asset_info = api.get_asset_info()
            if asset_info is None:
                print("자산현황 정보를 가져오는 데 실패했습니다.")
                time.sleep(10)
                continue

            current_time = datetime.now()
            if current_time.minute in [0, 30]:
                if not status_sent:
                    notifier.send_asset_info(asset_info, limit_amount, rsi_check, position_tracker)
                    status_sent = True
            else:
                status_sent = False
            
            for ticker in TICKERS:
                currency = ticker.split('-')[1]
                df = pyupbit.get_ohlcv(ticker, interval="minute5", count=100)
                indicator = Indicator(df)
                rsi, previous_rsi = indicator.calculate_rsi()
                current_price = api.get_current_price(ticker)
                new_rsi = indicator.get_new_rsi()

                # 매매신호 판단
                buy_signal = trader.buy_signal(rsi, previous_rsi)
                sell_signal = trader.sell_signal(rsi, previous_rsi, asset_info['coin_info'][currency]['profit_rate'])
                
                # 초기 자산 정리
                initial_avg_price = initial_asset_info['coin_info'][currency]['avg_price']
                initial_profit_rate = ((current_price - initial_avg_price) / initial_avg_price * 100) if initial_avg_price > 0 else 0
                if has_initial_coin and rsi >= 70 and initial_profit_rate >= 0.5 :
                    order = upbit.sell_market_order(ticker, initial_coin_balance)
                    message = f"매도 주문 완료. 현재가격: {current_price}"
                    print(message)
                    api.send_slack_message(slack_trade_channel, message)
                    time.sleep(10)
                    if order:
                        message = f"초기 자산 매도 주문 체결\n수량: {initial_coin_balance:.8f}\nRSI: {rsi:.2f}"
                        print(message)
                        api.send_slack_message(slack_trade_channel, message)
                        has_initial_coin[currency] = False
                        asset_info = api.get_asset_info()
                        notifier.send_asset_info(asset_info, limit_amount, rsi_check, position_tracker)

                # 매수 진행
                if buy_signal and new_rsi not in rsi_check[ticker]:
                    asset_info = api.get_asset_info()
                    position_size = trader.position_size(new_rsi)*limit_amount[ticker]
                    try:
                        if position_size > 0 and asset_info['krw_balance'] >= position_size and asset_info['krw_balance']*position_size > 5000:
                            order = upbit.buy_market_order(ticker, position_size)
                            message = f"{ticker}매수 주문 완료. 현재가격: {current_price}"
                            print(message)
                            api.send_slack_message(slack_trade_channel, message)
                            time.sleep(10)
                            if order:
                                # 실제 체결된 정보 가져오기
                                executed_order = upbit.get_order(order['uuid'])
                                executed_price = float(executed_order['trades'][0]['price'])
                                buy_amount = round(position_size / executed_price, 8)

                                # rsi 매매여부 체크(매수 시 추가)
                                position_tracker[ticker][new_rsi] = buy_amount
                                rsi_check[ticker].append(new_rsi)

                                message = f"""
{ticker}매수 주문 체결
체결가격: {executed_price:,.0f}원
체결수량: {buy_amount:.8f}
RSI: {new_rsi:.2f}
포지션 현황: {position_tracker[ticker]}
"""
                                print(message)
                                api.send_slack_message(slack_trade_channel, message)
                                asset_info = api.get_asset_info()
                                notifier.send_asset_info(asset_info, limit_amount, rsi_check, position_tracker)
                    except Exception as e:
                        print(f"매수 주문 중 오류: {str(e)}")
                        api.send_slack_message(f"매수 주문 중 오류: {str(e)}", slack_error_channel)

                # 매도 진행
                elif sell_signal and new_rsi in rsi_check[ticker]:
                    try:
                        asset_info = api.get_asset_info()
                        sell_amount = position_tracker[ticker][new_rsi]

                        if sell_amount > 0:
                            order = upbit.sell_market_order(ticker, sell_amount)
                            message = f"{ticker}매도 주문 완료. 현재가격: {current_price}"
                            print(message)
                            api.send_slack_message(slack_trade_channel, message)
                            time.sleep(10)
                            if order:
                                del position_tracker[ticker][new_rsi]
                                rsi_check[ticker].remove(new_rsi)

                                message = f"""
{ticker}매도 주문 체결
수량: {sell_amount:.8f}
RSI: {rsi:.2f}
{rsi_check}
"""
                                api.send_slack_message(slack_trade_channel, message)
                                asset_info = api.get_asset_info()
                                notifier.send_asset_info(asset_info, limit_amount, rsi_check, position_tracker)
                    except Exception as e:
                        print(f"{ticker}의 매도 주문 중 오류: {str(e)}")
                        api.send_slack_message(f"{ticker}의 매도 주문 중 오류: {str(e)}", slack_error_channel)

                elif current_price < asset_info['coin_info'][currency]['avg_price'] * config.stop_loss:
                    print(f"{ticker}의 손실이 {config.stop_loss * 100}% 이상 발생했습니다. 매도 주문 진행중...")
                    sell_amount = asset_info['coin_info'][currency]['balance']
                    order = upbit.sell_market_order(ticker, sell_amount)
                    message = f"{ticker}매도 주문 완료. 현재가격: {current_price}"
                    print(message)
                    api.send_slack_message(slack_trade_channel, message)
                    time.sleep(10)
                    if order:
                        position_tracker[ticker] = {}
                        rsi_check[ticker] = []
                        message = f"""
{ticker} 손절매 완료
포지션 초기화 완료
"""
                        api.send_slack_message(slack_trade_channel, message)
                        asset_info = api.get_asset_info()
                        notifier.send_asset_info(asset_info, limit_amount, rsi_check, position_tracker)

                else:
                    print(f"{ticker}의 매수/매도 신호가 없습니다. 기회 탐색중... rsi: {rsi}")

            # 10초간 대기
            time.sleep(10)

        except Exception as e:
            print(f"메인 루프 오류: {str(e)}")
            api.send_slack_message(f"메인 루프 오류: {str(e)}", slack_error_channel)

if __name__ == "__main__":
    main()
