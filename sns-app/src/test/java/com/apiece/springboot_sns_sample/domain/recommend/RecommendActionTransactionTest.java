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
        jdbc.execute("DROP TABLE IF EXISTS recommend_events, likes, posts CASCADE");
        jdbc.execute("CREATE TABLE posts(id bigint PRIMARY KEY, deleted_at timestamptz)");
        jdbc.execute("CREATE TABLE likes(id bigint PRIMARY KEY)");
        jdbc.execute("CREATE TABLE recommend_events(id uuid PRIMARY KEY, action text, user_id bigint, post_id bigint)");
        jdbc.update("INSERT INTO posts VALUES (4, NULL)");
        actions = new RecommendActionRepository(jdbc);
    }

    @Test
    void rollbackRemovesLikeAndEvent() {
        var id = UUID.randomUUID();
        assertThrows(IllegalStateException.class, () -> transactions.executeWithoutResult(status -> {
            jdbc.update("INSERT INTO likes VALUES (1)");
            actions.record(id, "like", 7, 4);
            throw new IllegalStateException("simulate failure");
        }));
        assertEquals(0, jdbc.queryForObject("SELECT count(*) FROM likes", Integer.class));
        assertEquals(0, jdbc.queryForObject("SELECT count(*) FROM recommend_events", Integer.class));
    }

    @Test
    void duplicateIsIdempotentAndPayloadCannotBeReused() {
        var id = UUID.randomUUID();
        actions.record(id, "click", 7, 4);
        actions.record(id, "click", 7, 4);
        assertEquals(1, jdbc.queryForObject("SELECT count(*) FROM recommend_events", Integer.class));
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
