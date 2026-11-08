# SNS 추천 서비스

추천은 다섯 단계로 나뉩니다. 후보 수집, 순위 매기기, 거르기와 섞기, 결과 저장, 평가입니다.

| 프로세스 | 하는 일 |
|---|---|
| `sns-recommend-event-worker` | SNS DB의 변경을 읽어 `user_events`와 글 벡터를 갱신 |
| `sns-recommend-worker` | 후보 수집, 순위 모델 점수, 작성자 섞기 후 Redis에 발행 |
| `sns-recommend-trainer` | 새 데이터가 쌓이면 순위 모델을 다시 학습하고, 기준을 넘을 때만 교체 |
| `uvicorn sns_recommend.api:app` | 저장된 추천 목록 조회. 모델을 호출하지 않음 |

실행 명령은 [전체 실습 가이드](../README.md)를 따릅니다.
