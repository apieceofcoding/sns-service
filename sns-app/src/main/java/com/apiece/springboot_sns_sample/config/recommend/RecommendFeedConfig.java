package com.apiece.springboot_sns_sample.config.recommend;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.http.client.ClientHttpRequestFactoryBuilder;
import org.springframework.boot.http.client.HttpClientSettings;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestClient;

import java.time.Duration;

@Configuration
public class RecommendFeedConfig {

    @Bean
    public RestClient recommendFeedRestClient(RestClient.Builder builder,
                                               ClientHttpRequestFactoryBuilder<?> requestFactoryBuilder,
                                               HttpClientSettings settings,
                                               @Value("${recommend.feed-base-url}") String feedBaseUrl) {
        return builder
                .baseUrl(feedBaseUrl)
                .requestFactory(requestFactoryBuilder.build(
                        settings.withTimeouts(Duration.ofMillis(500), Duration.ofSeconds(2))))
                .build();
    }
}
