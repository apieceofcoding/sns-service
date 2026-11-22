package com.apiece.springboot_sns_sample.domain.timeline;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.ZSetOperations;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Set;

@Slf4j
@Repository
@RequiredArgsConstructor
public class TimelineRedisRepository implements TimelineRepository {

    private final RedisTemplate<String, String> redisTemplate;

    private static final String TIMELINE_KEY_PREFIX = "timeline:user:";
    private static final String CELEB_POSTS_KEY_PREFIX = "timeline:fanout:celeb:";
    private static final int MAX_CELEB_POSTS_SIZE = 5;
    private static final int MAX_TIMELINE_SIZE = 1000;

    @Override
    public void addPostToTimeline(Long userId, Long postId) {
        String key = TIMELINE_KEY_PREFIX + userId;
        double score = System.currentTimeMillis();
        log.info("ZADD {} {} {}", key, score, postId);
        redisTemplate.opsForZSet().add(key, postId.toString(), score);

        Long size = redisTemplate.opsForZSet().size(key);
        if (size != null && size > MAX_TIMELINE_SIZE) {
            redisTemplate.opsForZSet().removeRange(key, 0, size - MAX_TIMELINE_SIZE - 1);
        }
    }

    @Override
    public void addPostToTimelineIfAbsent(Long userId, Long postId) {
        String key = TIMELINE_KEY_PREFIX + userId;
        Double existingScore = redisTemplate.opsForZSet().score(key, postId.toString());
        if (existingScore != null) {
            return;
        }
        double score = System.currentTimeMillis();
        log.info("ZADD NX {} {} {}", key, score, postId);
        redisTemplate.opsForZSet().addIfAbsent(key, postId.toString(), score);
    }

    @Override
    public List<TimelineEntry> getTimeline(Long userId, Double cursor, int limit) {
        String key = TIMELINE_KEY_PREFIX + userId;
        double maxScore = (cursor == null) ? Double.MAX_VALUE : cursor - 0.001; // for exclusive: maxCursor < lastMaxCursor

        String maxScoreLog = (cursor == null) ? "+inf" : String.valueOf(maxScore);
        log.info("ZREVRANGEBYSCORE {} {} -inf LIMIT 0 {}", key, maxScoreLog, limit);

        Set<ZSetOperations.TypedTuple<String>> results = redisTemplate.opsForZSet()
                .reverseRangeByScoreWithScores(key, Double.MIN_VALUE, maxScore, 0, limit);

        if (results == null || results.isEmpty()) {
            return List.of();
        }

        return results.stream()
                .filter(tuple -> tuple.getValue() != null && tuple.getScore() != null)
                .map(tuple -> new TimelineEntry(Long.parseLong(tuple.getValue()), tuple.getScore()))
                .toList();
    }

    @Override
    public void addCelebPost(Long celebUserId, Long postId) {
        String key = CELEB_POSTS_KEY_PREFIX + celebUserId;
        double score = System.currentTimeMillis();
        log.info("ZADD {} {} {}", key, score, postId);
        redisTemplate.opsForZSet().add(key, postId.toString(), score);

        Long size = redisTemplate.opsForZSet().size(key);
        if (size != null && size > MAX_CELEB_POSTS_SIZE) {
            redisTemplate.opsForZSet().removeRange(key, 0, size - MAX_CELEB_POSTS_SIZE - 1);
        }
    }

    @Override
    public List<Long> getCelebPosts(Long celebUserId, int limit) {
        String key = CELEB_POSTS_KEY_PREFIX + celebUserId;
        int actualLimit = Math.min(limit, MAX_CELEB_POSTS_SIZE);

        log.info("ZREVRANGE {} 0 {}", key, actualLimit - 1);

        Set<String> postIds = redisTemplate.opsForZSet().reverseRange(key, 0, actualLimit - 1);

        if (postIds == null) return List.of();
        return postIds.stream()
                .map(Long::parseLong)
                .toList();
    }
}
