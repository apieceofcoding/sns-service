package com.apiece.springboot_sns_sample.domain.recommend;

import com.apiece.springboot_sns_sample.domain.post.Post;
import com.apiece.springboot_sns_sample.domain.user.User;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatusCode;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDateTime;
import java.util.List;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class RecommendFeedServiceTest {

    private final RecommendFeedClient client = mock(RecommendFeedClient.class);
    private final RecommendRepository repository = mock(RecommendRepository.class);
    private final RecommendFeedService service = new RecommendFeedService(client, repository);

    @Test
    void restoresRankAndKeepsCursorWhenPostsDisappear() {
        when(client.get(7, 3, null)).thenReturn(new RecommendFeedClient.Feed(true, List.of(3L, 1L, 2L), "next"));
        Post one = post(1), three = post(3);
        when(repository.visible(List.of(3L, 1L, 2L))).thenReturn(List.of(one, three));

        var result = service.get(7, 3, null);

        assertThat(result.posts()).containsExactly(three, one);
        assertThat(result.nextCursor()).isEqualTo("next");
        assertThat(result.mode()).isEqualTo("recommend");
    }

    @Test
    void fallbackStaysInLatestModeAndUsesTimeAndIdCursor() {
        when(client.get(7, 1, null)).thenThrow(new ResourceAccessException("offline"));
        Post newest = post(1), older = post(99);
        when(repository.latest(any(), anyLong(), eq(PageRequest.of(0, 2)))).thenReturn(List.of(newest, older));
        var first = service.get(7, 1, null);
        assertThat(first.mode()).isEqualTo("latest");
        assertThat(first.nextCursor()).startsWith("latest:");
        when(repository.latest(newest.getCreatedAt(), 1, PageRequest.of(0, 2))).thenReturn(List.of(older));

        var next = service.get(7, 1, first.nextCursor());

        assertThat(next.posts()).containsExactly(older);
        assertThat(next.nextCursor()).isNull();
        verify(client, times(1)).get(anyLong(), anyInt(), any());
        assertThatThrownBy(() -> service.get(8, 1, first.nextCursor()))
                .isInstanceOfSatisfying(ResponseStatusException.class,
                        ex -> assertThat(ex.getStatusCode().value()).isEqualTo(400));
    }

    @Test
    void notReadyFirstPageFallsBack() {
        when(client.get(7, 20, null)).thenReturn(new RecommendFeedClient.Feed(false, List.of(), null));
        when(repository.latest(any(), anyLong(), any())).thenReturn(List.of());
        assertThat(service.get(7, 20, null).mode()).isEqualTo("latest");
    }

    @Test
    void readyEmptySnapshotDoesNotFallBack() {
        when(client.get(7, 20, null)).thenReturn(new RecommendFeedClient.Feed(true, List.of(), null));
        assertThat(service.get(7, 20, null).mode()).isEqualTo("recommend");
        verifyNoInteractions(repository);
    }

    @ParameterizedTest
    @ValueSource(ints = {400, 410, 503})
    void continuationErrorsNeverSwitchToLatest(int status) {
        when(client.get(7, 20, "cursor")).thenThrow(new RestClientResponseException(
                "upstream", HttpStatusCode.valueOf(status), "", null, null, null));
        assertThatThrownBy(() -> service.get(7, 20, "cursor"))
                .isInstanceOfSatisfying(ResponseStatusException.class,
                        ex -> assertThat(ex.getStatusCode().value()).isEqualTo(status));
        verifyNoInteractions(repository);
    }

    @Test
    void notReadyContinuationExpires() {
        when(client.get(7, 20, "cursor")).thenReturn(new RecommendFeedClient.Feed(false, List.of(), null));
        assertThatThrownBy(() -> service.get(7, 20, "cursor"))
                .isInstanceOfSatisfying(ResponseStatusException.class,
                        ex -> assertThat(ex.getStatusCode().value()).isEqualTo(410));
        verifyNoInteractions(repository);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "latest:invalid", "latest:", " "})
    void rejectsInvalidCursor(String cursor) {
        assertThatThrownBy(() -> service.get(7, 20, cursor)).isInstanceOf(ResponseStatusException.class);
        verifyNoInteractions(client, repository);
    }

    @ParameterizedTest
    @ValueSource(ints = {0, 51})
    void rejectsInvalidLimit(int limit) {
        assertThatThrownBy(() -> service.get(7, limit, null)).isInstanceOf(ResponseStatusException.class);
        verifyNoInteractions(client, repository);
    }

    private Post post(long id) {
        Post post = Post.create("post", User.create("author", ""), List.of());
        ReflectionTestUtils.setField(post, "id", id);
        ReflectionTestUtils.setField(post, "createdAt", LocalDateTime.of(2026, 10, 13, 12, 0));
        return post;
    }
}
