package com.apiece.springboot_sns_sample.domain.recommend;

import com.apiece.springboot_sns_sample.domain.post.Post;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.server.ResponseStatusException;

import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.util.Base64;
import java.util.List;
import java.util.Objects;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class RecommendFeedService {

    private final RecommendFeedClient client;
    private final RecommendRepository repository;

    public RecommendPage get(long userId, int limit, String cursor) {
        if (limit < 1 || limit > 50 || (cursor != null && (cursor.isBlank() || cursor.length() > 2048))) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "잘못된 조회 조건입니다");
        }
        if (cursor != null && cursor.startsWith("latest:")) {
            return latest(userId, limit, cursor);
        }
        RecommendFeedClient.Feed feed;
        try {
            feed = client.get(userId, limit, cursor);
        } catch (RestClientException ex) {
            if (cursor != null) {
                if (ex instanceof RestClientResponseException response
                        && (response.getStatusCode().value() == 400 || response.getStatusCode().value() == 410)) {
                    throw new ResponseStatusException(response.getStatusCode(), "추천 세션을 새로 시작하세요");
                }
                throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "추천 조회를 다시 시도하세요");
            }
            return latest(userId, limit, null);
        }
        if (!feed.ready()) {
            if (cursor != null) {
                throw new ResponseStatusException(HttpStatus.GONE, "추천 세션을 새로 시작하세요");
            }
            return latest(userId, limit, null);
        }
        var posts = feed.postIds().isEmpty() ? List.<Post>of() : repository.visible(feed.postIds());
        var byId = posts.stream().collect(Collectors.toMap(Post::getId, Function.identity()));
        var ordered = feed.postIds().stream().distinct().map(byId::get).filter(Objects::nonNull).toList();
        return new RecommendPage(ordered, feed.nextCursor(), "recommend");
    }

    private RecommendPage latest(long userId, int limit, String cursor) {
        LocalDateTime before = LocalDateTime.of(9999, 12, 31, 23, 59, 59);
        long id = Long.MAX_VALUE;
        if (cursor != null) {
            try {
                String decoded = new String(Base64.getUrlDecoder().decode(cursor.substring(7)), StandardCharsets.UTF_8);
                String[] parts = decoded.split("\\|", -1);
                if (parts.length != 3 || Long.parseLong(parts[0]) != userId) {
                    throw new IllegalArgumentException();
                }
                before = LocalDateTime.parse(parts[1]);
                id = Long.parseLong(parts[2]);
                if (id <= 0) throw new IllegalArgumentException();
            } catch (RuntimeException ex) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "잘못된 최신순 커서입니다");
            }
        }
        var page = repository.latest(before, id, PageRequest.of(0, limit + 1));
        var selected = page.stream().limit(limit).toList();
        String next = null;
        if (page.size() > limit) {
            Post last = selected.getLast();
            String value = userId + "|" + last.getCreatedAt() + "|" + last.getId();
            next = "latest:" + Base64.getUrlEncoder().withoutPadding()
                    .encodeToString(value.getBytes(StandardCharsets.UTF_8));
        }
        return new RecommendPage(selected, next, "latest");
    }
}
