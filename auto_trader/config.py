import os
from dotenv import load_dotenv

class Config:
    def __init__(self):
        load_dotenv()
        # upbit api 연결
        self.upbit_access_key = os.getenv("UPBIT_ACCESS_KEY")
        self.upbit_secret_key = os.getenv("UPBIT_SECRET_KEY")
        # slack api 연결
        self.slack_api_token = os.getenv("SLACK_API_TOKEN")
        # Trade_channel id
        self.slack_trade_channel = os.getenv("SLACK_TRADE_CHANNEL")
        # Error_channel id
        self.slack_error_channel = os.getenv("SLACK_ERROR_CHANNEL")
        # asset_channel id
        self.slack_asset_channel = os.getenv("SLACK_ASSET_CHANNEL")
        # coin_ticker
        self.coin_ticker = os.getenv("COIN_TICKER").split(" ")

if __name__ == "__main__":
    print("config 테스트")
    config = Config()
