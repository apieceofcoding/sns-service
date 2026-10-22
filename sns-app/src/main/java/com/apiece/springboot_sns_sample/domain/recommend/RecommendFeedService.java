package com.apiece.springboot_sns_sample.domain.recommend;

import com.apiece.springboot_sns_sample.domain.post.Post;
import com.apiece.springboot_sns_sample.domain.post.PostRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Objects;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class RecommendFeedService {

    private final RecommendFeedClient client;
    private final PostRepository posts;

    public Page get(long userId, int limit, String cursor) {
        var feed = client.get(userId, limit, cursor);
        if (!feed.ready()) return new Page(List.of(), null, "pending");
        var found = feed.postIds().isEmpty() ? List.<Post>of()
                : posts.findAllByIdInAndDeletedAtIsNull(feed.postIds());
        var byId = found.stream().collect(Collectors.toMap(Post::getId, Function.identity()));
        var ordered = feed.postIds().stream().map(byId::get).filter(Objects::nonNull).toList();
        return new Page(ordered, feed.nextCursor(), "recommend");
    }

    public record Page(List<Post> posts, String nextCursor, String mode) {
    }
}
