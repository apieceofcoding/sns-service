# SNS 추천 서비스 실습

추천을 생성해 Redis에 저장하고 FastAPI로 조회합니다. **part-1부터 part-6까지 순서대로 진행해요.** 기본 실습에는 모델 API 키가 필요 없습니다.

| 폴더 | 역할 |
|---|---|
| [sns-front](sns-front/README.md) | SNS 화면 |
| [sns-app](sns-app/README.md) | 로그인, 게시글, 행동 수집과 피드 API |
| [sns-recommend](sns-recommend/README.md) | 추천 생성과 조회 API |

<details>
<summary>처음 한 번: 도구 설치 (Windows / macOS)</summary>

[Node.js LTS](https://nodejs.org/)와 [Git](https://git-scm.com/downloads)을 설치합니다.

### Windows (PowerShell)

[Java 25 설치](https://adoptium.net/installation/)와 [uv 설치](https://docs.astral.sh/uv/getting-started/installation/) 명령입니다.

```powershell
winget install --exact --id EclipseAdoptium.Temurin.25.JDK
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

[Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)을 설치하고 실행합니다. WSL 2가 없다면 관리자 PowerShell에서 `wsl --install` 후 재부팅해요. 실습은 PowerShell에서 진행하며 Docker는 Linux 컨테이너를 사용합니다.

### macOS (터미널)

[Homebrew](https://brew.sh)가 없다면 먼저 설치합니다. 다음으로 [Java 25](https://formulae.brew.sh/cask/temurin@25)와 [uv](https://docs.astral.sh/uv/getting-started/installation/)를 설치해요.

```sh
brew install --cask temurin@25
brew install uv
```

[Docker Desktop](https://docs.docker.com/desktop/setup/install/mac-install/)에서 Apple Silicon 또는 Intel에 맞는 파일을 받아 설치하고 실행합니다.

### 설치 확인 (공통)

터미널을 다시 열고 Docker Desktop이 실행된 상태에서 확인해요.

```sh
java -version
javac -version
docker info
docker compose version
uv --version
node --version
npm --version
uv python install 3.13
```

Java와 javac는 25, Docker는 서버 정보가 나와야 합니다. 다른 Java가 선택되면 `JAVA_HOME`과 PATH를 JDK 25로 맞춰요.

</details>

## 시작하기

```sh
# Docker Desktop 실행 후 저장소 받기
git clone https://github.com/apieceofcoding/sns-service.git
cd sns-service/sns-recommend
```

## 실습 순서

명령은 `sns-recommend/`에서 시작합니다. 브랜치를 바꾸기 전 추천 API와 worker를 `Ctrl+C`로 종료해요. Windows에서는 `./gradlew`를 `.\gradlew.bat`로, `curl`을 `curl.exe`로 바꿉니다.

### part-1. SNS 실행과 데이터 관찰

```sh
# sns-recommend/에서 SNS 앱 실행
git switch part-1-environment
cd ../sns-app
./gradlew jibDockerBuild
docker compose up -d --wait
```

```sh
# status: UP 확인 후 실습 데이터 생성
curl -fsS http://localhost:8080/actuator/health
cd ../sns-recommend
uv sync --locked
uv run sns-recommend seed
docker compose -f ../sns-app/docker-compose.yml exec postgres psql -U snsuser -d snsdb -P pager=off
```

```sql
-- 회원과 게시글 확인 후 종료
SELECT id, username, created_at FROM users ORDER BY id;
SELECT id, user_id, left(content, 60) AS content, created_at FROM posts ORDER BY id LIMIT 5;
\q
```

#### SNS 화면 실행

```sh
# 새 터미널: sns-service/에서 실행하고 켜 두기
cd sns-front
npm ci
npm run dev
```

[SNS 화면](http://localhost:3000)에서 `recommenddemo` / `recommend1234`로 가입하고 로그인해요. 이미 가입했다면 로그인만 합니다. 글 작성도 확인하세요. `seed`로 만든 독자 7~9번은 추천 비교용이며 비밀번호가 없습니다.

### part-2. 추천 생성과 조회

```sh
# 실습 터미널: sns-recommend/ (SNS 화면은 켜 두기)
git switch part-2-feed-api

# SNS 앱 다시 빌드
cd ../sns-app
./gradlew jibDockerBuild
docker compose up -d --wait

# 추천 저장소 실행
cd ../sns-recommend
uv sync --locked
docker compose up -d --wait
```

```sh
# 새 터미널: sns-recommend/에서 API 실행 후 켜 두기
uv run uvicorn sns_recommend.api:app --host 0.0.0.0 --port 8001
```

[SNS 화면](http://localhost:3000)에 로그인하고 같은 브라우저에서 [내 정보](http://localhost:8080/api/v1/users/me)의 `id`를 확인해요.

```sh
# 실습 터미널: 10을 로그인한 사용자 ID로 변경
uv run sns-recommend baseline --user 10 --strategy latest
```

[SNS 화면](http://localhost:3000)을 새로고침하고 **추천** 탭에서 게시글을 확인해요. **팔로잉** 탭은 기존 타임라인입니다. [추천 피드 API](http://localhost:8080/api/v1/recommend)에서도 `mode: recommend`와 `posts`를 확인할 수 있습니다.

### part-3. 변경 수집과 검색 데이터 준비

아래 [모델 설정](#모델-설정)의 Ollama를 먼저 준비합니다.

```sh
git switch part-3-events-indexing
uv sync --locked
docker compose up -d --wait
uv run sns-recommend init
# 행동 수집 코드가 추가된 SNS 앱 다시 실행
cd ../sns-app
./gradlew jibDockerBuild
docker compose up -d --wait --force-recreate app
cd ../sns-recommend
uv run sns-recommend index
```

기존 글은 한 번에 최대 20개씩 색인해요. `indexed: 0`이 될 때까지 반복합니다.

```sh
# 글 변경과 독자별 좋아요 6개 기록
uv run sns-recommend source-post --post 1001
uv run sns-recommend seed-actions
# SNS DB에서 바뀐 행만 읽어 user_events와 글 벡터에 반영
uv run sns-recommend-event-worker --once
# 별도 터미널에서 계속 처리
uv run sns-recommend-event-worker
```

이벤트 worker가 테이블별로 마지막 위치 이후 바뀐 행만 읽어 추천 DB에 옮겨요. 위치는 `sync_cursors`에 저장하고, 늦게 커밋되는 변경을 놓치지 않도록 최근 60초는 다시 읽습니다. 글이 늘어도 한 주기의 읽기 양은 변경량만큼만 늘어요. 바뀐 것이 없으면 `--once` 결과의 `processed`가 0입니다.

#### 행동과 추천 갱신 기록

원본은 SNS DB에 두고, 추천 DB의 `user_events`에는 이벤트 worker만 저장합니다. 추천 API는 읽기만 해요.

| action | 원본 | 사용하는 곳 |
|---|---|---|
| `like` | `likes` | 사용자 벡터, 재정렬 이력 |
| `reply` | `posts.parent_id` | 사용자 벡터, 재정렬 이력 |
| `repost` | `posts.repost_id` | 사용자 벡터, 재정렬 이력 |
| `click` | `post_actions` | 사용자 벡터, 재정렬 이력 |
| `impression` | `post_actions` | 이미 본 글 제외, 활동 사용자 판단 |
| `recommend.requested` | worker가 생성 | 사용자별 추천 생성 예약 |

좋아요, 답글과 재게시는 SNS 앱의 기존 저장 그대로입니다. 취소하거나 삭제하면 worker가 `removed_at`을 채워 추천에서 빠져요. 노출과 클릭은 원본 테이블이 없어서 `POST /api/v1/recommend/actions`가 `post_actions`에 저장합니다. 화면의 게시글 카드가 이 요청을 보내고, 사용자 ID는 로그인 세션에서 읽어요. 같은 글의 노출은 한 행만 남고, 클릭의 재전송은 같은 eventId로 구분합니다. `seed-actions`는 독자별 합성 좋아요를 `likes`에 넣는 준비 명령입니다.

```sh
# 로그인 쿠키 저장 (1단원에서 가입한 계정)
curl -fsS -c cookies.txt -X POST http://localhost:8080/api/v1/login -d 'username=recommenddemo&password=recommend1234'
# 클릭 기록. 같은 행동을 재전송할 때는 같은 eventId 사용
curl -fsS -b cookies.txt -X POST http://localhost:8080/api/v1/recommend/actions -H 'Content-Type: application/json' -d '{"eventId":"03b9e8fe-a243-48b8-9048-11c48ce52001","action":"click","postId":4}'
# 기존 좋아요 API. SNS DB에는 좋아요만 저장
curl -fsS -b cookies.txt -X POST http://localhost:8080/api/v1/likes -H 'Content-Type: application/json' -d '{"postId":1}'
uv run sns-recommend-event-worker --once

# 2단원에서 실행한 추천 API를 종료하고 새 터미널에서 다시 실행
uv run uvicorn sns_recommend.api:app --host 0.0.0.0 --port 8001
```

```sh
# 실습 터미널: 조회는 저장된 목록을 읽기만 함
curl -fsS http://localhost:8001/internal/feeds/7
```

좋아요, 답글, 재게시와 클릭이 추가되거나 취소되면 worker가 추천 갱신을 예약해요. 최근 30분 내 노출이 있는 사용자의 목록이 없거나 5분이 지났을 때도 예약합니다. 이 경우 기본 60초 간격으로 제한하고, 같은 사용자의 대기 요청은 합쳐요. 3단원에서는 기록과 예약까지만 확인하며, 추천 worker의 처리와 복구는 4단원에서 연결합니다. 6단원에서는 비용과 갱신 주기를 검증해요.

```sql
-- 추천 DB에서 기록 확인
SELECT action, user_id, post_id, removed_at, processed_at
FROM user_events
ORDER BY occurred_at DESC LIMIT 20;
```

`recommend.requested`는 이벤트 worker가 처리하지 않으므로 대기 상태가 정상입니다.

#### 사용자 벡터 준비

최근 7일 좋아요, 답글, 재게시와 클릭이 있는 서로 다른 글 20개 중, 원본 버전과 임베딩 공간이 일치하는 최대 5개 벡터를 평균내 정규화합니다. 글 벡터를 재사용하므로 새 모델 호출은 없어요.

```sh
uv run sns-recommend profile --user 7
uv run sns-recommend profile --user 8
uv run sns-recommend profile --user 9
```

`ready`는 벡터 준비 여부이고 `dimensions`는 계산한 벡터 차원입니다. 유효한 반응 글이 없으면 `ready: false`로 표시해요. 사용자 벡터는 메모리에서 계산하며 추천 DB에 저장하지 않습니다. 다음 검색 함수에 인자로 전달해요. 게시글 본문은 SNS DB에만 둡니다.

### part-4. 후보 검색과 LangGraph 순위 생성

```sh
git switch part-4-reranking
uv sync --locked
uv run sns-recommend init
# 후보 검색 결과를 Redis에 저장해 확인
uv run sns-recommend embedding --user 7
# LangGraph로 후보 검색, LLM 재정렬, 검증, 다양성 조정과 발행을 실행
uv run sns-recommend graph --user 8
uv run sns-recommend graph --user 9
# 재정렬 직후 멈춘 뒤 worker로 이어서 실행
uv run sns-recommend graph --user 7 --pause-after-rerank
uv run python -m sns_recommend.worker --once
```

의미 검색, 최신순과 인기순 후보를 합치고 본인 글, 삭제 글, 이미 본 글을 제외합니다. 행동이 없으면 최신순과 인기순으로 시작해요. 검색에서 빠진 글은 LLM이 선택할 수 없으므로 후보를 먼저 확인합니다.

`embedding`과 `graph`는 실행 시 최신 행동으로 사용자 벡터를 다시 계산합니다. 새 모델 호출 없이 3단원의 함수를 재사용해요. `graph`는 후보만 LLM에 보내고, 반환 ID 검증과 다양성 조정을 거쳐 Redis에 저장합니다. 오류가 나면 후보 순위로 대체해요.

체크포인트에 진행 상태를 저장하고, 생성 번호로 오래된 결과의 발행을 막습니다. 체크포인트 테이블은 자동으로 준비해요. worker는 가장 오래된 대기 요청부터 처리하므로, 다른 요청이 남아 있으면 멈춘 작업은 그 뒤에 이어집니다.

### part-5. 품질 평가

```sh
git switch part-5-evaluation
uv sync --locked
uv run sns-recommend evaluate
```

`sns-recommend/reports/evaluation.json`에서 합성 데이터의 전략별 점수를 비교합니다.

### part-6. 갱신 주기와 조회 비용 검증

```sh
# SNS 앱 다시 빌드
git switch part-6-resilience
cd ../sns-app
./gradlew jibDockerBuild
docker compose up -d --wait
cd ../sns-recommend
uv sync --locked
uv run sns-recommend init
uv run sns-recommend graph --user 7
uv run sns-recommend benchmark --user 7
```

`sns-recommend/reports/benchmark.json`에서 Redis 조회 속도와 목록 나이를 확인해요. 추천 API를 중단하고 같은 브라우저에서 [추천 피드 API](http://localhost:8080/api/v1/recommend)를 새로고침하면 `mode: latest`로 응답합니다.

```sh
# 2단원 명령으로 API를 다시 켜고 브라우저에서 추천 피드 조회
# 새 터미널: sns-recommend/에서 worker 실행
uv run python -m sns_recommend.worker
```

worker는 3단원에서 정의한 예약 규칙을 30초마다 실행합니다. 기록 구조를 바꾸지 않고, 갱신 주기와 목록 나이, 생성 비용을 확인해요.

## 종료

```sh
# 화면, API, worker를 Ctrl+C로 종료 후 sns-recommend/에서 실행
# 데이터는 유지
docker compose -f ../sns-app/docker-compose.yml down
docker compose down  # part-2부터
```

```sh
# 이어서 실행: 해당 브랜치의 sns-recommend/
uv sync --locked
docker compose -f ../sns-app/docker-compose.yml up -d --wait
docker compose up -d --wait  # part-2부터
```

화면, 추천 API와 worker도 필요한 단원의 명령으로 다시 켭니다.

## 실습 데이터

작성자 6명, 독자 3명과 게시글 240개를 준비합니다.

| ID | 역할 | 작성 주제 또는 좋아요를 누른 글 |
|---|---|---|
| 1 | 작성자 | 백엔드 개발 |
| 2 | 작성자 | 여행 |
| 3 | 작성자 | 운동 |
| 4 | 작성자 | AI 개발 |
| 5 | 작성자 | 여행 유튜브 |
| 6 | 작성자 | 운동 식단 |
| 7 | 독자 | 백엔드와 AI 개발 |
| 8 | 독자 | 여행과 여행 유튜브 |
| 9 | 독자 | 운동과 운동 식단 |

작성자마다 40개씩 생성하며, 최신순 비교를 위해 최근 48시간의 경계와 미래 시각을 포함해요. `seed`는 빈 실습 DB에서 한 번 실행합니다. 기존 ID와 충돌하면 중단하며 데이터를 덮어쓰지 않습니다.

## 저장 위치

| 저장소 | 내용 | 연결 설정 |
|---|---|---|
| SNS DB (`snsdb`, 5432) | 회원, 게시글, 좋아요 원본과 post_actions | `SOURCE_DATABASE_URL` |
| 추천 DB (`recommend`, 55432) | user_events, 읽은 위치, 글 벡터와 체크포인트 | `DATABASE_URL` |
| Redis (56379) | 완성된 추천 ID 목록 | `REDIS_URL` |

본문은 SNS DB에서 읽어요. 글 변경 이벤트에는 ID와 버전만 담고, worker가 원본을 읽어 벡터를 갱신합니다.

## 모델 설정

기본 실습은 **최신 Ollama로 로컬 모델을 실제 호출**합니다. 외부 API 키와 사용료는 필요 없어요. 3단원부터 적용합니다.

```sh
# Ollama 설치 후 sns-recommend/에서 한 번 준비
ollama pull qwen3-embedding:0.6b
ollama pull qwen3-vl:2b-instruct
ollama create sns-reranker -f ollama.Modelfile
# Ollama 앱이 실행 중이면 별도 serve는 불필요
ollama list
```

Ollama 앱 대신 CLI로 켜려면 별도 터미널에서 `ollama serve`를 실행합니다.

```dotenv
# 코드 기본값. 기존 .env가 있다면 맞춰주세요.
MODEL_MODE=live
MODEL_BASE_URL=http://localhost:11434/v1
MODEL_API_KEY=ollama
EMBEDDING_MODEL=qwen3-embedding:0.6b
RERANK_MODEL=sns-reranker
DIMENSIONS=768
```

임베딩은 Qwen3 Embedding 0.6B, 재정렬은 Qwen3-VL 2B를 사용해요. `sns-reranker`는 8192 컨텍스트로 만든 모델 별칭입니다. 이미지 설명에도 같은 생성 API를 사용할 수 있습니다. 두 모델의 다운로드는 약 639MB와 1.9GB이며 실행 메모리는 별도입니다.

| 모드 | 용도 |
|---|---|
| live | 기본. 실제 로컬 추론 |
| record | 실제 응답 저장 |
| replay | 같은 입력, 서버와 모델의 저장 응답 재사용 |
| fixture | 자동 검사와 저사양 환경용 모의 응답. 품질 평가에 사용하지 않음 |

생성은 OpenAI 호환 `/v1/chat/completions`, 임베딩은 `/v1/embeddings`로 호출합니다. 모델이나 서버를 바꾸면 다시 색인해요. API 응답의 JSON, 후보 ID와 벡터 차원을 검증합니다.

Docker worker에서는 `MODEL_BASE_URL=http://host.docker.internal:11434/v1`을 사용합니다. Ollama도 Docker에서 접근할 수 있는 호스트 주소에 리스닝해야 해요. [호스트 설정](https://docs.ollama.com/faq)

OpenAI API는 강사용 비교 선택입니다. 서버 주소, 모델명과 키를 계정에서 사용 가능한 값으로 바꿔요. 수강생 기본 실습은 OpenAI 결제를 요구하지 않습니다. 키와 녹화 파일은 Git에 넣지 않습니다.

5단원은 합성 정답셋 평가, 6단원 benchmark는 Redis 읽기 측정입니다. 로컬 모델도 호출 횟수와 생성 시간을 기록해요. 일일 20회 제한은 실습의 과도한 작업을 막는 설정이며 제공자 한도가 아닙니다.
