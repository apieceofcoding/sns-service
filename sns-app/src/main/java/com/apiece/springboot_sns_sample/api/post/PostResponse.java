package com.apiece.springboot_sns_sample.api.post;

import com.apiece.springboot_sns_sample.domain.post.Post;
import com.apiece.springboot_sns_sample.domain.post.PostWithUserContext;
import com.apiece.springboot_sns_sample.domain.post.PostWithViewCount;

import java.time.LocalDateTime;
import java.util.List;

public record PostResponse(
        Long id,
        String content,
        Long userId,
        String username,
        Long userProfileMediaId,
        Integer repostCount,
        Integer likeCount,
        Integer replyCount,
        Long viewCount,
        List<Long> mediaIds,
        Long parentId,
        Long quoteId,
        Long repostId,
        LocalDateTime createdAt,
        LocalDateTime modifiedAt,
        Boolean isLikedByMe,
        Long likeIdByMe,
        Boolean isRepostedByMe,
        Long repostIdByMe,
        PostResponse repostedPost,
        PostResponse quotedPost,
        PostResponse parentPost,
        RepostedBy repostedBy
) {
    public record RepostedBy(Long userId, String username) {
    }

    public static PostResponse from(Post post) {
        return new PostResponse(
                post.getId(),
                post.getContent(),
                post.getUser().getId(),
                post.getUser().getUsername(),
                post.getUser().getProfileMediaId(),
                post.getRepostCount(),
                post.getLikeCount(),
                post.getReplyCount(),
                post.getViewCount(),
                post.getMediaIds(),
                post.getParentId(),
                post.getQuoteId(),
                post.getRepostId(),
                post.getCreatedAt(),
                post.getModifiedAt(),
                false,
                null,
                false,
                null,
                null,
                null,
                null,
                null
        );
    }

    public static PostResponse from(PostWithViewCount postWithViewCount) {
        Post post = postWithViewCount.post();
        return new PostResponse(
                post.getId(),
                post.getContent(),
                post.getUser().getId(),
                post.getUser().getUsername(),
                post.getUser().getProfileMediaId(),
                post.getRepostCount(),
                post.getLikeCount(),
                post.getReplyCount(),
                postWithViewCount.viewCount(),
                post.getMediaIds(),
                post.getParentId(),
                post.getQuoteId(),
                post.getRepostId(),
                post.getCreatedAt(),
                post.getModifiedAt(),
                false,
                null,
                false,
                null,
                null,
                null,
                null,
                null
        );
    }

    public static PostResponse from(PostWithUserContext ctx) {
        Post post = ctx.post();

        PostResponse repostedPostResponse = null;
        RepostedBy repostedBy = null;
        if (ctx.repostedPost() != null) {
            repostedPostResponse = fromSimple(ctx.repostedPost());
            repostedBy = new RepostedBy(
                    ctx.repostedByUserId() != null ? ctx.repostedByUserId() : post.getUser().getId(),
                    ctx.repostedByUsername() != null ? ctx.repostedByUsername() : post.getUser().getUsername()
            );
        }

        PostResponse quotedPostResponse = null;
        if (ctx.quotedPost() != null) {
            quotedPostResponse = fromSimple(ctx.quotedPost());
        }

        PostResponse parentPostResponse = null;
        if (ctx.parentPost() != null) {
            parentPostResponse = fromSimple(ctx.parentPost());
        }

        return new PostResponse(
                post.getId(),
                post.getContent(),
                post.getUser().getId(),
                post.getUser().getUsername(),
                post.getUser().getProfileMediaId(),
                post.getRepostCount(),
                post.getLikeCount(),
                post.getReplyCount(),
                ctx.viewCount(),
                post.getMediaIds(),
                post.getParentId(),
                post.getQuoteId(),
                post.getRepostId(),
                post.getCreatedAt(),
                post.getModifiedAt(),
                ctx.isLikedByMe(),
                ctx.likeIdByMe(),
                ctx.isRepostedByMe(),
                ctx.repostIdByMe(),
                repostedPostResponse,
                quotedPostResponse,
                parentPostResponse,
                repostedBy
        );
    }

    private static PostResponse fromSimple(Post post) {
        return new PostResponse(
                post.getId(),
                post.getContent(),
                post.getUser().getId(),
                post.getUser().getUsername(),
                post.getUser().getProfileMediaId(),
                post.getRepostCount(),
                post.getLikeCount(),
                post.getReplyCount(),
                post.getViewCount(),
                post.getMediaIds(),
                post.getParentId(),
                post.getQuoteId(),
                post.getRepostId(),
                post.getCreatedAt(),
                post.getModifiedAt(),
                false,
                null,
                false,
                null,
                null,
                null,
                null,
                null
        );
    }
}
