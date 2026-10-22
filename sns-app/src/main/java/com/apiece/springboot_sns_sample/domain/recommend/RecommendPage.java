package com.apiece.springboot_sns_sample.domain.recommend;

import com.apiece.springboot_sns_sample.domain.post.Post;
import java.util.List;

public record RecommendPage(List<Post> posts, String nextCursor, String mode) {
}
