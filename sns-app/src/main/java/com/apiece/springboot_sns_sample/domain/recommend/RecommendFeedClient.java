package com.apiece.springboot_sns_sample.domain.recommend;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.util.List;
import java.util.Optional;

@Component
@RequiredArgsConstructor
public class RecommendFeedClient {

    private final RestClient recommendFeedRestClient;

    public Feed get(long userId, int limit, String cursor) {
        Feed feed = recommendFeedRestClient.get()
                .uri(uri -> uri.path("/internal/feeds/{userId}")
                        .queryParam("limit", limit)
                        .queryParamIfPresent("cursor", Optional.ofNullable(cursor))
                        .build(userId))
                .retrieve()
                .body(Feed.class);
        if (feed == null || feed.postIds() == null) {
            throw new RestClientException("Invalid recommend response");
        }
        return feed;
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Feed(boolean ready, @JsonProperty("post_ids") List<Long> postIds,
                       @JsonProperty("next_cursor") String nextCursor) {
    }
}
