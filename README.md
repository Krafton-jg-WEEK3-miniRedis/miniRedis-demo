# miniRedis-demo

Mini Redis 1번 팀원용 데모/QA 저장소입니다. 이 저장소는 Redis 서버 자체를 구현하지 않고, 2~4번 팀원이 만든 Mini Redis 프로세스를 붙여서 `MongoDB 직접 조회`, `Mini Redis 캐시 조회`, `QA edge case`, `benchmark`, `monitoring`을 웹에서 시연하는 역할을 담당합니다.

## What This Repo Owns

- Python 기반 데모 웹 대시보드
- MongoDB direct read vs Mini Redis cached read 비교 API
- Redis 정상 동작 및 edge case QA 시나리오 러너
- 재현 가능한 benchmark 실행 및 JSON artifact 저장
- 발표 흐름과 데모 방법 문서화

## Project Structure

- `Plan.md`: 1번 팀원 계획 및 진행 현황
- `docs/웹_대시보드_설명.md`: 웹 화면 구성, 컴포넌트 역할, 발표 포인트 정리
- `demo_benchmark/`: 백엔드 앱, Mongo/Redis 어댑터, QA, benchmark, metrics
- `static/`: 데모 대시보드 UI
- `tests/`: 단위 테스트
- `artifacts/`: benchmark 결과 JSON
- `Dockerfile`, `docker-compose.yml`: 테스트 전용 로컬 Docker 실행 설정

## Quick Start

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Configure environment

```bash
cp .env.example .env
export $(grep -v '^#' .env | xargs)
```

`.env`는 `.gitignore`에 포함되어 있으므로 로컬/배포 환경값을 안전하게 분리할 수 있습니다.

기본값은 로컬 대시보드 실행 기준으로 아래처럼 맞춰져 있습니다.

- MongoDB: `mongodb://127.0.0.1:27017/<db-name>`
- Mini Redis host: `127.0.0.1`
- Mini Redis port: `6379`
- 웹 포트: `8000`
- 웹 바인딩 주소: `0.0.0.0`

공유 서버 API를 기준으로 붙을 때는 아래 값을 추가합니다.

- `UPSTREAM_API_BASE_URL=http://211.188.52.76:8088`

이 값이 설정되면 대시보드의 `/api/*` 요청은 로컬 MongoDB/Redis 대신 공유 서버로 프록시됩니다. 즉, 로컬에서 웹 UI만 띄우고 데이터 조회/QA/benchmark는 공유 서버 기준으로 확인할 수 있습니다.

`MINI_REDIS_BACKEND=stub`로 바꾸면 실제 Redis 서버 없이도 UI와 QA 흐름을 로컬에서 검증할 수 있습니다. 발표 전에는 반드시 실제 Mini Redis 프로세스에 맞춰 `tcp` 모드로 다시 확인하세요.

주요 환경 변수:

- `APP_HOST`, `APP_PORT`: 웹 서버 바인딩 주소/포트
- `UPSTREAM_API_BASE_URL`: 공유 서버 API base URL. 설정 시 로컬 API 대신 원격 API 프록시 모드로 동작
- `MONGO_URI`, `MONGO_DB_NAME`, `MONGO_DATABASE`, `MONGO_COLLECTION`: MongoDB 연결 정보
- `SECRET_KEY`: 공유된 Docker 환경 포맷에 맞춘 앱 시크릿 값
- `MINI_REDIS_HOST`, `MINI_REDIS_PORT`, `MINI_REDIS_TIMEOUT`, `MINI_REDIS_BACKEND`: Mini Redis 연결 정보
- `DEMO_DEFAULT_KEY`, `BENCHMARK_DEFAULT_ITERATIONS`, `METRICS_HISTORY_LIMIT`: 데모 기본 동작 값
- `CACHE_TTL_SECONDS`: 캐시에 적재한 데이터의 기본 TTL
- `WARM_CACHE_ON_STARTUP`, `WARM_CACHE_DOC_TYPE`, `WARM_CACHE_LIMIT`: 앱 시작 시 Mongo 데이터를 Redis로 미리 적재할지 여부와 범위

### 3. Run the dashboard

공유 서버 API를 기준으로 로컬에서 대시보드만 실행합니다.

```bash
export $(grep -v '^#' .env | xargs)
mini-redis-demo
```

