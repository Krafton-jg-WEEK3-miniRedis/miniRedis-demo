# 1번 팀원 Plan.md

## 목표
- 1번 팀원의 역할은 Mini Redis 자체를 구현하는 것이 아니라, 2~4번 팀원이 만든 Mini Redis 프로세스를 실제로 붙여서 시연하고 검증하는 웹 데모 플랫폼을 만드는 것이다.
- 웹에서 `MongoDB 직접 조회`와 `Mini Redis 경유 조회`를 같은 데이터 기준으로 비교한다.
- 구현한 Redis가 정상 동작하는지와 엣지 케이스에서도 문제가 없는지를 QA 시나리오로 실행하고 결과를 시각화한다.
- benchmark와 monitoring 결과를 재현 가능하게 정리하고, README만 보고 발표 데모를 실행할 수 있게 만든다.

## 1번 팀원 역할 정의
- 프론트엔드 담당
  - 데모용 웹 대시보드 구현
  - direct 조회, cache 조회, QA 결과, benchmark 결과, monitoring 결과를 한 화면에서 보여주기
- 백엔드 담당
  - MongoDB 직접 조회 API 구현
  - Mini Redis 호출 API 구현
  - benchmark 실행 API 구현
  - QA 시나리오 실행 API 구현
  - monitoring/metrics 수집 API 구현
- QA 담당
  - Redis 정상 동작 및 엣지 케이스 검증 시나리오 설계
  - 결과를 pass/fail, 응답값, 실패 원인, latency 기준으로 정리
- 발표 담당
  - README에 환경 구성, 실행 방법, benchmark 재현 방법, 발표 흐름 정리

## 진행 현황
- [x] 작업 브랜치 생성 및 이동
- [x] `AGENTS.md`, `docs/기획서.md`, `docs/요구사항.md`, `docs/협업규칙.md` 확인
- [x] 1번 팀원 역할 범위 확정
- [x] Python 프로젝트 구조 설계
- [x] 웹 백엔드 아키텍처 설계
- [x] 웹 프론트 대시보드 설계
- [x] MongoDB direct 조회 경로 설계
- [x] Mini Redis cache 조회 경로 설계
- [x] QA 시나리오 목록 확정
- [x] benchmark 지표 및 재현 방식 확정
- [x] monitoring 지표 및 화면 배치 확정
- [x] README 데모/발표 흐름 설계
- [x] 구현
- [x] 로컬 검증
- [x] 결과 정리

## 구현 계획

### 1. Python 기반 데모 프로젝트 구성
- `pyproject.toml`, `.env.example`, 공통 실행 스크립트, README를 추가한다.
- 웹 서버와 API를 담당하는 Python 애플리케이션 구조를 만든다.
- MongoDB와 Mini Redis 연결 설정을 환경 변수로 분리한다.

### 2. 백엔드 구성
- MongoDB direct 조회 모듈
  - 동일 key 기준으로 MongoDB 문서를 직접 조회
- Mini Redis client 모듈
  - 2~4번 팀원이 만든 Redis 프로세스에 연결
  - RESP2 기반으로 `PING`, `SET`, `GET`, `DEL`, `EXPIRE`, `QUIT`, `EXIT` 호출 가능하도록 구성
- QA runner 모듈
  - 정상/엣지 케이스를 순서대로 실행하고 결과를 JSON으로 반환
- benchmark 모듈
  - 동일 key를 대상으로 direct 조회와 cache 조회를 반복 측정
  - avg/min/max, 가능하면 p95와 req/sec 계산
- metrics collector 모듈
  - latency, throughput, hit/miss, error 수집
  - 가능하면 RSS memory, connection 수, CPU, network rx/tx도 함께 수집

### 3. 프론트엔드 구성
- 단일 대시보드 페이지로 구성한다.
- 섹션은 다음 4개로 나눈다.
  - Lookup 비교 패널
    - 같은 key에 대해 `MongoDB 직접 조회`와 `Mini Redis 경유 조회` 버튼 제공
    - 응답 데이터와 latency를 바로 비교
  - QA 패널
    - 시나리오별 pass/fail, expected/actual, latency, failure reason 표시
  - Benchmark 패널
    - 반복 횟수 입력 후 avg/min/max, req/sec, speedup 표시
  - Monitoring 패널
    - hit/miss, error 수, memory, connections, CPU, network 지표 표시
