import config
import api
import notifier
import indicator
import trader

def main():
    config = config.Config()
    api = api.API(config)
    notifier = notifier.Notifier(config, api)
    indicator = indicator.Indicator(config, api)
    trader = trader.Trader(config, api, notifier, indicator)

if __name__ == "__main__":
    main()
