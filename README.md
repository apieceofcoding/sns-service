# SNS 추천 서비스 실습

백엔드 개발자를 위한 추천 시스템 실습입니다. 우리 서비스의 행동 데이터로 순위 모델을 학습하고, 추천을 생성해 Redis에 저장한 뒤 FastAPI로 조회합니다. 새 데이터가 쌓이면 다시 학습하고 나아질 때만 교체하며, A/B 실험으로 실제 피드가 나아졌는지 확인해요. **part-1부터 part-6까지 순서대로 진행해요.** 모델 API 키와 GPU는 필요 없습니다.

| 폴더 | 역할 |
|---|---|
| [sns-front](sns-front/README.md) | SNS 화면 |
| [sns-app](sns-app/README.md) | 로그인, 게시글, 행동 수집과 피드 API |
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

추천은 다섯 단계로 나눠 만듭니다.

| 단계 | 하는 일 | 브랜치 |
|---|---|---|
| 후보 수집 (retrieve) | 볼 만한 글을 빠르게 모음 | part-2 |
| 순위 매기기 (rerank) | 우리 데이터로 학습한 트랜스포머가 반응 확률을 예측 | part-3, part-4 |
| 거르기와 섞기 (validate, diversify) | 모델 출력 검사, 같은 작성자 연속 줄이기 | part-4 |
| 결과 저장 (publish) | Redis에 목록 발행, 조회는 모델 없이 읽음 | part-4 |
| 평가 (evaluation) | 후보 재현율, 학습 뒤 기간의 사용자 이벤트, A/B 실험으로 확인하고 이긴 모델만 교체 | part-2, part-3, part-5, part-6 |

### part-1. 기존 SNS와 실습 환경

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

