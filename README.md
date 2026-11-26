# SNS 추천 서비스 실습

행동 데이터로 순위 모델을 학습해 추천 피드를 만들고 운영하는 실습입니다. part-1부터 part-6까지 순서대로 진행해요.

| 폴더                                     | 역할                                       |
| ---------------------------------------- | ------------------------------------------ |
| [sns-front](sns-front/README.md)         | SNS 화면                                   |
| [sns-app](sns-app/README.md)             | 로그인, 게시글, 행동 수집과 피드 API       |
| [sns-recommend](sns-recommend/README.md) | 행동 수집, 모델 학습, 추천 생성과 조회 API |

<details>
<summary>처음 한 번: 도구 설치 (Windows / macOS)</summary>

[Node.js LTS](https://nodejs.org/)와 [Git](https://git-scm.com/downloads)을 설치합니다.

### Windows (PowerShell)

[Java 25 설치](https://adoptium.net/installation/)와 [uv 설치](https://docs.astral.sh/uv/getting-started/installation/) 명령입니다.

```powershell
winget install --exact --id EclipseAdoptium.Temurin.25.JDK
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

[Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)을 설치하고 실행합니다. WSL 2가 없다면 `wsl --install` 후 재부팅해요.

### macOS (터미널)

[Homebrew](https://brew.sh), [Java 25](https://formulae.brew.sh/cask/temurin@25), [uv](https://docs.astral.sh/uv/getting-started/installation/)를 설치합니다.

```sh
brew install --cask temurin@25
brew install uv
```

[Docker Desktop](https://docs.docker.com/desktop/setup/install/mac-install/)을 설치하고 실행합니다.

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

Java는 25, Docker는 서버 정보가 나오면 됩니다.

</details>

## 시작하기

```sh
# Docker Desktop 실행 후 저장소 받기
git clone https://github.com/apieceofcoding/sns-service.git
cd sns-service/sns-recommend
```

## SNS 앱 실행

```sh
# sns-service/에서. 브랜치를 바꾸면 다시 실행
cd sns-app
./gradlew --stop && ./gradlew jibDockerBuild
docker compose up -d
```

## SNS 화면 실행

```sh
# 새 터미널, sns-service/에서. http://localhost:3000
cd sns-front
npm ci # 처음 한 번만
npm run dev
```

## part별 실행

명령은 `sns-recommend/`에서 실행하고, 브랜치를 바꾸기 전 API와 worker를 `Ctrl+C`로 종료합니다. Windows는 `.\gradlew.bat`, `curl.exe`를 씁니다.

### part-1. 기존 SNS와 실습 환경

```sh
git switch part-1-environment
# SNS 앱 실행 후
uv sync
# 사용자, 글, 팔로우, 이미지 생성. 다시 실행하면 SNS 데이터를 모두 지우고 새로 만듦
uv run sns-recommend seed
```

독자 계정(비밀번호 `sample1234`): `jihoon_codes`(백엔드, AI), `haeun_wander`(여행, 여행 영상), `taeyang_fit`(운동, 식단), `sujin_daily`(여행, 운동), `minho_weekend`(AI, 여행 영상)

### part-2. 행동 수집과 후보 수집

```sh
# Ollama 필요: 모델 설정
git switch part-2-events-embeddings
# SNS 앱 다시 실행 후 추천 DB 실행
docker compose up -d
uv sync
uv run sns-recommend init
# 합성 독자 300명의 노출과 반응 기록
uv run sns-recommend simulate
# 행동을 user_events로 옮기고 글 임베딩. 1~2분
uv run sns-recommend-event-worker --once
# 후보 30개 재현율 평가
uv run sns-recommend recall
```

### part-3. 순위 모델 학습

```sh
git switch part-3-ranking-model
# PyTorch 설치. 처음 한 번 약 600MB
uv sync
# 학습과 평가(NDCG@10). CPU에서 1~2분
uv run sns-recommend train
```

### part-4. 추론과 피드 제공

```sh
git switch part-4-inference
# SNS 앱 다시 실행 후
uv sync
uv run sns-recommend init
# part-3 모델로 추천 생성
uv run sns-recommend generate --user 7
# 새 터미널: 추천 조회 API
uv run uvicorn sns_recommend.api:app --host 0.0.0.0 --port 8001
# 새 터미널: 추천 worker. 화면의 추천 탭에서 확인
uv run sns-recommend-worker
```

### part-5. 지속 학습 파이프라인

```sh
git switch part-5-mlops
# MLflow 서버 추가. 학습 기록은 http://localhost:55000
docker compose up -d
uv sync
uv run sns-recommend init
# 학습을 MLflow run으로 기록, 기준을 통과하면 모델 버전으로 등록 후 교체
uv run sns-recommend train
# 독자 반응 방식 변화: 새 글에만 반응
uv run sns-recommend simulate --shift --hours 1 --sessions 8
uv run sns-recommend-event-worker --once
# 서비스 모델 성능 확인 후 다시 학습
uv run sns-recommend monitor
uv run sns-recommend train
# 직전 버전으로 되돌리기
uv run sns-recommend rollback
```

### part-6. A/B 실험과 운영

```sh
git switch part-6-operations
uv sync
uv run sns-recommend init
# 첫 모델로 서비스, 새 모델은 후보로 학습
uv run sns-recommend promote --version 1
uv run sns-recommend train
# A/B 실험. 3라운드에 2~3분
uv run sns-recommend experiment start
uv run sns-recommend experiment run --rounds 3
# 판정. 후보가 이기면 교체
uv run sns-recommend experiment stop
```

## 종료

```sh
# 화면, API, worker는 Ctrl+C. sns-recommend/에서
# 데이터는 유지
docker compose -f ../sns-app/docker-compose.yml down
docker compose down  # part-2부터
```

```sh
# 이어서 실행: 해당 브랜치의 sns-recommend/
uv sync
docker compose -f ../sns-app/docker-compose.yml up -d
docker compose up -d  # part-2부터
```

## 실습 데이터

`seed`는 사용자와 글 1,200개를, `simulate`는 합성 독자 300명(ID 101부터)의 반응을 만듭니다.

| ID            | 역할        | 작성 주제 또는 취향                      |
| ------------- | ----------- | ---------------------------------------- |
| 1, 11, 21, 31 | 작성자      | 백엔드 개발                              |
| 2, 12, 22, 32 | 작성자      | 여행                                     |
| 3, 13, 23, 33 | 작성자      | 운동                                     |
| 4, 14, 24, 34 | 작성자      | AI 개발                                  |
| 5, 15, 25, 35 | 작성자      | 여행 유튜브                              |
| 6, 16, 26, 36 | 작성자      | 운동 식단                                |
| 7             | 독자        | 백엔드와 AI 개발                         |
| 8             | 독자        | 여행과 여행 유튜브                       |
| 9             | 독자        | 운동과 운동 식단                         |
| 17            | 독자        | 여행과 운동                              |
| 18            | 독자        | AI 개발과 여행 유튜브                    |
| 19            | 신규 가입자 | 글과 반응 없음. 최신순과 인기순으로 시작 |
| 101~400       | 합성 독자   | 무작위 두 주제                           |

## 저장 위치

| 저장소                       | 내용                                                                   | 연결 설정             |
| ---------------------------- | ---------------------------------------------------------------------- | --------------------- |
| SNS DB (`snsdb`, 5432)       | 회원, 게시글, 좋아요 원본과 post_actions                               | `SOURCE_DATABASE_URL` |
| 추천 DB (`recommend`, 55432) | user_events, 읽은 위치, 글 벡터, 생성 기록, 서빙 기록, 실험             | `DATABASE_URL`        |
| Redis (56379)                | 완성된 추천 ID 목록                                                    | `REDIS_URL`           |
| MLflow (55000, part-5부터)   | 학습 기록(run), 등록된 모델 버전, 모델 파일                            | `MLFLOW_TRACKING_URI` |
| `sns-recommend/models/`      | 학습한 모델 파일                                                       | 기본 경로             |

## 모델 설정

임베딩은 Ollama 로컬 모델을 씁니다(part-2부터, API 키 불필요).

```sh
# Ollama 설치 후 한 번
ollama pull qwen3-embedding:0.6b
```

```dotenv
# 코드 기본값. 기존 .env가 있다면 맞춰주세요.
MODEL_MODE=live
MODEL_BASE_URL=http://localhost:11434/v1
MODEL_API_KEY=ollama
EMBEDDING_MODEL=qwen3-embedding:0.6b
DIMENSIONS=768
```

| 모델                                 | 역할                         | 크기                               |
| ------------------------------------ | ---------------------------- | ---------------------------------- |
| Qwen3 Embedding 0.6B (Ollama)        | 글 본문을 768차원 벡터로     | 다운로드 약 639MB                  |
| 순위 트랜스포머 (PyTorch, 직접 학습) | 행동과 후보로 반응 확률 예측 | 파라미터 약 15만 개, 파일 약 600KB |
