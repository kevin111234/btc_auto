import pyupbit
import slack
from config import Config

class API:
    def __init__(self):
        self.config = Config()
        self.upbit = pyupbit.Upbit(self.config.upbit_access_key, self.config.upbit_secret_key)
        self.slack = slack.WebClient(token=self.config.slack_api_token)
