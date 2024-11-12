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
