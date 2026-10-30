package com.apiece.springboot_sns_sample.domain.recommend;

import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.web.server.ResponseStatusException;

@Repository
@RequiredArgsConstructor
public class RecommendActionRepository {
    private final JdbcTemplate jdbc;

    public void record(UUID eventId, String action, long userId, long postId) {
        int inserted = jdbc.update("""
                INSERT INTO recommend_events(id, action, user_id, post_id)
                SELECT ?, ?, ?, id FROM posts WHERE id = ? AND deleted_at IS NULL
                ON CONFLICT (id) DO NOTHING
                """, eventId, action, userId, postId);
        if (inserted == 1) return;
        var existing = jdbc.queryForList("SELECT action, user_id, post_id FROM recommend_events WHERE id = ?", eventId);
        if (existing.isEmpty()) throw new ResponseStatusException(HttpStatus.NOT_FOUND, "post not found");
        var event = existing.getFirst();
        if (!action.equals(event.get("action")) || !Long.valueOf(userId).equals(event.get("user_id"))
                || !Long.valueOf(postId).equals(event.get("post_id"))) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "event ID already used");
        }
    }
}
