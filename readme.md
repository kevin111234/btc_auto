# 코인 자동투자 프로그램 제작
1. 환경변수에 아래 변수를 저장해 두고 불러와서 활용할 것.
  A. UPBIT_ACCESS_KEY
  B. UPBIT_SECRET_KEY
  C. SLACK_API_TOKEN
  D. SLACK_CHANNEL_ID
  E. COIN_TICKER
2. UPBIT API를 활용하여 자산 조회, 매수/매도 주문을 실행할 것.
3. SLACK API를 활용하여 투자상황 로깅할 것.
4. 여러 기술적 지표를 분석하고, 이들을 적절히 조합하여 사용할 것. 선행지표와 후행지표를 모두 각 장점에 맞게 적용하여 투자에 활용할 것.
5. 코드 흐름은 아래와 같이 진행됩니다.
  A. 기존 자산 확인 후 손절 가격, 이익 실현 가격 저장 후 포지션 정보 출력
  B. 반복문 시작 - 데이터 수집
  C. 매수, 매도 조건 판단
  D. 홀수 번째 매도/매수 시 보유자산의 절반만, 짝수 번째 매도/매수 시 보유자산 전체로 주문
  E. 매수 조건 충족 시 희망가격 설정 후 해당 가격의 1.005배로 지정가 주문
  F. 10초간 대기 후 주문 체결 확인. 체결되지 않은 경우 주문취소
  G. 매도 조건 3가지 (1. 기술적 지표 매도, 2. 이익 실현 매도, 3. 손절 매도) 판단 후 시장가 주문
  H. 10초간 대기 후 매도 실현 확인, 포지션 정보 변경
  I. 매수/매도 조건 실현 안될 시 "홀드" 출력 후 10초 대기
  J. 조건문 종료 - 20초

---
## 매수/매도 조건 정리
### **1. 전략 개요**

- **1분봉 차트에서 매매 신호 포착**: **RSI**, **볼린저 밴드**, **%B 지표**를 사용하여 핵심 매매 신호를 탐색합니다.
- **보조 지표를 활용한 포지션 크기 조절**: **거래량**과 **OBV** 등의 보조 지표에 스코어를 매겨, 전체 자본의 일정 비율(점수/만점)만큼 매수/매도합니다.
- **리스크 관리**: **손절매**와 **이익 실현** 지점을 설정하여 리스크를 관리합니다.

---

### **2. 1분봉 차트에서 매매 신호 포착 및 포지션 크기 결정**

#### **핵심 매매 조건 (매매 결정에 사용)**

**매수 조건**:

1. **RSI**가 **30 이하**에서 상승 반전.
2. 가격이 **볼린저 밴드 하단**을 터치하거나 하향 돌파 후 반등.
3. **%B 지표**가 **0 이하**에서 상승.

**매도 조건**:

1. **RSI**가 **70 이상**에서 하락 반전.
2. 가격이 **볼린저 밴드 상단**을 터치하거나 상향 돌파 후 하락.
3. **%B 지표**가 **1 이상**에서 하락.

**핵심 조건이 모두 충족될 때 매매를 실행합니다.**

#### **보조 지표 스코어링 시스템 (포지션 크기 결정에 사용)**

**사용 지표**:

- **거래량**
- **OBV (On-Balance Volume)**

**스코어링 방법**:

- 각 보조 지표에 대해 **0점**에서 **2점**까지 부여합니다.
  - **거래량**:
    - 평균 거래량보다 낮으면 **0점**.
    - 평균 거래량과 비슷하면 **1점**.
    - 평균 거래량보다 높으면 **2점**.
  - **OBV**:
    - 추세 변화 없음 또는 불리한 방향이면 **0점**.
    - 약간의 추세 변화가 있으면 **1점**.
    - 유리한 방향으로 강한 추세 변화가 있으면 **2점**.

**포지션 크기 결정**:

- 보조 지표의 총합 스코어에 따라 전체 자산의 일정 비율로 포지션 크기를 결정합니다.
  - **총 스코어 0점**: 포지션 진입을 보류하거나 최소 포지션 크기로 진입.
  - **총 스코어 N점 (N>0)**: 전체 자산의 **N*25%**만큼 매수/매도.

---

### **3. 리스크 관리**

**손절매 설정**:

- **ATR (평균진폭지수)**를 활용하여 손절매 지점을 설정합니다.
- **매수 포지션**: 진입 가격에서 최근 스윙 로우(swing low) 아래에 손절매 설정.
- **매도 포지션**: 진입 가격에서 최근 스윙 하이(swing high) 위에 손절매 설정.

**이익 실현 설정**:

