package com.apiece.springboot_sns_sample.api;

import com.apiece.springboot_sns_sample.config.recommend.RecommendConfig;
import com.apiece.springboot_sns_sample.api.demo.TraceResponse;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.test.json.JsonCompareMode;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import com.apiece.springboot_sns_sample.config.recommend.RecommendProperties;
import com.apiece.springboot_sns_sample.domain.recommend.RecommendClient;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.context.Scope;
import io.opentelemetry.api.common.AttributeKey;
import io.opentelemetry.api.trace.StatusCode;
import io.opentelemetry.context.Context;
import io.opentelemetry.sdk.OpenTelemetrySdk;
import io.opentelemetry.sdk.trace.ReadWriteSpan;
import io.opentelemetry.sdk.trace.ReadableSpan;
import io.opentelemetry.sdk.trace.SdkTracerProvider;
import io.opentelemetry.sdk.trace.SpanProcessor;
import io.opentelemetry.sdk.trace.data.SpanData;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestClient;
import org.springframework.boot.http.client.ClientHttpRequestFactoryBuilder;
import org.springframework.boot.http.client.HttpClientSettings;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;

class TraceIncidentTest {

    private static final Duration TIMEOUT = Duration.ofMillis(200);

    private static final String FAST_RANK = "{\"userId\":7,\"segment\":\"ga\",\"rankedPostIds\":[101],\"tookMs\":40}";

    private final CapturingSpanProcessor spans = new CapturingSpanProcessor();

    private HttpServer server;
    private OpenTelemetrySdk openTelemetry;

    @AfterEach
    void tearDown() {
        if (openTelemetry != null) {
            openTelemetry.close();
        }
        if (server != null) {
            server.stop(0);
        }
    }

    @Test
    @DisplayName("추천 타임아웃은 503으로 응답하고 Span에 오류를 남긴다")
    void recordsRankTimeout() throws IOException {
        startServer(
                exchange -> {
                    sleep(TIMEOUT.toMillis() * 3);
                    respond(exchange, 200, FAST_RANK);
                });

        ResponseEntity<TraceResponse> response = controller().trace("hello", 3L, "incident");

        assertThat(Span.current().getSpanContext().isValid()).isFalse();
        assertThat(response.getStatusCode().value()).isEqualTo(503);

        SpanData span = endedSpan();
        assertThat(span.getName()).isEqualTo("recommend-fetch");
        assertThat(span.getStatus().getStatusCode()).isEqualTo(StatusCode.ERROR);
        assertThat(span.getEvents()).anySatisfy(event -> assertThat(event.getName()).isEqualTo("exception"));
    }

    @Test
    @DisplayName("장애 분석은 추천 API를 한 번만 호출한다")
    void callsRankOnce() throws IOException {
        AtomicInteger calls = new AtomicInteger();
        startServer(exchange -> {
            calls.incrementAndGet();
            assertThat(exchange.getRequestMethod()).isEqualTo("POST");
            respond(exchange, 200, FAST_RANK);
        });

        assertThat(controller().trace("hello", 7L, "incident").getStatusCode().value()).isEqualTo(200);
        assertThat(calls).hasValue(1);
        assertThat(spans.ended).hasSize(1);
    }

    @Test
    @DisplayName("장애 분석 성공 응답은 message와 rankedPostIds를 포함한다")
    void returnsOnlyFeedFieldsOnSuccess() throws Exception {
        startServer(
                exchange -> respond(exchange, 200, FAST_RANK));

        MockMvcBuilders.standaloneSetup(controller()).build()
                .perform(get("/api/v1/demo/trace").param("scenario", "incident"))
                .andExpect(status().isOk())
                .andExpect(content().json("""
                        {"message":"hello","rankedPostIds":[101]}
                        """, JsonCompareMode.STRICT));
    }

    @Test
    @DisplayName("장애 분석 실패 응답은 null rankedPostIds와 HTTP 503을 반환한다")
    void returnsNullPostIdsOnFailure() throws Exception {
        startServer(
                exchange -> respond(exchange, 500, "{\"error\":\"boom\"}"));

        MockMvcBuilders.standaloneSetup(controller()).build()
                .perform(get("/api/v1/demo/trace").param("scenario", "incident").param("userId", "3"))
                .andExpect(status().isServiceUnavailable())
                .andExpect(content().json("""
                        {"message":"hello","rankedPostIds":null}
                        """, JsonCompareMode.STRICT));
    }

    @Test
    @DisplayName("직접 생성한 Span은 기존 요청 Span의 자식으로 생성되고 종료 후 부모로 복원된다")
    void createsChildSpanAndRestoresParent() throws IOException {
        startServer(
                exchange -> respond(exchange, 200, FAST_RANK));
        ObservabilityDemoController controller = controller();
        Span parent = openTelemetry.getTracer("test").spanBuilder("http-request").startSpan();
        try (Scope ignored = parent.makeCurrent()) {
            controller.trace("hello", 7L, "incident");

            SpanData child = endedSpan();
            assertThat(child.getName()).isEqualTo("recommend-fetch");
            assertThat(child.getParentSpanId()).isEqualTo(parent.getSpanContext().getSpanId());
            assertThat(child.getTraceId()).isEqualTo(parent.getSpanContext().getTraceId());
            assertThat(child.getAttributes().get(AttributeKey.longKey("user.id"))).isEqualTo(7L);
            assertThat(Span.current().getSpanContext()).isEqualTo(parent.getSpanContext());
        } finally {
            parent.end();
        }
    }

