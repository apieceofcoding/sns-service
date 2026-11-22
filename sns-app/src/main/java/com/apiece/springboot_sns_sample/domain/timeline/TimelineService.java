package com.apiece.springboot_sns_sample.domain.timeline;

import com.apiece.springboot_sns_sample.domain.follow.Follow;
import com.apiece.springboot_sns_sample.domain.follow.FollowCount;
import com.apiece.springboot_sns_sample.domain.follow.FollowCountService;
import com.apiece.springboot_sns_sample.domain.follow.FollowRepository;
import com.apiece.springboot_sns_sample.domain.post.Post;
import com.apiece.springboot_sns_sample.domain.post.PostRepository;
import com.apiece.springboot_sns_sample.domain.user.User;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.function.Function;

import static java.util.stream.Collectors.toMap;

@Service
@RequiredArgsConstructor
public class TimelineService {

    private final TimelineRepository timelineRepository;
    private final FollowRepository followRepository;
    private final FollowCountService followCountService;
    private final PostRepository postRepository;

    public void fanOutToFollowers(Long postId, User author) {
        FollowCount followCount = followCountService.getFollowCountOrDefault(author.getId());

        timelineRepository.addPostToTimeline(author.getId(), postId);

        if (followCount.isCeleb()) {
            timelineRepository.addCelebPost(author.getId(), postId);
            return;
        }

        List<Follow> follows = followRepository.findByFolloweeIdAndDeletedAtIsNull(author.getId());
        follows.parallelStream()
                .forEach(follow -> timelineRepository.addPostToTimeline(follow.getFollowerId(), postId));
    }

    public TimelinePage getTimeline(User user, Double cursor, int limit) {
        List<Follow> follows = followRepository.findByFollowerIdAndDeletedAtIsNull(user.getId());
        follows.parallelStream()
                .map(Follow::getFolloweeId)
                .map(followCountService::getFollowCountOrDefault)
                .filter(FollowCount::isCeleb)
                .flatMap(followCount -> timelineRepository.getCelebPosts(followCount.getUserId(), 5).stream())
                .forEach(postId -> timelineRepository.addPostToTimelineIfAbsent(user.getId(), postId));

        List<TimelineEntry> entries = timelineRepository.getTimeline(user.getId(), cursor, limit);

        if (entries.isEmpty()) {
            return new TimelinePage(List.of(), null, false);
        }

        List<Long> postIds = entries.stream().map(TimelineEntry::postId).toList();
        Map<Long, Post> postMap = postRepository.findAllByIdInAndDeletedAtIsNull(postIds).stream()
                .collect(toMap(Post::getId, Function.identity()));

        List<Post> posts = entries.stream()
                .map(entry -> postMap.get(entry.postId()))
                .filter(Objects::nonNull)
                .toList();

        Double nextCursor = entries.getLast().score();
        boolean hasMore = entries.size() >= limit;

        return new TimelinePage(posts, nextCursor, hasMore);
    }
}