이후 브라우저에서 [http://127.0.0.1:8000](http://127.0.0.1:8000) 로 접속합니다.

이 경우 UI는 로컬에서 열리지만, API는 `UPSTREAM_API_BASE_URL`로 프록시됩니다.

### 4. Run local Docker for testing

테스트 용도로 로컬 MongoDB와 웹 컨테이너를 함께 띄우려면 아래 명령을 사용합니다.

```bash
docker compose up --build -d web mongo
```

이 compose는 `UPSTREAM_API_BASE_URL`을 강제로 비워서 공유 서버 프록시가 아니라 로컬 Mongo 기준으로 동작하게 합니다.

로그 확인:

```bash
docker compose logs -f web
```

### 5. Seed demo data

```bash
mini-redis-seed --count 20
```

기본 seed 데이터는 중고 매물 20개를 생성합니다.

- 예시 listing key: `listing:1001`
- 예시 search cache key: `market:search:아이폰:성남시 분당구:digital:12`

공유 서버 API를 사용하는 기본 흐름에서는 이 단계가 필수는 아닙니다.

Redis를 미리 채우고 시작하려면 아래 예열 명령도 사용할 수 있습니다.

```bash
mini-redis-warm --doc-type listing --ttl 300
```

### 6. Start Mini Redis

이 저장소는 Mini Redis 서버를 직접 제공하지 않습니다. 2~4번 팀원이 만든 서버를 먼저 실행한 뒤, 아래 환경 변수로 연결합니다.

```bash
export MINI_REDIS_HOST=mini-redis-server
export MINI_REDIS_PORT=6379
export MINI_REDIS_BACKEND=tcp
```

Mini Redis 서버에 직접 붙어야 할 때만 환경에 맞는 호스트로 값을 바꾸면 됩니다.

지원 가정 명령:

- `PING`
- `SET`
- `GET`
- `DEL`
- `EXPIRE`
- `QUIT`
- `EXIT`

## Dashboard Features

현재 대시보드는 `중고나라 스타일 중고거래 플랫폼` 컨셉으로 구성됩니다.

### 좌우 비교형 서비스 화면

- 왼쪽: `MongoDB Direct Experience`
- 오른쪽: `Mini Redis Cached Experience`
- 같은 검색 조건을 두 경로에 동시에 적용하고, 같은 매물 데이터를 각각의 서비스 UI로 렌더링합니다.

각 섹션의 위쪽:

- 검색 결과 카드 목록
- 선택한 상품 상세
- 판매자 정보

각 섹션의 아래쪽:

- request trace
- source
- cache status
- latency
- result count

### Comparison Dashboard

- direct latency vs cache latency
- speedup
- benchmark avg/min/max/p95/req/sec
- global metrics snapshot

### Redis Command Playground

- `GET`
- `SET`
- `DEL`
- `EXPIRE`

실제 서비스형 key 예시:

- `market:listing:1001`
- `market:search:아이폰:성남시 분당구:digital:12`
- `seller:501`

### QA 패널

다음 시나리오를 실행하고 pass/fail을 시각화합니다.

- `PING`
- `SET` 후 `GET`
- overwrite
- missing key lookup
- multiple key `DEL`
- `EXPIRE` lazy expiration
- `QUIT`
- `EXIT`
- unknown command
- wrong arity
- malformed RESP

## API Reference

- `POST /api/market/search`
- `POST /api/market/listing`
- `POST /api/market/compare`
- `POST /api/redis/command`
- `POST /api/cache/warm`
- `POST /api/qa/run`
- `GET /api/metrics/current`
- `GET /api/metrics/history`
- `GET /api/config`

모든 응답은 JSON입니다.

`POST /api/cache/warm`는 MongoDB에서 문서를 읽어 Redis에 적재합니다. 기본값은 `listing` 문서 전체이며, `doc_type=all` 또는 `limit`으로 범위를 조절할 수 있습니다.

`UPSTREAM_API_BASE_URL`이 설정되면 위 API는 로컬 구현 대신 공유 서버로 프록시됩니다. `/api/config` 응답에는 현재 대상 서버를 보여주는 `api_target`, `api_mode`가 추가됩니다.

## Test

```bash
python3 -m unittest discover -s tests -v
```

테스트 범위:

- cache miss 후 warm-up, 다음 요청 hit 전환
- 중고거래 검색 cache hit 검증
- 상품 상세 trace 반환 검증
- Redis playground command 검증
- benchmark artifact 저장
- stub backend 기준 QA suite 실행
- 통계 계산 함수 검증

## Demo Flow For Presentation

발표 4분 기준 권장 순서:

1. 중고거래 플랫폼 컨셉과 좌우 direct/cache 비교 구조를 설명
2. 같은 검색 조건으로 좌우 비교를 실행해 latency 차이를 시연
3. 상품 하나를 골라 상세 trace가 direct와 cache에서 어떻게 다른지 설명
4. Redis playground에서 실제 서비스 key로 GET/DEL/EXPIRE를 실행
5. Benchmark 패널에서 avg/min/max, req/sec, speedup을 보여줌
6. QA 패널에서 edge case를 실행하고 Redis 호환성을 정리

## Reproducible Benchmark Notes

- direct path는 MongoDB 검색 결과만 반복 측정
- cache path는 1회 warm-up miss 후 hit path만 반복 측정
- 동일 검색 조건을 계속 사용해 데이터 기준을 맞춤
- JSON artifact를 남겨 QA/발표 때 동일 수치를 재확인 가능

## Risks

- 실제 Mini Redis 서버가 아직 `EXPIRE`, `QUIT`, `EXIT`, malformed RESP 에러 응답을 완전히 지원하지 않으면 QA 일부가 실패할 수 있습니다.
- `INFO` 같은 메트릭 엔드포인트가 없으므로 monitoring 일부는 클라이언트 관측값 기반입니다.
- 로컬 환경에 MongoDB와 `pymongo`가 없으면 direct/benchmark 흐름은 실행되지 않습니다.
- Docker Compose에는 현재 `web`과 `mongodb`만 포함되어 있으므로 Mini Redis 서버 컨테이너 이름은 실제 통합 환경에 맞춰 `MINI_REDIS_HOST`를 수정해야 합니다.
- 공유 서버를 사용할 때는 브라우저에서 보이는 UI가 로컬이어도 실제 API 응답은 `UPSTREAM_API_BASE_URL` 기준일 수 있으므로 상단의 `API Target` 표시를 먼저 확인해야 합니다.
