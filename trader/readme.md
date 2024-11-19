**config.py**
- 환경변수 설정
- 호출 시 from config import Config

**api.py**
- api 연결 및 일부 핵심 기능 구현
- 호출 시 from api import API
- 주요 기능
    - send_slack_message(channel_id, message) >>> channel_id는 config.py에 설정된 값
    - get_current_price(ticker) >>> ticker는 KRW-BTC 등의 형식
    - get_ohlcv(ticker, interval, count) >>> ticker는 KRW-BTC 등의 형식
    - get_asset_info() >>> krw_balance, coin_info(balance, avg_price, current_price, value, profit_rate), total_asset
    - get_limit_amount() >>> {ticker: limit_amount} 형식

**indicator.py**
- 지표 계산 및 시각화
- 호출 시 from indicator import Indicator
    - Indicator(ticker) >>> ticker는 KRW-BTC 등의 형식
- 주요 기능
    - calculate_rsi(data) >>> 데이터에 대한 rsi 계산 data는 get_ohlcv() 반환값
    - calculate_volume_profile(data, num_bins=12, time_period=100) >>> 데이터에 대한 볼륨 프로파일 계산
    - get_new_rsi(data) >>> 데이터에 대한 새로운 rsi 계산 data는 get_ohlcv() 반환값
    - get_volume_profile() >>> poc, support_levels, resistance_levels 반환
    - get_position_size() >>> 포지션 사이즈 반환
**trader.py**
- 거래 신호 확인 및 거래 실행
- 호출 시 from trader import Trader
- 주요 기능
    - signal_check(asset_info) >>> asset_info는 api.get_asset_info() 반환값

**main.py**
- 거래 로직 구현

# 코드 흐름 정리
1. 환경변수 설정 **config.py**
2. 코인 티커 목록 설정 **config.py**
3. api 객체 생성 **api.py**
4. slack 메시지 전송 함수 생성 **api.py**
5. rsi 계산 함수 생성 **indicator.py**
6. rsi 정규화 함수 생성 **indicator.py**
7. 포지션 사이즈 계산 함수 생성 **trader.py**
8. 매매한도 계산 함수 생성 **trader.py**
9. 자산 정보 계산 함수 생성 **trader.py**
10. 자산 정보 전송 함수 생성 **trader.py**
11. 주기적 상태 전송 함수 생성 **trader.py**
12. 메인함수 시작
    a. rsi체크 리스트 초기화
    b. 포지션 트래커 초기화
    c. 초기 자산 정보 조회 **api.py**
    d. 초기 자산 정보 전송 **notifier.py**
    e. 초기 자산 존재여부 및 수량 계산
    f. 메인루프 시작
        - 1. 주기적 상태 전송 30분단위
        - 2. 현재 구매한 자산이 없을 때(rsi체크 리스트가 비어있을 때)
            a. 자산 정보 조회 **api.py**
            b. 매매한도 계산 **api.py**
        - 3. coin_ticker = 'KRW-BTC', currency = 'BTC'
        - 4. 가격 데이터 조회 **api.py**
        - 5. 현재 가격 조회 **api.py**
        - 6. rsi, previous_rsi 계산 **indicator.py**
        - 7. rsi 정규화 **trader.py**
        - 8. 매매 신호 판단 **trader.py**
            a. 매수 신호 판단
            b. 매도 신호 판단
        - 9. 초기 자산 정리
            a. 초기 자산 수량, 수익률 계산
            b. 수익률이 0.5% 이상이고 rsi가 70 이상이면 매도 주문 전송 **trader.py**
            c. 매도 주문 완료 메시지 전송 **api.py**
            d. 매도 주문 채결 확인
            e. 매도 주문 채결 메시지 전송 **notifier.py**
            f. 재실행 방지 **trader.py**
        - 10. 매수 진행
            a. 매수 신호가 존재하고, 해당 rsi가 체크 리스트에 없을 때
            b. 자산 정보 조회 **api.py**
            c. 포지션 사이즈 계산 **trader.py**
            d. 자산 정보 조회 **api.py**
            e. 매수 주문 전송 **api.py**
            f. 매수 주문 완료 메시지 전송 **api.py**
            g. 매수 주문 채결 확인
            h. 매수 주문 채결 메시지 전송 **notifier.py**
            i. 포지션 트래커 업데이트 **trader.py**
            j. rsi 체크 리스트 업데이트 **trader.py**
        - 11. 매도 진행
            a. 매도 신호가 존재하고, 해당 rsi가 체크 리스트에 있을 때
            b. 자산 정보 조회 **api.py**
            c. 포지션 사이즈 계산 **trader.py**
            d. 포지션 사이즈가 0보다 크면 매도 주문 전송 **api.py**
            e. 매도 주문 완료 메시지 전송 **api.py**
            f. 매도 주문 채결 확인
            g. 매도 주문 채결 메시지 전송 **notifier.py**
            h. 포지션 트래커 업데이트 **trader.py**
            i. rsi 체크 리스트 업데이트 **trader.py**
        - 12. 10초 대기
