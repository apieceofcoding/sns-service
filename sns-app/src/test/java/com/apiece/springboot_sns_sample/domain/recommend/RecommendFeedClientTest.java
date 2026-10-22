package com.apiece.springboot_sns_sample.domain.recommend;

import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.boot.http.client.ClientHttpRequestFactoryBuilder;
import org.springframework.boot.http.client.HttpClientSettings;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.*;

class RecommendFeedClientTest {

    private HttpServer server;
    private final AtomicReference<String> path = new AtomicReference<>();
    private final AtomicReference<String> token = new AtomicReference<>();

    @AfterEach
    void stop() {
        if (server != null) server.stop(0);
    }

    @Test
    void readsPythonContractWithoutTokenAndSendsCursor() throws Exception {
        var client = start(200, """
                {"ready":true,"post_ids":[3,1],"next_cursor":"next","strategy":"latest","stale":false}
                """);
        var feed = client.get(7, 2, "abc==");
        assertThat(feed.postIds()).containsExactly(3L, 1L);
        assertThat(feed.nextCursor()).isEqualTo("next");
        assertThat(path.get()).startsWith("/internal/feeds/7?limit=2&cursor=");
        assertThat(token.get()).isNull();
    }

    @Test
    void rejectsMalformedSuccessBody() throws Exception {
        var client = start(200, "{\"ready\":true}");
        assertThatThrownBy(() -> client.get(7, 20, null)).isInstanceOf(RestClientException.class);
    }

    @Test
    void preservesExpiredCursorStatus() throws Exception {
        var client = start(410, "{\"detail\":\"expired\"}");
        assertThatThrownBy(() -> client.get(7, 20, "old"))
                .isInstanceOf(org.springframework.web.client.HttpClientErrorException.Gone.class);
    }

    private RecommendFeedClient start(int status, String body) throws Exception {
        server = HttpServer.create(new InetSocketAddress("localhost", 0), 0);
        server.createContext("/internal/feeds/7", exchange -> {
            path.set(exchange.getRequestURI().toString());
            token.set(exchange.getRequestHeaders().getFirst("X-Internal-Token"));
            byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "application/json");
            exchange.sendResponseHeaders(status, bytes.length);
            exchange.getResponseBody().write(bytes);
            exchange.close();
        });
        server.start();
        return new RecommendFeedClient(RestClient.builder(), ClientHttpRequestFactoryBuilder.detect(),
                HttpClientSettings.defaults(), "http://localhost:" + server.getAddress().getPort());
    }
}
