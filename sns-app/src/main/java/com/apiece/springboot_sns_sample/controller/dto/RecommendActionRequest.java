package com.apiece.springboot_sns_sample.controller.dto;

import com.apiece.springboot_sns_sample.domain.recommend.RecommendAction;
import java.util.UUID;

public record RecommendActionRequest(UUID eventId, RecommendAction action, Long postId) {
    public RecommendActionRequest {
        if (eventId == null || action == null || postId == null || postId <= 0) {
            throw new IllegalArgumentException("eventId, action and positive postId required");
        }
    }
}