- **리스크 대비 보상 비율**을 **1:2 이상**으로 설정합니다.
- **볼린저 밴드의 반대편** 또는 **주요 지지/저항 수준**을 목표가로 설정합니다.

---

### **4. 거래 관리**

**실행 시간대**:

- 시간대 구분 없이 **24시간 전략을 실행**합니다.

**모니터링 및 조정**:

- 포지션 진입 후 시장 변동성을 모니터링하고, 필요 시 손절매 지점을 조정합니다.
- **트레일링 스탑**을 활용하여 이익을 보호합니다.

**거래 종료**:

- 설정한 **이익 실현 지점** 또는 **손절매 지점**에 도달하면 포지션을 청산합니다.
- **반대 신호**가 발생하면 포지션을 재평가하고 필요 시 청산합니다.

---

### **5. 전략 실행 단계 요약**

1. **1분봉에서 핵심 매매 신호 탐색**:
   - **RSI**, **볼린저 밴드**, **%B 지표**의 핵심 조건이 모두 충족되는지 확인합니다.

2. **보조 지표 스코어링 및 포지션 크기 결정**:
   - **거래량**과 **OBV**에 스코어를 부여하여 총합 스코어를 계산합니다.
   - 총합 스코어에 따라 포지션 크기를 결정합니다.

3. **포지션 진입 및 리스크 관리 설정**:
   - 손절매와 이익 실현 지점을 설정하고 포지션에 진입합니다.

4. **거래 모니터링 및 종료**:
   - 시장 상황을 모니터링하고, 설정한 조건에 따라 포지션을 관리합니다.

---

## **구현해야 할 함수 목록 및 기능 설명**

### **1. 환경 설정 및 초기화 관련 함수**

**1.1 환경 변수 로드**

- **`load_env_variables()`**
  - **설명**: 환경 변수에서 필요한 설정 값과 API 키를 불러옵니다.
  - **입력값**: 없음
  - **출력값**: 환경 변수들의 딕셔너리 (`config`)

**1.2 API 클라이언트 초기화**

- **`initialize_upbit_client(access_key, secret_key)`**
  - **설명**: UPBIT API를 사용하기 위한 클라이언트를 초기화합니다.
  - **입력값**: `access_key`, `secret_key`
  - **출력값**: UPBIT API 클라이언트 객체

- **`initialize_slack_client(slack_api_token)`**
  - **설명**: SLACK API를 사용하기 위한 클라이언트를 초기화합니다.
  - **입력값**: `slack_api_token`
  - **출력값**: SLACK API 클라이언트 객체

---

### **2. 데이터 수집 및 지표 계산 관련 함수**

**2.1 시장 데이터 수집**

- **`fetch_market_data(ticker, interval, count)`**
  - **설명**: 지정된 코인의 시장 데이터를 수집합니다.
  - **입력값**: `ticker`(코인 티커), `interval`(봉 간격), `count`(가져올 봉의 개수)
  - **출력값**: 시장 데이터(DataFrame 또는 리스트)

**2.2 기술적 지표 계산**

- **`calculate_rsi(data, period)`**
  - **설명**: RSI 지표를 계산합니다.
  - **입력값**: `data`(가격 데이터), `period`(기간)
  - **출력값**: RSI 값 시리즈

- **`calculate_bollinger_bands(data, period, num_std_dev)`**
  - **설명**: 볼린저 밴드 상단, 중간, 하단을 계산합니다.
  - **입력값**: `data`, `period`, `num_std_dev`(표준편차 배수)
  - **출력값**: 볼린저 밴드 값 딕셔너리

- **`calculate_percent_b(data, bollinger_bands)`**
  - **설명**: %B 지표를 계산합니다.
  - **입력값**: `data`, `bollinger_bands`
  - **출력값**: %B 값 시리즈

- **`calculate_obv(data)`**
  - **설명**: OBV 지표를 계산합니다.
  - **입력값**: `data`
  - **출력값**: OBV 값 시리즈

- **`calculate_atr(data, period)`**
  - **설명**: ATR 지표를 계산합니다.
  - **입력값**: `data`, `period`
  - **출력값**: ATR 값 시리즈

- **`get_swing_high_low(data)`**
  - **설명**: 최근 스윙 하이(swing high)와 스윙 로우(swing low)를 찾습니다.
  - **입력값**: `data`
  - **출력값**: 스윙 하이, 스윙 로우 값

---

### **3. 매매 신호 생성 및 스코어링 관련 함수**

**3.1 매매 신호 생성**

- **`generate_buy_signal(indicators)`**
  - **설명**: 매수 조건을 확인하여 매수 신호를 생성합니다.
  - **입력값**: `indicators`(RSI, 볼린저 밴드, %B 지표 등)
  - **출력값**: 매수 신호 (Boolean)

