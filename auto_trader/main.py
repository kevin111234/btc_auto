from config import Config
from api import API
from notifier import Notifier
from indicator import Indicator
from trader import Trader
import time
from datetime import datetime

def main():
    config = Config()
    api = API()
    notifier = Notifier()
    indicator = Indicator()
    limit_amounts_per_coin = {}
    trade_check_per_coin = {}

    # 초기 자산 현황 보고
    initial_asset_info = api.get_asset_info()
    initial_limit_amounts = api.get_limit_amount()  # Dict[int, float] # new_rsi: buy_amount
    notifier.report_asset_info(initial_asset_info, initial_limit_amounts)

    for currency in config.coin_ticker:
        limit_amounts_per_coin[currency] = initial_limit_amounts[currency]
        trade_check_per_coin[currency] = {}

    while True:
        try:
            current_asset_info = api.get_asset_info()
            current_time = datetime.now()
            if current_time.minute in [0, 30]:
                if not status_sent:
                    notifier.report_asset_info(current_asset_info, limit_amounts_per_coin)
                    status_sent = True
            else:
                status_sent = False
            
            # 현재 구매한 자산이 없을 때 자산데이터 조회 후 구매한도 재설정
            all_empty = all(len(trades) == 0 for trades in trade_check_per_coin.values())
            if all_empty:
                limit_amounts_per_coin = api.get_limit_amount()
                if current_asset_info is None:
                    notifier.report_error("main", "자산 정보 조회 실패, 10초 대기 후 다시 시도합니다...")
                    time.sleep(10)
                    continue

            for currency in config.coin_ticker:
                current_price = api.get_current_price(currency)
                trader = Trader(currency)
                buy_signal, sell_signal, new_rsi, rsi = trader.signal_check(current_asset_info)
                # 초기 자산 정리
                initial_avg_price = initial_asset_info['coin_info'][currency]['avg_price']
                initial_profit_rate = ((current_price - initial_avg_price) / initial_avg_price * 100) if initial_avg_price > 0 else 0
                initial_balance = initial_asset_info['coin_info'][currency]['balance']
                if initial_balance > 0 and rsi >= 70 and initial_profit_rate >= 0.5 :
                    order = api.upbit.sell_market_order(currency, initial_balance)
                    time.sleep(10)
                    if order:
                        executed_order = api.upbit.get_order(order['uuid'])
                        executed_price = float(executed_order['trades'][0]['price'])
                        notifier.report_trade_info(currency, executed_price, initial_balance, rsi)
                        del trade_check_per_coin[currency]
                        current_asset_info = api.get_asset_info()
                        notifier.report_asset_info(current_asset_info, limit_amounts_per_coin)

                if buy_signal and new_rsi not in trade_check_per_coin[currency]:
                    position_size = indicator.get_position_size(new_rsi)
                    if position_size > 0 and current_asset_info['krw_balance'] >= position_size:
                        order = api.upbit.buy_market_order(currency, position_size)
                        time.sleep(10)
                        if order:
                            executed_order = api.upbit.get_order(order['uuid'])
                            executed_price = float(executed_order['trades'][0]['price'])
                            
                            buy_amount = round(position_size / executed_price, 8)
                            notifier.report_trade_info(currency, executed_price, buy_amount, rsi)
                            trade_check_per_coin[currency][new_rsi] = buy_amount

                elif sell_signal and new_rsi in trade_check_per_coin[currency]:
                    order = api.upbit.sell_market_order(currency, trade_check_per_coin[currency][new_rsi])
                    time.sleep(10)
                    if order:
                        executed_order = api.upbit.get_order(order['uuid'])
                        executed_price = float(executed_order['trades'][0]['price'])
                        notifier.report_trade_info(currency, executed_price, trade_check_per_coin[currency][new_rsi], rsi)
                        del trade_check_per_coin[currency][new_rsi]
                        current_asset_info = api.get_asset_info()
                        notifier.report_asset_info(current_asset_info, limit_amounts_per_coin)

                else:
                    print(f"{currency}에 대한 매매 신호가 없습니다. rsi: {rsi}")
                
            time.sleep(10)
        except Exception as e:
            notifier.report_error("main", str(e))



if __name__ == "__main__":
    main()