- 발표용 화면이므로 direct vs cache 차이가 바로 보이도록 카드/표/그래프 중심으로 설계한다.

## API 및 인터페이스 계획
- `GET /api/lookup?key=<key>&mode=mongo|cache`
- `POST /api/qa/run`
- `POST /api/benchmark`
- `GET /api/metrics/current`
- `GET /api/metrics/history`

응답은 모두 JSON으로 통일한다.

## QA 계획
- 정상 동작 검증
  - `PING`
  - `SET` 후 `GET`
  - overwrite 동작
  - 없는 key 조회
  - 여러 key `DEL`
- 엣지 케이스 검증
  - `EXPIRE` 후 lazy expiration
  - `QUIT`/`EXIT`
  - unknown command
  - 인자 수 오류
  - malformed RESP
- QA 결과는 단순 로그가 아니라 웹에서 시각적으로 확인 가능해야 한다.

## Benchmark 계획
- 동일한 데이터셋, 동일한 key 기준으로 direct/cache를 비교한다.
- direct path 반복 측정
- cache path는 warm-up 후 hit 기준 반복 측정
- 결과로 다음 지표를 남긴다.
  - avg/min/max
  - p95 가능 시 추가
  - requests/sec
  - hit/miss count
  - speedup
- 결과는 재현 가능하도록 JSON artifact로 저장한다.

## Monitoring 계획
- 주지표
  - latency
  - requests/sec
  - hit/miss ratio
  - error count
- 보조지표
  - RSS used memory
  - active connections
  - CPU usage
  - network rx/tx
- 발표에서는 latency/throughput/hit-miss를 먼저 보여주고, memory/connections/CPU/network는 보조 설명에 사용한다.

## README 계획
- 환경 설정
- MongoDB 실행 방법
- seed 데이터 적재 방법
- Mini Redis 서버 연결 방법
- 웹 실행 방법
- QA 실행 방법
- benchmark 실행 방법
- monitoring 확인 방법
- 발표 4분 흐름

## 검증 기준
- README만 보고 환경 실행 가능해야 한다.
- 웹에서 같은 key로 Mongo direct와 Redis cache를 비교할 수 있어야 한다.
- QA 결과가 pass/fail로 명확히 보이고, 실패 원인을 확인할 수 있어야 한다.
- benchmark 결과가 재현 가능해야 한다.
- 발표 시 README와 웹 화면만으로 설명 가능해야 한다.

## 가정
- 이 저장소는 1번 팀원 전용이므로 Redis 서버 내부 구현은 하지 않는다.
- Mini Redis 서버 자체는 2~4번 팀원 결과물을 사용한다.
- 서버가 `INFO` 또는 유사 메트릭을 제공하지 않으면, monitoring 일부는 클라이언트 관측값으로 대체한다.
- 핵심 목적은 “Redis 구현 자체”가 아니라 “Redis를 붙여서 검증하고 시연하는 웹 데모”다.

## 검증 결과
- `python3 -m unittest discover -s tests -v` 통과
- `python3 -m compileall demo_benchmark tests` 통과
- `python3 -c 'from demo_benchmark.app import create_app; app = create_app(); print(callable(app))'` 확인 완료

## 변경 파일 요약
- `demo_benchmark/`: Mongo/Redis 연동, QA, benchmark, metrics, WSGI 앱 추가
- `static/`: 발표용 대시보드 UI 추가
- `tests/`: 서비스 및 benchmark 단위 테스트 추가
- `README.md`, `Plan.md`, `.env.example`, `docker-compose.yml`, `pyproject.toml`: 실행/문서/환경 구성 추가

## 남은 리스크
- 실제 Mini Redis 서버가 `EXPIRE`, `QUIT`, `EXIT`, malformed RESP 에러 처리까지 동일하게 지원하는지는 통합 환경에서 추가 확인이 필요하다.
- MongoDB와 실제 Mini Redis 프로세스가 로컬에 없어서 end-to-end 실측 benchmark는 아직 수행하지 못했다.