- **`generate_sell_signal(indicators, current_price, stop_loss_price, take_profit_price)`**
  - **설명**: 매도 조건을 확인하여 매도 신호를 생성합니다.
  - **입력값**: `indicators`, `current_price`, `stop_loss_price`, `take_profit_price`
  - **출력값**: 매도 신호 (Boolean)

**3.2 보조 지표 스코어링**

- **`score_volume(data)`**
  - **설명**: 거래량을 기반으로 스코어를 계산합니다.
  - **입력값**: `data`
  - **출력값**: 거래량 스코어 (0, 1, 2)

- **`score_obv(obv_series)`**
  - **설명**: OBV를 기반으로 스코어를 계산합니다.
  - **입력값**: `obv_series`
  - **출력값**: OBV 스코어 (0, 1, 2)

- **`calculate_total_score(volume_score, obv_score)`**
  - **설명**: 거래량과 OBV 스코어의 합을 계산합니다.
  - **입력값**: `volume_score`, `obv_score`
  - **출력값**: 총 스코어

---

### **4. 포지션 관리 및 주문 관련 함수**

**4.1 포지션 및 자산 정보 조회**

- **`get_current_balance(upbit_client, ticker)`**
  - **설명**: 현재 보유 자산 및 잔액을 조회합니다.
  - **입력값**: `upbit_client`, `ticker`
  - **출력값**: 잔액 정보 딕셔너리

- **`update_position_info(position_info, trade_info)`**
  - **설명**: 거래 이후 포지션 정보를 업데이트합니다.
  - **입력값**: 기존 `position_info`, 새로운 `trade_info`
  - **출력값**: 업데이트된 `position_info`

**4.2 주문 실행**

- **`calculate_order_size(total_score, balance, trade_count)`**
  - **설명**: 스코어와 거래 횟수에 따라 주문 수량을 계산합니다.
  - **입력값**: `total_score`, `balance`, `trade_count`
  - **출력값**: 주문 수량

- **`place_limit_buy_order(upbit_client, ticker, price, volume)`**
  - **설명**: 지정가 매수 주문을 실행합니다.
  - **입력값**: `upbit_client`, `ticker`, `price`, `volume`
  - **출력값**: 주문 ID

- **`place_market_sell_order(upbit_client, ticker, volume)`**
  - **설명**: 시장가 매도 주문을 실행합니다.
  - **입력값**: `upbit_client`, `ticker`, `volume`
  - **출력값**: 주문 ID

- **`check_order_status(upbit_client, order_id)`**
  - **설명**: 주문의 체결 상태를 확인합니다.
  - **입력값**: `upbit_client`, `order_id`
  - **출력값**: 체결 여부 (Boolean)

- **`cancel_order(upbit_client, order_id)`**
  - **설명**: 미체결 주문을 취소합니다.
  - **입력값**: `upbit_client`, `order_id`
  - **출력값**: 취소 결과

**4.3 손절매 및 이익 실현 설정**

- **`set_stop_loss_price(entry_price, swing_low)`**
  - **설명**: 매수 포지션의 손절매 가격을 설정합니다.
  - **입력값**: `entry_price`, `swing_low`
  - **출력값**: 손절매 가격

- **`set_take_profit_price(entry_price, risk_reward_ratio)`**
  - **설명**: 매수 포지션의 이익 실현 가격을 설정합니다.
  - **입력값**: `entry_price`, `risk_reward_ratio`
  - **출력값**: 이익 실현 가격

---

### **5. 로깅 및 모니터링 관련 함수**

**5.1 SLACK 로깅**

- **`send_slack_message(slack_client, channel_id, message)`**
  - **설명**: SLACK 채널로 메시지를 전송합니다.
  - **입력값**: `slack_client`, `channel_id`, `message`
  - **출력값**: 전송 결과

**5.2 로그 기록**

- **`log_trade(action, price, volume, message)`**
  - **설명**: 거래 정보를 로컬 파일이나 데이터베이스에 기록합니다.
  - **입력값**: `action`(매수/매도), `price`, `volume`, `message`
  - **출력값**: 로그 기록 결과

---

### **6. 유틸리티 함수**

**6.1 시간 지연**

- **`wait(seconds)`**
  - **설명**: 지정된 시간 동안 실행을 일시 정지합니다.
  - **입력값**: `seconds`
  - **출력값**: 없음

**6.2 거래 횟수 관리**

- **`increment_trade_count(trade_count)`**
  - **설명**: 거래 횟수를 증가시킵니다.
  - **입력값**: `trade_count`
  - **출력값**: 증가된 `trade_count`

---

### **7. 메인 루프 및 실행 흐름 관련 함수**

**7.1 메인 실행 함수**

