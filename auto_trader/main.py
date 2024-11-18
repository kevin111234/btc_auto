import config
import api
import notifier
import indicator

def main():
    config = config.Config()
    api = api.API()
    notifier = notifier.Notifier()
    indicator = indicator.Indicator()
    limit_amounts_per_coin = {}
    trade_check_per_coin = {}

    # 초기 자산 현황 보고
    initial_asset_info = api.get_asset_info()
    initial_limit_amounts = api.get_limit_amount() # type: dict
    notifier.report_asset_info(initial_asset_info, initial_limit_amounts)

    for currency in config.coin_ticker:
        limit_amounts_per_coin[currency] = initial_limit_amounts[currency]
        trade_check_per_coin[currency] = {}

    while True:
        current_asset_info = api.get_asset_info()




if __name__ == "__main__":
    main()
