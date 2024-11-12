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
TICKERS = ['KRW-BTC', 'KRW-ETH']

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
    rs = pd.Series(avg_gain_list, index=delta.index[n:]) / pd.Series(avg_loss_list, index=delta.index[n:])
    rsi = 100 - (100 / (1 + rs))

    # 볼린저 밴드 계산
    rolling_mean = df['close'].rolling(window=20).mean()
    rolling_std = df['close'].rolling(window=20).std()
    upper_band = rolling_mean + (rolling_std * 2)
    lower_band = rolling_mean - (rolling_std * 2)

    return rsi.iloc[-1], upper_band.iloc[-1], rolling_mean.iloc[-1], lower_band.iloc[-1]

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
      return None
