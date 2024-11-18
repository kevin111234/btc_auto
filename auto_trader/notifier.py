from api import API
from config import Config
from datetime import datetime

class Notifier:
    def __init__(self):
        self.api = API()
        self.config = Config()

    def create_error_report(self, error_type, error_message, additional_info=None):
        """
        에러 보고서를 생성하는 메서드
        """
        try:
            # 기본 에러 정보
            message = f"""
⚠️ 에러 발생
──────────────
🔴 에러 유형: {error_type}
🔴 에러 내용: {error_message}
🔴 발생 시간: {self.api.get_current_time()}
──────────────"""

            # 에러 상세 정보 추가
            if isinstance(error_message, Exception):
                message += f"\n🔍 에러 클래스: {error_message.__class__.__name__}"
                message += f"\n🔍 에러 위치: {getattr(error_message, '__traceback__', '알 수 없음')}"

            # 추가 정보 처리
            if additional_info:
                message += "\n📌 추가 정보:"
                for key, value in additional_info.items():
                    # 값이 딕셔너리인 경우 더 자세히 표시
                    if isinstance(value, dict):
                        message += f"\n• {key}:"
                        for sub_key, sub_value in value.items():
                            message += f"\n  - {sub_key}: {sub_value}"
                    else:
                        message += f"\n• {key}: {value}"
                message += "\n──────────────"

            return message
        except Exception as e:
            # 에러 보고서 생성 자체에서 에러가 발생한 경우
            return f"❌ 에러 보고서 생성 실패: {str(e)}\n원본 에러: {error_type} - {error_message}"

    def report_error(self, error_type, error_message, additional_info=None):
        """
        에러 정보를 슬랙으로 보고하는 메서드
        """
        try:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 기본 추가 정보 설정
            if additional_info is None:
                additional_info = {}
            
            # 시스템 정보 추가
            additional_info.update({
                "시간": current_time,
                "에러 발생 위치": self._get_caller_info()
            })

            message = self.create_error_report(error_type, error_message, additional_info)
            self.api.send_slack_message(self.config.slack_error_channel, message)
        except Exception as e:
            # 최후의 수단으로 최소한의 에러 정보라도 전송
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            fallback_message = f"""
❌ 치명적 오류: 에러 보고 실패
──────────────
발생 시간: {current_time}
원본 에러: {error_type}
에러 내용: {error_message}
──────────────
에러 보고 실패 사유: {str(e)}
"""
            try:
                self.api.send_slack_message(self.config.slack_error_channel, fallback_message)
            except:
                print("CRITICAL: 슬랙 메시지 전송 완전 실패")
                print(fallback_message)

    def _get_caller_info(self):
        """
        에러가 발생한 위치 정보를 추출하는 헬퍼 메서드
        """
        import inspect
        stack = inspect.stack()
        # 현재 함수와 호출자를 건너뛰고 실제 에러 발생 위치 확인
        for frame in stack[2:]:
            filename = frame.filename
            lineno = frame.lineno
            function = frame.function
            if 'auto_trader' in filename:  # 프로젝트 관련 파일만 추적
                return f"{filename}:{lineno} in {function}"
        return "알 수 없음"

    def create_asset_report(self, asset_info, limit_amounts):
        """
        자산 현황 보고서를 생성하는 메서드
        
        Args:
            asset_info (dict): 자산 정보가 담긴 딕셔너리
            limit_amounts (dict): 코인별 투자한도가 담긴 딕셔너리
            
        Returns:
            str: 포맷팅된 자산 보고서 메시지
        """
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
코인별 투자한도: {limit_amounts.get(f'KRW-{currency}', 0):,.0f}원
──────────────
"""
        message += f"""
💵 총 자산: {asset_info['total_asset']:,.0f}원
💵 전체 수익률: {((asset_info['total_asset'] - 200000) / 200000 * 100):.2f}%
──────────────
"""
        return message

    def report_asset_info(self, asset_info, limit_amounts):
        """
        자산 정보를 조회하고 슬랙으로 보고하는 메서드
        """
        try:               
            message = self.create_asset_report(asset_info, limit_amounts)
            self.api.send_slack_message(self.config.slack_asset_channel, message)
            
        except Exception as e:
            self.report_error(
                "자산 보고 오류",
                str(e),
                {"시간": self.api.get_current_time()}
            )

    def create_trade_report(self, coin_ticker, executed_price, executed_volume, rsi):
        """
        거래 보고서를 생성하는 메서드
        
        Args:
            coin_ticker (str): 코인 티커
            executed_price (float): 체결 가격
            executed_volume (float): 체결 수량
            rsi (float): RSI 지표값
            
        Returns:
            str: 포맷팅된 거래 보고서 메시지
        """
        asset_info = self.api.get_asset_info()
        message = f"""
📈 [{coin_ticker}] 거래 보고
──────────────
진입가격: {executed_price:,.0f}원
진입수량: {executed_volume:.8f}
거래가격: {executed_price * executed_volume:,.0f}원
RSI: {rsi:.2f}
──────────────
💵 전체 수익률: {((asset_info['total_asset'] - 200000) / 200000 * 100):.2f}%
"""
        return message
    
    def report_trade_info(self, coin_ticker, executed_price, executed_volume, rsi):
        """
        거래 정보를 슬랙으로 보고하는 메서드
        
        Args:
            coin_ticker (str): 코인 티커
            executed_price (float): 체결 가격
            executed_volume (float): 체결 수량
            rsi (float): RSI 지표값
        """
        try:
            message = self.create_trade_report(coin_ticker, executed_price, executed_volume, rsi)
            self.api.send_slack_message(self.config.slack_trade_channel, message)
        except Exception as e:
            self.report_error(
                "거래 보고 오류",
                str(e),
                {
                    "코인": coin_ticker,
                    "가격": executed_price,
                    "수량": executed_volume,
                    "RSI": rsi,
                    "상세 에러": {
                        "에러 타입": type(e).__name__,
                        "에러 메시지": str(e),
                        "발생 위치": self._get_caller_info()
                    }
                }
            )

    def create_initial_asset_report(self, asset_info, limit_amounts):
        message = f"""
📊 초기 자산 보고
──────────────
💰 보유 KRW: {asset_info['krw_balance']:,.0f}원
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
코인별 투자한도: {limit_amounts.get(f'KRW-{currency}', 0):,.0f}원
──────────────
"""
        message += f"""
💵 총 자산: {asset_info['total_asset']:,.0f}원
각 코인별 투자한도: {limit_amounts}
──────────────
"""
        return message

    def report_initial_asset_info(self, asset_info, limit_amounts):
        try:
            message = self.create_initial_asset_report(asset_info, limit_amounts)
            self.api.send_slack_message(self.config.slack_asset_channel, message)
        except Exception as e:
            self.report_error("초기 자산 보고 오류", str(e))
