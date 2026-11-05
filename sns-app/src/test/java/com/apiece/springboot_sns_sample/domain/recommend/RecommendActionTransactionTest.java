package com.apiece.springboot_sns_sample.domain.recommend;

import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.server.ResponseStatusException;
import static org.junit.jupiter.api.Assertions.*;

@EnabledIfEnvironmentVariable(named = "SNS_ACTION_TEST_DATABASE_URL", matches = ".+")
class RecommendActionTransactionTest {
    private JdbcTemplate jdbc;
    private TransactionTemplate transactions;
    private RecommendActionRepository actions;

    @BeforeEach
    void setup() {
        var dataSource = new DriverManagerDataSource(System.getenv("SNS_ACTION_TEST_DATABASE_URL"), "postgres", "postgres");
        jdbc = new JdbcTemplate(dataSource);
        transactions = new TransactionTemplate(new DataSourceTransactionManager(dataSource));
        jdbc.execute("DROP TABLE IF EXISTS post_actions, posts CASCADE");
        jdbc.execute("CREATE TABLE posts(id bigint PRIMARY KEY, deleted_at timestamptz)");
        jdbc.execute("CREATE TABLE post_actions(id uuid PRIMARY KEY, action text, user_id bigint, post_id bigint)");
        jdbc.execute("CREATE UNIQUE INDEX post_actions_one_impression ON post_actions(user_id, post_id) WHERE action = 'impression'");
        jdbc.update("INSERT INTO posts VALUES (4, NULL)");
        actions = new RecommendActionRepository(jdbc);
    }

    @Test
    void repeatedImpressionKeepsOneRow() {
        actions.record(UUID.randomUUID(), "impression", 7, 4);
        actions.record(UUID.randomUUID(), "impression", 7, 4);
        assertEquals(1, jdbc.queryForObject("SELECT count(*) FROM post_actions", Integer.class));
    }

    @Test
    void duplicateIsIdempotentAndPayloadCannotBeReused() {
        var id = UUID.randomUUID();
        actions.record(id, "click", 7, 4);
        actions.record(id, "click", 7, 4);
        assertEquals(1, jdbc.queryForObject("SELECT count(*) FROM post_actions", Integer.class));
        assertEquals(409, assertThrows(ResponseStatusException.class,
                () -> actions.record(id, "click", 8, 4)).getStatusCode().value());
    }

    @Test
    void deletedPostIsRejected() {
        jdbc.update("UPDATE posts SET deleted_at = now() WHERE id = 4");
        assertEquals(404, assertThrows(ResponseStatusException.class,
                () -> actions.record(UUID.randomUUID(), "click", 7, 4)).getStatusCode().value());
    }
}
