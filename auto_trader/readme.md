# 암호화폐 자동매매 시스템 설계 문서

## 1. 시스템 개요

### 1.1 목적
- 다중 암호화폐에 대한 자동화된 매매 시스템 구현
- RSI 기반의 매매 전략을 통한 수익 창출
- 실시간 모니터링 및 리포팅 시스템 구축

### 1.2 주요 기능
- 복수의 암호화폐 동시 모니터링 및 매매
- RSI 기반 매매 신호 생성
- 자동 손익절 실행
- 실시간 매매 현황 및 자산 상태 리포팅

## 2. 시스템 아키텍처

### 2.1 디렉토리 구조
```
auto_trader/
├── config.py           # 설정 및 상수값
├── api.py              # 주요 기능 구현
├── indicator.py       # 기술적 지표 계산
├── notifier.py        # Slack 알림 관리
├── trader.py          # 주요 트레이딩 로직
└── main.py           # 실행 파일
```

### 2.2 컴포넌트별 주요 기능

#### config.py
```python
class TradeConfig
```

#### api.py
- send_slack_message(channel_id, message)
- get_current_price(ticker)
- get_ohlcv(ticker, interval, count)
- get_asset_info()
- get_limit_amount(ticker)

#### indicator.py
- calculate_rsi(ohlcv)
- calculate_volume_profile(ohlcv, num_bins, time_period)
- get_new_rsi(ohlcv)
- get_volume_profile(ohlcv)
- get_position_size(asset_info, ticker)

#### notifier.py
- create_error_report(error_type, error_message, additional_info)
- report_error(error_type, error_message, additional_info)
- create_asset_report(asset_info, limit_amounts)
- report_asset_info(asset_info, limit_amounts)
- create_trade_report(trade_info)
- report_trade_info(trade_info)

## 3. 주요 프로세스 흐름

### 3.1 초기화 프로세스
1. 환경 설정 로드
2. API 연결 초기화
3. 초기 자산 상태 확인
4. 초기 보고서 생성 및 전송

### 3.2 매매 프로세스
1. 코인별 현재가 및 RSI 계산
2. 매매 신호 확인
3. 포지션 크기 계산
4. 주문 실행
5. 결과 알림 전송

### 3.3 모니터링 프로세스
1. 30분 주기 자산 현황 보고
2. 실시간 매매 기록 전송
3. 에러 발생 시 즉시 알림

## 4. 알림 시스템 상세

### 4.1 매매 알림 (TRADE_CHANNEL)
```
📈 매매 체결 알림
코인: {COIN_TICKER}
유형: 매수/매도
가격: {PRICE}원
수량: {AMOUNT}
RSI: {RSI_VALUE}
```

### 4.2 자산 현황 보고 (REPORT_CHANNEL)
```
📊 자산 현황 보고
──────────────
💰 보유 KRW: {KRW_BALANCE}원
──────────────
🪙 보유 코인:
{COIN_NAME}:
- 수량: {AMOUNT}
- 평균매수가: {AVG_PRICE}원
- 현재가격: {CURRENT_PRICE}원
- 평가금액: {TOTAL_VALUE}원
- 수익률: {PROFIT_RATE}%
──────────────
💵 총 자산: {TOTAL_ASSET}원
```

### 4.3 에러 알림 (ERROR_CHANNEL)
```
⚠️ 에러 발생
시간: {TIMESTAMP}
유형: {ERROR_TYPE}
내용: {ERROR_MESSAGE}
```

## 5. 에러 처리 정책

### 5.1 API 오류
- 최대 3회 재시도
- 재시도 실패 시 에러 채널 알림

### 5.2 주문 실패
- 실패 사유 로깅
- 에러 채널 알림
- 다음 주기까지 해당 코인 거래 중지

### 5.3 크리티컬 에러
- 즉시 프로그램 중단
- 관리자 알림
- 전체 거래 일시 중지

## 6. 구현 우선순위

1. 기본 매매 로직 구현
2. 슬랙 알림 시스템 구축
3. 에러 처리 및 재시도 로직
4. 자산 관리 및 리포팅 시스템
5. 성능 최적화 및 안정화

이 문서는 향후 개발 과정에서 필요에 따라 업데이트될 수 있습니다. 실제 구현 시 발생하는 이슈나 추가 요구사항에 따라 수정될 수 있습니다.