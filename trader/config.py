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
        # 초기 자산
        self.initial_asset = os.getenv("INITIAL_ASSET")
        # 테스트 여부
        self.verify()

    def verify(self):
        if not self.upbit_access_key or not self.upbit_secret_key:
            raise ValueError("UPBIT_ACCESS_KEY 또는 UPBIT_SECRET_KEY가 설정되지 않았습니다")
        if not self.slack_api_token:
            raise ValueError("SLACK_API_TOKEN이 설정되지 않았습니다")
        if not self.slack_trade_channel:
            raise ValueError("SLACK_TRADE_CHANNEL이 설정되지 않았습니다") 
        if not self.slack_error_channel:
            raise ValueError("SLACK_ERROR_CHANNEL이 설정되지 않았습니다")
        if not self.slack_asset_channel:
            raise ValueError("SLACK_ASSET_CHANNEL이 설정되지 않았습니다")
        if not self.coin_ticker:
            raise ValueError("COIN_TICKER가 설정되지 않았습니다")

if __name__ == "__main__":
    print("config 테스트")
    config = Config()
