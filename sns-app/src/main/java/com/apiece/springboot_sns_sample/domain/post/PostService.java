package com.apiece.springboot_sns_sample.domain.post;

import com.apiece.springboot_sns_sample.domain.like.Like;
import com.apiece.springboot_sns_sample.domain.like.LikeRepository;
import com.apiece.springboot_sns_sample.domain.media.Media;
import com.apiece.springboot_sns_sample.domain.media.MediaRepository;
import com.apiece.springboot_sns_sample.domain.postview.PostViewService;
import com.apiece.springboot_sns_sample.domain.timeline.TimelineService;
import com.apiece.springboot_sns_sample.domain.user.User;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class PostService {

    private final PostRepository postRepository;
    private final PostViewService postViewService;
    private final MediaRepository mediaRepository;
    private final TimelineService timelineService;
    private final LikeRepository likeRepository;

    public Post createPost(String content, List<Long> mediaIds, User user) {
        if (mediaIds != null && !mediaIds.isEmpty()) {
            List<Media> mediaList = mediaRepository.findAllById(mediaIds);

            if (mediaList.size() != mediaIds.size()) {
                throw new IllegalArgumentException("Some media not found");
            }

            mediaList.forEach(media -> {
                if (!media.getUserId().equals(user.getId())) {
                    throw new IllegalArgumentException("You are not authorized to use this media: " + media.getId());
                }
            });
        }

        Post post = Post.create(content, user, mediaIds);
        Post savedPost = postRepository.save(post);

        timelineService.fanOutToFollowers(savedPost.getId(), user);

        return savedPost;
    }

    public List<PostWithViewCount> getAllPosts() {
        List<Post> posts = postRepository.findAllByDeletedAtIsNullOrderByCreatedAtDesc();
        return enrichWithViewCount(posts);
    }

    public Post getPostById(Long id) {
        return postRepository.findByIdAndDeletedAtIsNull(id)
                .orElseThrow(() -> new IllegalArgumentException("Post not found: " + id));
    }

    public PostWithViewCount getPostByIdWithPostViewIncrement(Long id) {
        Post post = getPostById(id);
        postViewService.incrementPostView(id);
        Long viewCount = postViewService.getPostView(id);
        return new PostWithViewCount(post, viewCount);
    }

    @Transactional
    public Post updatePost(Long id, String content, User user) {
        Post post = getPostById(id);

        if (!post.getUser().getId().equals(user.getId())) {
            throw new IllegalArgumentException("You are not authorized to update this post");
        }

        if (post.isEditExpired()) {
            throw new IllegalArgumentException("Post can only be edited within 1 hour of creation");
        }

        post.updateContent(content);
        return post;
    }

    public void deletePost(Long id, User user) {
        Post post = getPostById(id);

        if (!post.getUser().getId().equals(user.getId())) {
            throw new IllegalArgumentException("You are not authorized to delete this post");
        }

        post.delete();
        postRepository.save(post);
    }

    public List<PostWithViewCount> getPostsByUserId(Long userId) {
        List<Post> posts = postRepository.findByUserIdAndParentIdIsNullAndDeletedAtIsNullOrderByCreatedAtDesc(userId);
        return enrichWithViewCount(posts);
    }

    public List<PostWithViewCount> getRepliesByUserId(Long userId) {
        List<Post> posts = postRepository.findByUserIdAndParentIdIsNotNullAndDeletedAtIsNullOrderByCreatedAtDesc(userId);
        return enrichWithViewCount(posts);
    }

    public PostWithViewCount enrichWithViewCount(Post post) {
        Long viewCount = postViewService.getPostView(post.getId());
        return new PostWithViewCount(post, viewCount);
    }

    public List<PostWithViewCount> enrichWithViewCount(List<Post> posts) {
        return posts.stream()
                .map(this::enrichWithViewCount)
                .toList();
    }

    public PostWithUserContext enrichWithUserContext(Post post, User user) {
        return enrichWithUserContext(List.of(post), user).get(0);
    }

    public List<PostWithUserContext> enrichWithUserContext(List<Post> posts, User user) {
        if (posts.isEmpty()) {
            return List.of();
        }

        List<Long> postIds = posts.stream().map(Post::getId).toList();

        Set<Long> relatedPostIds = posts.stream()
                .flatMap(p -> java.util.stream.Stream.of(p.getRepostId(), p.getQuoteId(), p.getParentId()))
                .filter(Objects::nonNull)
                .collect(Collectors.toSet());

        Map<Long, Post> relatedPostsMap = relatedPostIds.isEmpty()
                ? Map.of()
                : postRepository.findAllByIdInAndDeletedAtIsNull(new ArrayList<>(relatedPostIds)).stream()
                        .collect(Collectors.toMap(Post::getId, p -> p));

        Map<Long, Like> likesMap = likeRepository.findByUserIdAndPostIdInAndDeletedAtIsNull(user.getId(), postIds).stream()
                .collect(Collectors.toMap(l -> l.getPost().getId(), l -> l));

        Map<Long, Post> repostsMap = postRepository.findByUserIdAndRepostIdInAndDeletedAtIsNull(user.getId(), postIds).stream()
                .collect(Collectors.toMap(Post::getRepostId, p -> p));

        return posts.stream()
                .map(post -> buildPostWithUserContext(post, relatedPostsMap, likesMap, repostsMap))
                .toList();
    }

    private PostWithUserContext buildPostWithUserContext(
            Post post,
            Map<Long, Post> relatedPostsMap,
            Map<Long, Like> likesMap,
            Map<Long, Post> repostsMap
    ) {
        Long viewCount = postViewService.getPostView(post.getId());

        Like like = likesMap.get(post.getId());
        Post userRepost = repostsMap.get(post.getId());

        boolean isRepostOrQuote = post.getRepostId() != null || post.getQuoteId() != null;

        return new PostWithUserContext(
                post,
                viewCount,
                like != null,
                like != null ? like.getId() : null,
                userRepost != null,
                userRepost != null ? userRepost.getId() : null,
                post.getRepostId() != null ? relatedPostsMap.get(post.getRepostId()) : null,
                post.getQuoteId() != null ? relatedPostsMap.get(post.getQuoteId()) : null,
                post.getParentId() != null ? relatedPostsMap.get(post.getParentId()) : null,
                isRepostOrQuote ? post.getUser().getId() : null,
                isRepostOrQuote ? post.getUser().getUsername() : null
        );
    }
}
