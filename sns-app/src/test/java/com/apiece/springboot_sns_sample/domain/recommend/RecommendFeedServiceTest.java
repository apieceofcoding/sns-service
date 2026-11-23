package com.apiece.springboot_sns_sample.domain.recommend;

import com.apiece.springboot_sns_sample.domain.post.Post;
import com.apiece.springboot_sns_sample.domain.post.PostRepository;
import com.apiece.springboot_sns_sample.domain.user.User;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.List;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

class RecommendFeedServiceTest {

    private final RecommendFeedClient recommendFeedClient = mock(RecommendFeedClient.class);
    private final PostRepository postRepository = mock(PostRepository.class);
    private final RecommendFeedService recommendFeedService = new RecommendFeedService(recommendFeedClient, postRepository);

    @Test
    void restoresRankAndKeepsCursorWhenPostsDisappear() {
        when(recommendFeedClient.get(7, 3, null)).thenReturn(new RecommendFeedClient.Feed(true, List.of(3L, 1L, 2L), "next"));
        Post one = post(1), three = post(3);
        when(postRepository.findAllByIdInAndDeletedAtIsNull(List.of(3L, 1L, 2L))).thenReturn(List.of(one, three));
        var result = recommendFeedService.get(7, 3, null);
        assertThat(result.posts()).containsExactly(three, one);
        assertThat(result.nextCursor()).isEqualTo("next");
        assertThat(result.mode()).isEqualTo("recommend");
    }

    @Test
    void missingFeedReturnsPendingWithoutReadingPosts() {
        when(recommendFeedClient.get(7, 20, null)).thenReturn(new RecommendFeedClient.Feed(false, List.of(), null));
        var result = recommendFeedService.get(7, 20, null);
        assertThat(result.mode()).isEqualTo("pending");
        assertThat(result.posts()).isEmpty();
        assertThat(result.nextCursor()).isNull();
        verifyNoInteractions(postRepository);
    }

    private Post post(long id) {
        Post post = Post.create("post", User.create("author", ""), List.of());
        ReflectionTestUtils.setField(post, "id", id);
        return post;
    }
}
