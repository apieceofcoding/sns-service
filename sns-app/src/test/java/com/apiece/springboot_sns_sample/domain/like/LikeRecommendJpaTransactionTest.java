package com.apiece.springboot_sns_sample.domain.like;

import com.apiece.springboot_sns_sample.domain.post.Post;
import com.apiece.springboot_sns_sample.domain.post.PostRepository;
import com.apiece.springboot_sns_sample.domain.post.PostService;
import com.apiece.springboot_sns_sample.domain.recommend.RecommendActionRepository;
import com.apiece.springboot_sns_sample.domain.user.User;
import com.apiece.springboot_sns_sample.domain.user.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.boot.jdbc.test.autoconfigure.AutoConfigureTestDatabase;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionTemplate;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.when;

@DataJpaTest(properties = {
    "spring.datasource.url=${SNS_ACTION_TEST_DATABASE_URL}",
    "spring.datasource.username=postgres", "spring.datasource.password=postgres",
    "spring.jpa.hibernate.ddl-auto=create-drop"
})
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import({LikeService.class, RecommendActionRepository.class, LikeRecommendJpaTransactionTest.Auditing.class})
@Transactional(propagation = Propagation.NOT_SUPPORTED)
@EnabledIfEnvironmentVariable(named = "SNS_ACTION_TEST_DATABASE_URL", matches = ".+")
class LikeRecommendJpaTransactionTest {
    @org.springframework.boot.test.context.TestConfiguration
    @org.springframework.data.jpa.repository.config.EnableJpaAuditing
    static class Auditing {}

    @Autowired LikeService service;
    @Autowired PostRepository posts;
    @Autowired UserRepository users;
    @Autowired JdbcTemplate jdbc;
    @Autowired PlatformTransactionManager manager;
    @MockitoBean PostService postService;
    private User reader;
    private Post post;

    @BeforeEach
    void setup() {
        jdbc.execute("DROP TABLE IF EXISTS recommend_events");
        jdbc.execute("CREATE TABLE recommend_events(id uuid PRIMARY KEY, action text, user_id bigint, post_id bigint)");
        new TransactionTemplate(manager).executeWithoutResult(status -> {
            reader = users.save(User.create("reader-" + java.util.UUID.randomUUID(), ""));
            post = posts.save(Post.create("hello", reader, null));
        });
        when(postService.getPostById(post.getId())).thenReturn(post);
    }

    @Test
    void jpaLikeAndJdbcEventCommitTogether() {
        service.createLike(post.getId(), reader);
        assertEquals(1, jdbc.queryForObject("SELECT count(*) FROM likes WHERE post_id = ?", Integer.class, post.getId()));
        assertEquals(1, jdbc.queryForObject("SELECT count(*) FROM recommend_events WHERE post_id = ?", Integer.class, post.getId()));
    }

    @Test
    void eventFailureRollsBackJpaLikeAndCounter() {
        jdbc.execute("ALTER TABLE recommend_events ADD CHECK (action <> 'like')");
        assertThrows(org.springframework.dao.DataIntegrityViolationException.class,
                () -> service.createLike(post.getId(), reader));
        assertEquals(0, jdbc.queryForObject("SELECT count(*) FROM likes WHERE post_id = ?", Integer.class, post.getId()));
        assertEquals(0, jdbc.queryForObject("SELECT like_count FROM posts WHERE id = ?", Integer.class, post.getId()));
        assertEquals(0, jdbc.queryForObject("SELECT count(*) FROM recommend_events", Integer.class));
    }
}
