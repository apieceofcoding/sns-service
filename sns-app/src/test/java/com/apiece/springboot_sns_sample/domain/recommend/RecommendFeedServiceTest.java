package com.apiece.springboot_sns_sample.domain.recommend;

import com.apiece.springboot_sns_sample.domain.post.Post;
import com.apiece.springboot_sns_sample.domain.post.PostRepository;
import com.apiece.springboot_sns_sample.domain.user.User;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.client.ResourceAccessException;

import java.util.List;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

class RecommendFeedServiceTest {

    private final RecommendFeedClient client = mock(RecommendFeedClient.class);
    private final PostRepository posts = mock(PostRepository.class);
    private final RecommendFeedService service = new RecommendFeedService(client, posts);

    @Test
    void restoresRankAndKeepsCursorWhenPostsDisappear() {
        when(client.get(7, 3, null)).thenReturn(new RecommendFeedClient.Feed(true, List.of(3L, 1L, 2L), "next"));
        Post one = post(1), three = post(3);
        when(posts.findAllByIdInAndDeletedAtIsNull(List.of(3L, 1L, 2L))).thenReturn(List.of(one, three));
        var result = service.get(7, 3, null);
        assertThat(result.posts()).containsExactly(three, one);
        assertThat(result.nextCursor()).isEqualTo("next");
        assertThat(result.mode()).isEqualTo("recommend");
    }

    @Test
    void missingFeedReturnsPendingWithoutReadingPosts() {
        when(client.get(7, 20, null)).thenReturn(new RecommendFeedClient.Feed(false, List.of(), null));
        var result = service.get(7, 20, null);
        assertThat(result.mode()).isEqualTo("pending");
        assertThat(result.posts()).isEmpty();
        assertThat(result.nextCursor()).isNull();
        verifyNoInteractions(posts);
    }

    @Test
    void readyEmptySnapshotRemainsARecommend() {
        when(client.get(7, 20, null)).thenReturn(new RecommendFeedClient.Feed(true, List.of(), null));
        assertThat(service.get(7, 20, null).mode()).isEqualTo("recommend");
        verifyNoInteractions(posts);
    }

    @Test
    void forwardsCursorAndKeepsItEvenWhenAllPostsWereDeleted() {
        when(client.get(7, 2, "old")).thenReturn(new RecommendFeedClient.Feed(true, List.of(1L), "next"));
        when(posts.findAllByIdInAndDeletedAtIsNull(List.of(1L))).thenReturn(List.of());
        var result = service.get(7, 2, "old");
        assertThat(result.posts()).isEmpty();
        assertThat(result.nextCursor()).isEqualTo("next");
    }

    @Test
    void connectionFailureDoesNotQueryAnUnrelatedFeed() {
        when(client.get(7, 20, null)).thenThrow(new ResourceAccessException("offline"));
        assertThatThrownBy(() -> service.get(7, 20, null)).isInstanceOf(ResourceAccessException.class);
        verifyNoInteractions(posts);
    }

    private Post post(long id) {
        Post post = Post.create("post", User.create("author", ""), List.of());
        ReflectionTestUtils.setField(post, "id", id);
        return post;
    }
}
