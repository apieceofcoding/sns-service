package com.apiece.springboot_sns_sample.domain.like;

import com.apiece.springboot_sns_sample.domain.post.Post;
import com.apiece.springboot_sns_sample.domain.post.PostRepository;
import com.apiece.springboot_sns_sample.domain.post.PostService;
import com.apiece.springboot_sns_sample.domain.recommend.RecommendActionRepository;
import com.apiece.springboot_sns_sample.domain.user.User;
import org.junit.jupiter.api.Test;
import java.util.UUID;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.*;

class LikeRecommendActionTest {
    @Test
    void writesLikeAndEventTogether() {
        var likes = mock(LikeRepository.class);
        var posts = mock(PostRepository.class);
        var postService = mock(PostService.class);
        var actions = mock(RecommendActionRepository.class);
        var user = mock(User.class);
        when(user.getId()).thenReturn(7L);
        when(postService.getPostById(4L)).thenReturn(mock(Post.class));
        var service = new LikeService(likes, posts, postService, actions);
        service.createLike(4L, user);
        var order = inOrder(likes, posts, actions);
        order.verify(likes).save(any(Like.class));
        order.verify(posts).incrementLikeCount(4L);
        order.verify(actions).record(any(UUID.class), eq("like"), eq(7L), eq(4L));
    }

    @Test
    void duplicateLikeDoesNotCreateEvent() {
        var likes = mock(LikeRepository.class);
        var actions = mock(RecommendActionRepository.class);
        var user = mock(User.class);
        when(user.getId()).thenReturn(7L);
        when(likes.existsByUserIdAndPostIdAndDeletedAtIsNull(7L, 4L)).thenReturn(true);
        var service = new LikeService(likes, mock(PostRepository.class), mock(PostService.class), actions);
        assertThrows(IllegalArgumentException.class, () -> service.createLike(4L, user));
        verifyNoInteractions(actions);
    }
}
