# SNS 앱

Java 25와 Spring Boot로 로그인, 게시글과 피드 API를 제공합니다. 실행과 연동 확인은 [실습 가이드](../README.md#실습-순서)를 따라가요.

`GET /api/v1/recommend`는 로그인한 사용자 ID로 추천 API를 호출하고, 받은 ID 순서대로 게시글을 응답합니다.

`RECOMMEND_FEED_BASE_URL`은 로컬에서 `http://localhost:8001`, Docker에서 `http://host.docker.internal:8001`입니다.
