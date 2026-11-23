package com.apiece.springboot_sns_sample.domain.recommend;

import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import static org.junit.jupiter.api.Assertions.*;

@EnabledIfEnvironmentVariable(named = "SNS_ACTION_TEST_DATABASE_URL", matches = ".+")
class RecommendActionRepositoryTest {
    private JdbcTemplate jdbcTemplate;
    private RecommendActionRepository recommendActionRepository;

    @BeforeEach
    void setup() {
        var dataSource = new DriverManagerDataSource(System.getenv("SNS_ACTION_TEST_DATABASE_URL"), "postgres", "postgres");
        jdbcTemplate = new JdbcTemplate(dataSource);
        jdbcTemplate.execute("DROP TABLE IF EXISTS post_actions, posts CASCADE");
        jdbcTemplate.execute("CREATE TABLE posts(id bigint PRIMARY KEY, deleted_at timestamptz)");
        jdbcTemplate.execute("CREATE TABLE post_actions(id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, event_id uuid UNIQUE, action text, user_id bigint, post_id bigint)");
        jdbcTemplate.execute("CREATE UNIQUE INDEX post_actions_one_impression ON post_actions(user_id, post_id) WHERE action = 'impression'");
        jdbcTemplate.update("INSERT INTO posts VALUES (4, NULL)");
        recommendActionRepository = new RecommendActionRepository(jdbcTemplate);
    }

    private int storedRows() {
        return jdbcTemplate.queryForObject("SELECT count(*) FROM post_actions", Integer.class);
    }

    @Test
    void repeatedImpressionKeepsOneRow() {
        recommendActionRepository.record(UUID.randomUUID(), RecommendAction.IMPRESSION, 7, 4);
        recommendActionRepository.record(UUID.randomUUID(), RecommendAction.IMPRESSION, 7, 4);
        assertEquals(1, storedRows());
    }

    @Test
    void retriedEventIsStoredOnce() {
        var id = UUID.randomUUID();
        recommendActionRepository.record(id, RecommendAction.CLICK, 7, 4);
        recommendActionRepository.record(id, RecommendAction.CLICK, 7, 4);
        recommendActionRepository.record(id, RecommendAction.CLICK, 8, 4);
        assertEquals(1, storedRows());
        assertEquals(7L, jdbcTemplate.queryForObject("SELECT user_id FROM post_actions", Long.class));
    }

    @Test
    void deletedPostIsSkipped() {
        jdbcTemplate.update("UPDATE posts SET deleted_at = now() WHERE id = 4");
        recommendActionRepository.record(UUID.randomUUID(), RecommendAction.CLICK, 7, 4);
        assertEquals(0, storedRows());
    }
}
