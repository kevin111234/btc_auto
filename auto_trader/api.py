import pyupbit
import slack
from config import Config

class API:
    def __init__(self):
        self.config = Config()
        self.upbit = pyupbit.Upbit(self.config.upbit_access_key, self.config.upbit_secret_key)
        self.slack = slack.WebClient(token=self.config.slack_api_token)

    def send_slack_message(self, channel_id, message):
        try:
            self.slack.chat_postMessage(channel=channel_id, text=message)
        except Exception as e:
            print(f"Error sending message: {e}")

    def get_current_price(self, ticker):
        try:
            return pyupbit.get_current_price(ticker)
        except Exception as e:
            print(f"Error getting current price: {e}")

    def get_ohlcv(self, ticker, interval, count=100):
        try:
            return pyupbit.get_ohlcv(ticker, interval, count)
        except Exception as e:
            print(f"Error getting OHLCV: {e}")

if __name__ == "__main__":
    print("api 테스트")
    api = API()