- **`main_loop()`**
  - **설명**: 전체 전략을 실행하는 메인 루프 함수입니다. 위에서 정의한 함수들을 순서대로 호출하여 전략을 실행합니다.
  - **입력값**: 없음 (초기 설정은 함수 내부 또는 글로벌 변수로 처리)
  - **출력값**: 없음

**7.2 전략 실행 단계별 함수**

- **`initialize_strategy()`**
  - **설명**: 전략 실행 전에 필요한 초기 설정과 변수를 초기화합니다.
  - **입력값**: 없음
  - **출력값**: 초기화된 변수들

- **`execute_trade_decision()`**
  - **설명**: 매수 또는 매도 결정을 실행합니다.
  - **입력값**: 지표와 매매 신호들
  - **출력값**: 거래 실행 결과

---

### **8. 예외 처리 및 오류 관리**

**8.1 API 오류 처리**

- **`handle_api_error(error)`**
  - **설명**: API 호출 중 발생한 오류를 처리하고 로깅합니다.
  - **입력값**: `error` 객체
  - **출력값**: 없음

**8.2 일반 오류 처리**

- **`handle_general_exception(exception)`**
  - **설명**: 일반적인 예외를 처리하고 프로그램이 중단되지 않도록 합니다.
  - **입력값**: `exception` 객체
  - **출력값**: 없음

---

### **9. 설정 및 구성 관련 함수**

**9.1 설정 값 로드**

- **`load_strategy_config()`**
  - **설명**: 전략 실행에 필요한 추가 설정 값을 파일이나 데이터베이스에서 로드합니다.
  - **입력값**: 없음
  - **출력값**: 설정 값 딕셔너리

---

### **10. 리스크 관리 강화 함수**

**10.1 트레일링 스탑 설정**

- **`adjust_trailing_stop(current_price, trailing_stop_value)`**
  - **설명**: 현재 가격에 따라 트레일링 스탑 가격을 조정합니다.
  - **입력값**: `current_price`, `trailing_stop_value`
  - **출력값**: 새로운 손절매 가격

**10.2 최대 손실 한도 체크**

- **`check_max_drawdown(balance, max_drawdown_limit)`**
  - **설명**: 최대 손실 한도를 초과했는지 확인하고, 초과 시 전략을 일시 중지합니다.
  - **입력값**: `balance`, `max_drawdown_limit`
  - **출력값**: 전략 실행 여부 (Boolean)

---

### **11. 시장 상황 분석 함수**

**11.1 시장 변동성 체크**

- **`check_market_volatility(data)`**
  - **설명**: 시장의 변동성을 분석하여 거래 실행 여부를 결정합니다.
  - **입력값**: `data`
  - **출력값**: 변동성 지표 값

**11.2 시간대별 거래량 분석**

- **`analyze_time_based_volume(data)`**
  - **설명**: 특정 시간대의 거래량을 분석하여 전략에 반영합니다.
  - **입력값**: `data`
  - **출력값**: 시간대별 거래량 패턴

---

### **함수들의 실행 흐름 요약**

1. **초기화 단계**
   - `load_env_variables()`: 환경 변수 로드
   - `initialize_upbit_client()`, `initialize_slack_client()`: API 클라이언트 초기화
   - `load_strategy_config()`: 추가 설정 값 로드
   - `initialize_strategy()`: 전략 초기화

2. **메인 루프 (`main_loop()`)**
   - **반복 시작**
     - `fetch_market_data()`: 시장 데이터 수집
     - **지표 계산**
       - `calculate_rsi()`, `calculate_bollinger_bands()`, `calculate_percent_b()`, `calculate_obv()`, `calculate_atr()`
     - **매매 신호 생성**
       - `generate_buy_signal()`, `generate_sell_signal()`
     - **보조 지표 스코어링**
       - `score_volume()`, `score_obv()`, `calculate_total_score()`
     - **포지션 크기 결정**
       - `calculate_order_size()`
     - **매매 실행**
       - 매수: `place_limit_buy_order()`, `wait()`, `check_order_status()`, `cancel_order()`
       - 매도: `place_market_sell_order()`, `wait()`, `check_order_status()`
     - **포지션 정보 업데이트**
       - `update_position_info()`
     - **리스크 관리**
       - `set_stop_loss_price()`, `set_take_profit_price()`, `adjust_trailing_stop()`
     - **로깅 및 모니터링**
       - `log_trade()`, `send_slack_message()`
     - **예외 처리**
       - `handle_api_error()`, `handle_general_exception()`
     - **대기 및 다음 반복 준비**
       - `wait()`
   - **반복 종료 또는 지속**

3. **종료 또는 전략 재평가**
   - 필요 시 `check_max_drawdown()` 등을 통해 전략을 일시 중지하거나 종료