[SNS 화면](http://localhost:3000)에서 `recommenddemo` / `recommend1234`로 가입하고 로그인해요. 이미 가입했다면 로그인만 합니다. 글 작성도 확인하세요.

### part-2. 행동 수집과 후보 수집

아래 [모델 설정](#모델-설정)의 Ollama를 먼저 준비합니다.

```sh
git switch part-2-events-retrieval
# 노출과 클릭을 기록하는 SNS 앱 다시 실행
cd ../sns-app
./gradlew jibDockerBuild
docker compose up -d --wait --force-recreate app
# 추천 DB 실행
cd ../sns-recommend
uv sync --locked
docker compose up -d --wait
uv run sns-recommend init
```

```sh
# 합성 독자 300명이 4시간 동안 글을 보고 반응
uv run sns-recommend simulate
# SNS DB의 변경을 user_events로 옮기고 글 1,200개를 임베딩. 1~2분 걸림
uv run sns-recommend-event-worker --once
```

`simulate`는 독자마다 숨은 취향(주 관심 주제, 두 번째 주제)과 그때그때 바뀌는 관심을 정해 두고, 글 10개씩 15번 보여 줍니다. 보면 `post_actions`에 노출, 누르면 클릭, 마음에 들면 `likes`에 좋아요가 남아요. 독자 7, 8, 9번의 취향은 각각 백엔드와 AI 개발, 여행과 여행 유튜브, 운동과 운동 식단이고, 17번은 여행과 운동, 18번은 AI 개발과 여행 유튜브입니다. 실제 앱과 같은 테이블에 쓰므로 이후 단계는 진짜 사용자와 똑같이 처리해요.

이벤트 worker는 테이블별로 마지막 위치 이후 바뀐 행만 읽어 추천 DB에 옮깁니다. `post_actions`는 행동 시각(`created_at`)과 저장 시각(`recorded_at`)을 따로 둬요. 늦게 도착한 행동도 저장 시각으로 읽으므로 놓치지 않고, 원래 행동 시각은 그대로 남습니다. 바뀐 것이 없으면 `processed`가 0이에요.

| action | 원본 | 사용하는 곳 |
|---|---|---|
| `like` | `likes` | 사용자 벡터, 모델 입력과 정답 |
| `reply` | `posts.parent_id` | 사용자 벡터, 모델 입력 |
| `repost` | `posts.repost_id` | 사용자 벡터, 모델 입력 |
| `click` | `post_actions` | 사용자 벡터, 모델 입력과 정답 |
| `impression` | `post_actions` | 이미 본 글 제외, 학습 데이터 |

```sh
# 로그인 쿠키 저장 (part-1에서 가입한 계정)
curl -fsS -c cookies.txt -X POST http://localhost:8080/api/v1/login -d 'username=recommenddemo&password=recommend1234'
# 클릭 기록. 같은 행동을 재전송할 때는 같은 eventId 사용
curl -fsS -b cookies.txt -X POST http://localhost:8080/api/v1/recommend/actions -H 'Content-Type: application/json' -d '{"eventId":"03b9e8fe-a243-48b8-9048-11c48ce52001","action":"click","postId":4}'
uv run sns-recommend-event-worker --once
```

```sh
# 후보 수집: 사용자 벡터로 의미 검색, 최신순과 인기순을 합쳐 최대 30개
uv run sns-recommend profile --user 7
uv run sns-recommend candidates --user 7
```

사용자 벡터는 최근 반응한 글 벡터 최대 5개의 평균이며 메모리에만 둡니다. 후보는 최근 48시간 글에서 본인 글, 삭제 글, 이미 본 글을 빼고 고릅니다. `sources`로 후보가 들어온 경로를 확인해요. 후보에서 빠진 글은 다음 단계가 되살릴 수 없습니다.

```sh
# 후보 수집 평가: 최근 1시간에 반응한 글이 그 전에 만든 후보 30개 안에 있었나
uv run sns-recommend recall
```

`recall@30`은 최근 1시간 동안 클릭하거나 좋아요한 글 중, 그 시점 전의 정보로 만든 후보에 이미 들어 있던 비율입니다. 독자가 반응할 만한 글은 수백 개인데 후보는 30개라 값 자체는 작아요. `random`(무작위 30개의 기댓값)보다 몇 배 높은지를 봅니다. 최신순과 인기순을 섞으면 의미 검색만 쓸 때보다 재현율이 조금 낮아지지만, 새 글과 인기 글도 노출할 기회를 얻습니다.

별도 터미널에서 `uv run sns-recommend-event-worker`를 켜 두면 이후 변경도 계속 반영해요.

### part-3. 순위 모델 학습

```sh
git switch part-3-ranking-model
# PyTorch 설치. 처음 한 번 약 600MB
uv sync --locked
# 학습과 평가. 노트북 CPU에서 1~2분
uv run sns-recommend train
```

사용자 이벤트(노출과 반응)로 학습 데이터를 만듭니다. 한 사용자의 노출을 5분 간격으로 묶어 한 건으로 하고, 각 노출 뒤 5분 안의 클릭과 좋아요가 정답입니다. 5분이 지나지 않은 노출은 정답이 아직 바뀔 수 있어 학습에서 빼요. 입력은 사용자가 최근 반응한 글 20개와 보여 준 글들이에요. 앞의 75% 기간으로 학습하고, 뒤 25% 기간의 사용자 이벤트로 평가합니다. 학습에 쓰지 않은 뒤쪽 기간으로 확인해야 실제 성능에 가깝습니다.

| 결과 | 뜻 |
|---|---|
| `ndcg@10.latest` | 최신순 |
| `ndcg@10.embedding` | 사용자 벡터 유사도 순 (part-2의 의미 검색) |
| `ndcg@10.model` | 학습한 모델 |

모델은 2층, 4헤드, 64차원 트랜스포머이고 파라미터는 약 15만 개입니다. 글 벡터는 part-2의 임베딩을 그대로 쓰고, 행동 순서와 종류로 반응 확률을 학습해요. 후보끼리는 서로 보지 않으므로 한 글의 점수가 함께 놓인 다른 글에 따라 바뀌지 않습니다. 결과는 `models/latest.pt`에 저장해요.

### part-4. 추론과 피드 제공

```sh
git switch part-4-inference
# 추천 피드 API가 추가된 SNS 앱 다시 실행
cd ../sns-app
./gradlew jibDockerBuild
docker compose up -d --wait
cd ../sns-recommend
uv sync --locked
uv run sns-recommend init
```

```sh
# 새 터미널: 추천 조회 API 실행 후 켜 두기
uv run uvicorn sns_recommend.api:app --host 0.0.0.0 --port 8001
```

```sh
# 실습 터미널: 모델로 순위를 매겨 Redis에 발행
uv run sns-recommend generate --user 7
curl -fsS http://localhost:8001/internal/feeds/7
```

`generate`는 후보 수집, 모델 점수, 출력 검사, 작성자 섞기, 발행을 차례로 실행합니다. 점수가 숫자가 아니거나 모델이 없으면 후보 순서로 대체하고 `strategy`에 `embedding`을 남겨요. 같은 작성자의 글은 앞선 글이 하나 늘 때마다 우선순위가 0.7배가 됩니다.

[SNS 화면](http://localhost:3000)에 로그인하고 같은 브라우저에서 [내 정보](http://localhost:8080/api/v1/users/me)의 `id`를 확인해요.

```sh
# 37을 로그인한 사용자 ID로 변경. 반응이 없으면 최신순과 인기순 후보로 시작
uv run sns-recommend generate --user 37
# 새 터미널: 30초마다 활동한 사용자의 추천을 다시 생성
uv run sns-recommend-worker
```

[SNS 화면](http://localhost:3000)의 **추천** 탭을 새로고침합니다. 추천 worker는 30초마다 최근 30분 안에 활동했고 목록이 없거나 5분이 지난 사용자의 목록을 다시 만들어요. 활동 기록이 없어도 추천 탭을 열었는데 목록이 없던 사용자는 다음 주기에 함께 만듭니다. 바로 확인하려면 `generate --user`를 다시 실행합니다. 조회 API는 저장된 목록을 읽으며 모델을 호출하지 않습니다. 스크롤 중에는 커서가 같은 목록을 가리켜 순서가 유지돼요.

### part-5. 지속 학습 파이프라인

```sh
git switch part-5-mlops
uv sync --locked
uv run sns-recommend init
# 학습, 기준 검사, 통과하면 등록 후 교체
uv run sns-recommend train
uv run sns-recommend models
```

다시 학습할 때는 최근 학습 데이터 2,400건만 씁니다. 독자들이 지금 반응하는 방식을 따라가기 위해서예요. 새 모델은 같은 평가 데이터에서 임베딩 순보다 NDCG가 0.01 이상 높고, 지금 서비스 중인 모델보다 나빠지지 않을 때만 교체합니다. 떨어지면 `rejected`로 기록만 남아요. 모든 버전은 `model_versions`에 학습 기간, 데이터 수, 지표와 함께 저장됩니다.

```sh
# 지금부터 독자들의 반응 방식이 바뀜: 새 글에만 반응이 몰림
uv run sns-recommend simulate --shift --hours 1 --sessions 8
uv run sns-recommend-event-worker --once
# 서비스 중인 모델의 최근 1시간 성능
uv run sns-recommend monitor
# 새 데이터로 다시 학습
uv run sns-recommend train
uv run sns-recommend models
```

`monitor`의 `recent.active`가 학습 당시보다 떨어지면 독자들의 반응 방식이 달라졌다는 신호입니다. 한 사람의 관심사가 바뀌는 것은 모델이 최근 반응을 입력으로 읽어 따라가지만, 모두의 반응 방식이 바뀌면 다시 학습해야 해요. 다시 학습한 모델이 기준을 넘으면 교체됩니다. worker는 다음 생성부터 새 버전을 불러와요.

```sh
# 직전 버전으로 되돌리기
uv run sns-recommend rollback
# 새 터미널: 새 데이터가 충분히 쌓이면 10분마다 자동으로 다시 학습
uv run sns-recommend-trainer
```

### part-6. A/B 실험과 운영

```sh
git switch part-6-operations
uv sync --locked
uv run sns-recommend init
# 추천 worker를 다시 켠 뒤
uv run sns-recommend generate --user 7
curl -fsS http://localhost:8001/metrics
```

`/metrics`는 서비스 중인 모델 버전, 진행 중인 실험, 최근 한 시간 동안 보여 준 글 수를 순위 방식(`model`, `explore`, `embedding`)별로 보여 줍니다.

part-5까지는 오프라인 기준만 넘으면 새 모델로 바로 교체했습니다. 오프라인 NDCG는 과거 노출을 얼마나 잘 정렬하는지만 알려 줘요. part-6부터 새 모델은 **후보**로 남고, 실제로 보여 준 피드에서 이겨야 교체됩니다. 독자들은 part-5에서 바뀐 방식 그대로 반응해요. 그 전에 학습한 모델이 서비스 중일 때, 바뀐 뒤의 사용자 이벤트로 학습한 후보가 실제로 더 나은지 확인합니다.

```sh
# part-5의 trainer를 Ctrl+C로 종료한 뒤, 반응 방식이 바뀌기 전에 학습한 첫 모델을 서비스 모델로 둠
uv run sns-recommend models
uv run sns-recommend promote --version 1
# 다시 학습. 이번에는 교체되지 않고 후보로 남음
uv run sns-recommend train
# A/B 실험 시작: 대조군은 서비스 중인 모델, 실험군은 후보 모델
uv run sns-recommend experiment start
# 라운드마다 새 글이 올라오고, 독자가 발행된 피드의 위쪽 10개를 보고 반응. 3라운드에 2~3분
uv run sns-recommend experiment run --rounds 3
uv run sns-recommend experiment report
# 종료와 판정. 실험군이 이기면 후보가 서비스 모델이 됨
uv run sns-recommend experiment stop
uv run sns-recommend models
```

| 항목 | 기준 |
|---|---|
| 그룹 배정 | 실험 이름과 사용자 ID의 해시. 같은 독자는 항상 같은 그룹 |
| 서빙 기록 | 조회할 때마다 `served_posts`에 글, 위치, 목록, 모델 버전과 그룹을 남김. 반응을 이 기록에 이어 붙여 그룹별로 셈 |
| 계획한 크기 | 그룹마다 노출 3,000건(`--min-impressions`). 채우기 전의 `verdict`는 `wait` |
| 검정 | 독자를 나눴으므로 독자 단위로 비교. 그룹 이름표를 섞어도 이만한 차이가 나오는 비율이 `p_value` |
| 가드레일 | 클릭률이 올라도 좋아요율이 대조군의 95% 아래면 대조군 승 |
| 판정 | `treatment wins`면 후보로 교체, `control wins`나 `no clear difference`면 후보 탈락 |

한 독자의 노출은 서로 닮아 있어서, 노출을 하나씩 독립으로 세면 우연한 차이도 의미 있어 보입니다. 결과를 중간에 보고 유리할 때 멈춰도 같은 문제가 생겨요. 그래서 크기를 먼저 정하고 독자 단위로 비교합니다.

피드의 10%는 **탐색**으로 후보를 무작위 순서로 보여 줍니다(`strategy: explore`, `EXPLORE_RATE`). 순위 모델이 고른 글에만 반응이 쌓이면 그 데이터로는 모델을 공정하게 평가할 수 없기 때문이에요. 오프라인 평가와 `monitor`는 순위 모델이 고르지 않은 노출만 씁니다.

`sns-recommend-trainer`는 이 과정을 이어서 실행합니다. 새 데이터가 쌓이면 다시 학습하고, 후보가 생기면 실험을 시작하고, 계획한 노출이 차면 판정해요.

| 장애 | 동작 |
|---|---|
| 모델 파일이 없거나 읽을 수 없음 | 후보 순서로 발행 (`strategy: embedding`) |
| 모델 점수가 숫자가 아님 | 후보 순서로 발행 (`strategy: embedding_fallback`) |
| 추천 API 중지 | SNS가 최신순 제공 (`mode: latest`) |
| 생성 중 worker 중단 | 다음 주기에 다시 생성 |

추천 API를 끄고 [추천 피드 API](http://localhost:8080/api/v1/recommend)를 새로고침하면 `mode: latest`로 응답합니다.

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

`seed`는 작성자 24명, 독자 5명, 신규 가입자 1명과 게시글 1,200개를 만듭니다. `simulate`는 합성 독자 300명(ID 101부터)을 더하고 노출과 반응을 기록해요.

| ID | 역할 | 작성 주제 또는 취향 |
|---|---|---|
| 1, 11, 21, 31 | 작성자 | 백엔드 개발 |
| 2, 12, 22, 32 | 작성자 | 여행 |
| 3, 13, 23, 33 | 작성자 | 운동 |
| 4, 14, 24, 34 | 작성자 | AI 개발 |
| 5, 15, 25, 35 | 작성자 | 여행 유튜브 |
| 6, 16, 26, 36 | 작성자 | 운동 식단 |
| 7 | 독자 | 백엔드와 AI 개발 |
| 8 | 독자 | 여행과 여행 유튜브 |
| 9 | 독자 | 운동과 운동 식단 |
| 17 | 독자 | 여행과 운동 |
| 18 | 독자 | AI 개발과 여행 유튜브 |
| 19 | 신규 가입자 | 글과 반응 없음. 최신순과 인기순으로 시작 |
| 101~400 | 합성 독자 | 무작위 두 주제 |

작성자마다 50개씩, 약 20시간에 걸쳐 1분에 하나씩 올라온 것으로 만들어요. 주제마다 예문은 40개이고, 나머지 글은 두 예문을 이어 붙입니다. 최신순 비교를 위해 최근 48시간의 경계와 미래 시각도 포함해요. `seed`는 빈 실습 DB에서 한 번 실행합니다. 기존 ID와 충돌하면 중단하며 데이터를 덮어쓰지 않습니다. 모델 점수는 합성 독자의 행동으로 잰 것이며 실제 서비스 성과가 아닙니다.

## 저장 위치

| 저장소 | 내용 | 연결 설정 |
|---|---|---|
| SNS DB (`snsdb`, 5432) | 회원, 게시글, 좋아요 원본과 post_actions | `SOURCE_DATABASE_URL` |
| 추천 DB (`recommend`, 55432) | user_events, 읽은 위치, 글 벡터, 모델 버전, 생성 기록, 서빙 기록, 실험 | `DATABASE_URL` |
| Redis (56379) | 완성된 추천 ID 목록 | `REDIS_URL` |
| `sns-recommend/models/` | 학습한 모델 파일 | `MODEL_DIR` |

본문은 SNS DB에서 읽어요. 글 변경 이벤트에는 ID와 버전만 담고, worker가 원본을 읽어 벡터를 갱신합니다.

## 모델 설정

임베딩은 **Ollama로 로컬 모델을 실제 호출**합니다. 외부 API 키와 사용료는 필요 없어요. part-2부터 적용합니다.

```sh
# Ollama 설치 후 한 번 준비. Ollama 앱이 실행 중이면 별도 serve는 불필요
ollama pull qwen3-embedding:0.6b
ollama list
```

```dotenv
# 코드 기본값. 기존 .env가 있다면 맞춰주세요.
MODEL_MODE=live
MODEL_BASE_URL=http://localhost:11434/v1
MODEL_API_KEY=ollama
EMBEDDING_MODEL=qwen3-embedding:0.6b
DIMENSIONS=768
```

| 모델 | 역할 | 크기 |
|---|---|---|
| Qwen3 Embedding 0.6B (Ollama) | 글 본문을 768차원 벡터로 | 다운로드 약 639MB |
| 순위 트랜스포머 (PyTorch, 직접 학습) | 행동과 후보로 반응 확률 예측 | 파라미터 약 15만 개, 파일 약 600KB |

순위 모델은 GPU 없이 학습합니다. 학습 중 메모리는 1GB 안쪽이고, 사용자 한 명의 후보 30개 점수 계산은 1ms 미만이에요. `fixture` 모드는 자동 검사용 키워드 벡터이며 품질 평가에 사용하지 않습니다. 임베딩 모델을 바꾸면 다시 색인하고, 이전 벡터로 학습한 순위 모델은 쓰지 않아요.
