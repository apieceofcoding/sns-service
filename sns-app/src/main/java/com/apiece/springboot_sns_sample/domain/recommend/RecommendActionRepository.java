package com.apiece.springboot_sns_sample.domain.recommend;

import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
@RequiredArgsConstructor
public class RecommendActionRepository {
    private final JdbcTemplate jdbcTemplate;

    public void record(UUID eventId, RecommendAction action, long userId, long postId) {
        jdbcTemplate.update("""
                INSERT INTO post_actions(event_id, action, user_id, post_id)
                SELECT ?, ?, ?, id FROM posts WHERE id = ? AND deleted_at IS NULL
                ON CONFLICT DO NOTHING
                """, eventId, action.name().toLowerCase(), userId, postId);
    }
}
