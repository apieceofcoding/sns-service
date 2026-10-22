package com.apiece.springboot_sns_sample.domain.recommend;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.http.client.ClientHttpRequestFactoryBuilder;
import org.springframework.boot.http.client.HttpClientSettings;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.time.Duration;
import java.util.List;
import java.util.Optional;

@Component
public class RecommendFeedClient {

    private final RestClient client;

    public RecommendFeedClient(RestClient.Builder builder,
                                ClientHttpRequestFactoryBuilder<?> factory,
                                HttpClientSettings settings,
                                @Value("${recommend.feed-base-url}") String baseUrl) {
        client = builder.baseUrl(baseUrl)
                .requestFactory(factory.build(settings.withTimeouts(
                        Duration.ofMillis(500), Duration.ofSeconds(2))))
                .build();
    }

    public Feed get(long userId, int limit, String cursor) {
        Feed feed = client.get()
                .uri(uri -> uri.path("/internal/feeds/{userId}")
                        .queryParam("limit", limit)
                        .queryParamIfPresent("cursor", Optional.ofNullable(cursor))
                        .build(userId))
                .retrieve()
                .body(Feed.class);
        if (feed == null || feed.ready() == null || feed.postIds() == null
                || feed.postIds().size() > limit
                || feed.postIds().stream().anyMatch(id -> id == null || id <= 0)) {
            throw new RestClientException("Invalid recommend response");
        }
        return feed;
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Feed(Boolean ready, @JsonProperty("post_ids") List<Long> postIds,
                       @JsonProperty("next_cursor") String nextCursor) {
    }
}
