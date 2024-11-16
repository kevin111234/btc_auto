import api

class Notifier:
    def __init__(self):
        self.api = api.API()

    def create_asset_report(self):
        asset_info = self.api.get_asset_info()
        limit_amounts = self.api.get_limit_amounts()
        """
        자산 현황 보고서를 생성하는 메서드
        
        Args:
            asset_info (dict): 자산 정보가 담긴 딕셔너리
            limit_amounts (dict): 코인별 투자한도가 담긴 딕셔너리
            
        Returns:
            str: 포맷팅된 자산 보고서 메시지
        """
        message = """
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
코인별 투자한도: {limit_amounts.get(f'KRW-{currency}', 0):,.0f}원
──────────────
"""
        message += f"""
💵 총 자산: {asset_info['total_asset']:,.0f}원
💵 전체 수익률: {((asset_info['total_asset'] - 200000) / 200000 * 100):.2f}%
──────────────
"""
        return message
    
    def report_asset_info(self):
        """
        자산 정보를 조회하고 슬랙으로 보고하는 메서드
        """
        try:
            asset_info = self.api.get_asset_info()
            limit_amounts = self.api.get_limit_amounts()
            
            if not asset_info or not limit_amounts:
                raise ValueError("자산 정보 또는 투자한도 조회 실패")
                
            message = self.create_asset_report(asset_info, limit_amounts)
            self.api.send_slack_message(self.api.config.slack_asset_channel, message)
            
        except Exception as e:
            error_msg = f"자산 보고 중 오류 발생: {str(e)}"
            self.api.send_slack_message(self.api.config.slack_error_channel, error_msg)

    def create_trade_report(self):
        message = """
📈 거래 보고
──────────────

"""