    @Test
    void defaultTraceKeepsResponseAndCreatesSpan() throws Exception {
        startServer(exchange -> respond(exchange, 200, FAST_RANK));
        MockMvcBuilders.standaloneSetup(controller()).build()
                .perform(get("/api/v1/demo/trace").param("message", "part-7"))
                .andExpect(status().isOk())
                .andExpect(content().json("""
                        {"message":"part-7","rankedPostIds":[101]}
                        """, JsonCompareMode.STRICT));
        assertThat(endedSpan().getName()).isEqualTo("recommend-fetch");
    }

    @Test
    void unknownScenarioIsRejectedWithoutCallingRecommend() throws Exception {
        AtomicInteger calls = new AtomicInteger();
        startServer(exchange -> {
            calls.incrementAndGet();
            respond(exchange, 200, FAST_RANK);
        });
        MockMvcBuilders.standaloneSetup(controller()).build()
                .perform(get("/api/v1/demo/trace").param("scenario", "typo"))
                .andExpect(status().isBadRequest());
        assertThat(calls).hasValue(0);
        assertThat(spans.ended).isEmpty();
    }

    @Test
    void defaultTraceStillPropagatesRecommendErrors() throws Exception {
        startServer(exchange -> respond(exchange, 500, "{}"));
        var mvc = MockMvcBuilders.standaloneSetup(controller()).build();
        org.assertj.core.api.Assertions.assertThatThrownBy(() -> mvc.perform(get("/api/v1/demo/trace")))
                .hasCauseInstanceOf(org.springframework.web.client.RestClientException.class);
        assertThat(endedSpan().getStatus().getStatusCode()).isEqualTo(StatusCode.ERROR);
        assertThat(Span.current().getSpanContext().isValid()).isFalse();
    }

    @Test
    void feedMappingIsRemoved() throws Exception {
        startServer(exchange -> respond(exchange, 200, FAST_RANK));
        MockMvcBuilders.standaloneSetup(controller()).build()
                .perform(get("/api/v1/demo/feed"))
                .andExpect(status().isNotFound());
    }

    @Test
    void usesBootManagedOpenTelemetryWithoutAspectj() {
        new org.springframework.boot.test.context.runner.ApplicationContextRunner()
                .withConfiguration(org.springframework.boot.autoconfigure.AutoConfigurations.of(
                        org.springframework.boot.opentelemetry.autoconfigure.OpenTelemetrySdkAutoConfiguration.class))
                .withBean(com.apiece.springboot_sns_sample.domain.recommend.RecommendService.class,
                        () -> org.mockito.Mockito.mock(com.apiece.springboot_sns_sample.domain.recommend.RecommendService.class))
                .withUserConfiguration(ObservabilityDemoController.class)
                .run(context -> {
                    assertThat(context).hasNotFailed();
                    assertThat(context).hasSingleBean(io.opentelemetry.api.OpenTelemetry.class);
                    assertThat(context).hasSingleBean(ObservabilityDemoController.class);
                });
    }

    private ObservabilityDemoController controller() {
        RecommendProperties properties = new RecommendProperties(
                "http://localhost:" + server.getAddress().getPort(),
                TIMEOUT,
                TIMEOUT
        );
        RestClient restClient = new RecommendConfig()
                .recommendRestClient(RestClient.builder(), ClientHttpRequestFactoryBuilder.detect(),
                        HttpClientSettings.defaults(), properties);

        openTelemetry = OpenTelemetrySdk.builder()
                .setTracerProvider(SdkTracerProvider.builder().addSpanProcessor(spans).build())
                .build();

        return new ObservabilityDemoController(
                new com.apiece.springboot_sns_sample.domain.recommend.RecommendService(new RecommendClient(restClient)),
                openTelemetry);
    }

    private SpanData endedSpan() {
        assertThat(spans.ended).hasSize(1);
        return spans.ended.getFirst();
    }

    private void startServer(HttpHandler rankHandler) throws IOException {
        server = HttpServer.create(new InetSocketAddress("localhost", 0), 0);
        server.createContext("/v1/rank", closing(rankHandler));
        server.start();
    }

    private static HttpHandler closing(HttpHandler handler) {
        return exchange -> {
            try {
                handler.handle(exchange);
            } finally {
                exchange.close();
            }
        };
    }

    private static void respond(HttpExchange exchange, int status, String body) throws IOException {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().add("Content-Type", "application/json");
        exchange.sendResponseHeaders(status, bytes.length);
        try (OutputStream out = exchange.getResponseBody()) {
            out.write(bytes);
        }
    }

    private static void sleep(long millis) {
        try {
            Thread.sleep(millis);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private static final class CapturingSpanProcessor implements SpanProcessor {

        private final List<SpanData> ended = new CopyOnWriteArrayList<>();

        @Override
        public void onStart(Context parentContext, ReadWriteSpan span) {
        }

        @Override
        public boolean isStartRequired() {
            return false;
        }

        @Override
        public void onEnd(ReadableSpan span) {
            ended.add(span.toSpanData());
        }

        @Override
        public boolean isEndRequired() {
            return true;
        }
    }
}
