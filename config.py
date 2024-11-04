import os
from dotenv import load_dotenv

class Config:
    def __init__(self):
        load_dotenv()
        # UPBIT API
        self.UPBIT_ACCESS_KEY = os.getenv('UPBIT_ACCESS_KEY')
        self.UPBIT_SECRET_KEY = os.getenv('UPBIT_SECRET_KEY')

        # SLACK API
        self.SLACK_API_TOKEN = os.getenv('SLACK_API_TOKEN')
        self.SLACK_CHANNEL_ID = os.getenv('SLACK_CHANNEL_ID')

        # Database Configuration
        self.DB_HOST = os.getenv('DB_HOST')
        self.DB_PORT = os.getenv('DB_PORT')
        self.DB_USER = os.getenv('DB_USER')
        self.DB_PASSWORD = os.getenv('DB_PASSWORD')
        self.DB_NAME = os.getenv('DB_NAME')

        # Coin Ticker
        self.COIN_TICKER = os.getenv('COIN_TICKER')

        # Other configurations
        self.TIMEFRAME = '5min'  # 5분봉 기준

        # 초기 설정 검증
        self.validate_config()

    def validate_config(self):
        required_attrs = [
            'UPBIT_ACCESS_KEY', 'UPBIT_SECRET_KEY',
            'SLACK_API_TOKEN', 'SLACK_CHANNEL_ID',
            'DB_HOST', 'DB_PORT', 'DB_USER', 'DB_PASSWORD', 'DB_NAME',
            'COIN_TICKER'
        ]
        for attr in required_attrs:
            if getattr(self, attr) is None:
                raise ValueError(f"환경변수 {attr}가 설정되지 않았습니다.")
            else:
              print(f"환경변수 {attr} 설정완료")
