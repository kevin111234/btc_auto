class Trader:
    def __init__(self, upbit, slack, tickers):
        self.upbit = upbit
        self.slack = slack
        self.tickers = tickers

# 포지션 트래커
    def position_tracker(self):
        self.position_tracker = {}
        for ticker in self.tickers:
            self.position_tracker[ticker] = {}
        return self.position_tracker
    
    def rsi_check(self):
        self.rsi_check = {}
        for ticker in self.tickers:
            self.rsi_check[ticker] = []
        return self.rsi_check
    
    def add_position(self, ticker, amount, new_rsi):
        self.position_tracker[ticker][new_rsi] = amount
        self.rsi_check[ticker].append(new_rsi)
        return self.position_tracker, self.rsi_check
    
    def remove_position(self, ticker, new_rsi):
        del self.position_tracker[ticker][new_rsi]
        self.rsi_check[ticker].remove(new_rsi)
        return self.position_tracker, self.rsi_check
    
# 초기 자산 관리
    def initial_coin_balance(self, asset_info):
        initial_coin_balance = {}
        for ticker in self.tickers:
            initial_coin_balance[ticker] = asset_info['coin_info'][ticker]['balance']
        return initial_coin_balance

    def has_initial_coin(self, initial_coin_balance):
        # 초기 자산에 코인이 있는지 확인
        has_initial_coin = {}
        for ticker in self.tickers:
            if initial_coin_balance[ticker] > 0:
                has_initial_coin[ticker] = True
        return has_initial_coin

# 매매신호 판단
    def buy_signal(self, rsi, previous_rsi):
        return rsi <= 35 and previous_rsi <= rsi
    
    def sell_signal(self, rsi, previous_rsi, profit_rate):
        return rsi >= 65 and previous_rsi >= rsi and profit_rate >= 0.5
    
    def position_size(self, new_rsi):
        if new_rsi == 20:
            return 0.2
        elif new_rsi == 25:
            return 0.4
        elif new_rsi == 30:
            return 0.3
        elif new_rsi == 35:
            return 0.1
        else:
            return 0.0
