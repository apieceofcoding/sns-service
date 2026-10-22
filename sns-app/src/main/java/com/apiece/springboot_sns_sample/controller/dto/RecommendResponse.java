package com.apiece.springboot_sns_sample.controller.dto;

import com.apiece.springboot_sns_sample.api.post.PostResponse;
import java.util.List;

public record RecommendResponse(List<PostResponse> posts, String nextCursor, boolean hasMore, String mode) {
}
