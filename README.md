# SNS 추천 서비스 실습

추천을 생성해 Redis에 저장하고 FastAPI로 조회합니다. **part-1부터 part-9까지 순서대로 진행해요.** 기본 실습에는 모델 API 키가 필요 없습니다.

| 폴더 | 역할 |
|---|---|
| [sns-front](sns-front/README.md) | SNS 화면 |
| [sns-app](sns-app/README.md) | 로그인, 게시글과 피드 API |
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

[SNS 화면](http://localhost:3000)을 새로고침하고 **추천** 탭에서 게시글을 확인해요. **팔로잉** 탭은 기존 타임라인입니다. [추천 피드 API](http://localhost:8080/api/v1/recommendations)에서도 `mode: recommend`와 `posts`를 확인할 수 있습니다.

### part-3. 이벤트 전달

```sh
git switch part-3-events
uv sync --locked
docker compose up -d --wait
uv run sns-recommend init
uv run sns-recommend source-post --post 1001
```

```sh
# 별도 터미널에서 2단원 명령으로 API를 다시 켠 뒤 전송
uv run sns-recommend relay
```

`delivered: 1`을 확인해요. `init`은 필요한 DB 구조를 추가하고 기존 데이터를 유지합니다.

### part-4. 게시글 색인

처음에는 아래 [모델 설정](#모델-설정)의 Ollama 준비 명령을 실행합니다.

```sh
git switch part-4-indexing
uv sync --locked
uv run sns-recommend init
uv run sns-recommend index
```

게시글 벡터를 저장합니다. 다시 실행하면 `indexed: 0`이에요.

### part-5. 관심사 검색

```sh
git switch part-5-retrieval
uv sync --locked
uv run sns-recommend init
uv run sns-recommend embedding --user 7
```

관심사에 맞는 추천 ID를 확인합니다.

### part-6. 재정렬

```sh
git switch part-6-reranking
uv sync --locked
uv run sns-recommend generate --user 7
```

재정렬한 추천 ID를 확인해요.

### part-7. LangGraph

```sh
git switch part-7-langgraph
uv sync --locked
uv run sns-recommend graph --user 7
```

검색부터 추천 저장까지 실행합니다. 체크포인트 테이블은 자동으로 준비해요.

### part-8. 품질 평가

```sh
git switch part-8-evaluation
uv sync --locked
uv run sns-recommend evaluate
```

`sns-recommend/reports/evaluation.json`에서 합성 데이터의 전략별 점수를 비교합니다.

### part-9. 조회 측정과 자동 갱신

```sh
# SNS 앱 다시 빌드
git switch part-9-resilience
cd ../sns-app
./gradlew jibDockerBuild
docker compose up -d --wait
cd ../sns-recommend
uv sync --locked
uv run sns-recommend init
uv run sns-recommend graph --user 7
uv run sns-recommend benchmark --user 7
```

`sns-recommend/reports/benchmark.json`에서 Redis 조회 속도와 목록 나이를 확인해요. 추천 API를 중단하고 같은 브라우저에서 [추천 피드 API](http://localhost:8080/api/v1/recommendations)를 새로고침하면 `mode: latest`로 응답합니다.

```sh
# 2단원 명령으로 API를 다시 켜고 브라우저에서 추천 피드 조회
# 새 터미널: sns-recommend/에서 worker 실행
uv run python -m sns_recommend.worker
```

worker는 30초마다 갱신 대상을 확인해요. 최근 30분 내 조회했고 최근 5분 내 생성 작업이 없는 사용자의 추천을 갱신합니다.

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

| ID | 역할 | 주제 또는 관심사 |
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
| SNS DB (`snsdb`, 5432) | 회원과 게시글 원본, 관심사, Outbox | `SOURCE_DATABASE_URL` |
| 추천 DB (`recommend`, 55432) | 글 ID별 벡터, 행동, 작업과 체크포인트 | `DATABASE_URL` |
| Redis (56379) | 완성된 추천 ID 목록 | `REDIS_URL` |

본문은 SNS DB에서 읽어요. 글 변경 이벤트에는 ID와 버전만 담고, worker가 원본을 읽어 벡터를 갱신합니다.

## 모델 설정

기본 실습은 **최신 Ollama로 로컬 모델을 실제 호출**합니다. 외부 API 키와 사용료는 필요 없어요. 4단원부터 적용합니다.

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

8단원은 합성 정답셋 평가, 9단원 benchmark는 Redis 읽기 측정입니다. 로컬 모델도 호출 횟수와 생성 시간을 기록해요. 일일 20회 제한은 실습의 과도한 작업을 막는 설정이며 제공자 한도가 아닙니다.
