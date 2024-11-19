from config import Config
from api import API

class Notifier:
    def __init__(self):
        self.config = Config()
        self.api = API()

    def send_asset_info(self, asset_info, limit_amount):
        message = f"""
📊 자산 현황 보고
──────────────
💰 보유 KRW: {asset_info['krw_balance']:,.0f}원
──────────────"""
        for currency, info in asset_info['coin_info'].items():
            message += f"""
🪙 {currency}:
수량: {info['balance']:.8f}
평균매수가: {info['avg_price']:,.0f}원
현재가격: {info['current_price']:,.0f}원
평가금액: {info['value']:,.0f}원
수익률: {info['profit_rate']:.2f}%
코인별 투자한도: {limit_amount.get(f'KRW-{currency}', 0):,.0f}원
──────────────"""
        message += f"""
💵 총 자산: {asset_info['total_asset']:,.0f}원
💵 전체 수익률: {((asset_info['total_asset'] - 200000) / 200000 * 100):.2f}%
──────────────"""
        
        try:
            self.api.send_slack_message(self.config.slack_asset_channel, message)
        except Exception as e:
            print(f"자산 보고 오류: {str(e)}")

    def send_status_update(self, limit_amount, rsi_check, position_tracker):
        asset_info = self.api.get_asset_info()
        if asset_info is None:
            print("자산현황 정보를 가져오는 데 실패했습니다.")
            return
        
        message = f"""
📈 상태 점검 보고서
──────────────
💰 보유 KRW: {asset_info['krw_balance']:,.0f}원
💵 총 자산: {asset_info['total_asset']:,.0f}원
⚖️ 코인당 투자한도: {limit_amount:,.0f}원
──────────────
{position_tracker}
{rsi_check}
──────────────
"""
        for currency, info in asset_info['coin_info'].items():
            message += f"""
🪙 {currency}:
수량: {info['balance']:.8f}
평균매수가: {info['avg_price']:,.0f}원
현재가격: {info['current_price']:,.0f}원
평가금액: {info['value']:,.0f}원
수익률: {info['profit_rate']:.2f}%
──────────────"""
        message += f"""
💵 총 자산: {asset_info['total_asset']:,.0f}원
💵 전체 수익률: {((asset_info['total_asset'] - 200000) / 200000 * 100):.2f}%
──────────────"""
        
        try:
            self.api.send_slack_message(self.config.slack_asset_channel, message)
        except Exception as e:
            print(f"상태점검 보고 오류: {str(e)}")
