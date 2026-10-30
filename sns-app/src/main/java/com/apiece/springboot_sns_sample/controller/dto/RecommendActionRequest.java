package com.apiece.springboot_sns_sample.controller.dto;

import java.util.Set;
import java.util.UUID;

public record RecommendActionRequest(UUID eventId, String action, Long postId) {
    public RecommendActionRequest {
        if (eventId == null || action == null || !Set.of("click", "impression", "not_interested").contains(action)
                || postId == null || postId <= 0) {
            throw new IllegalArgumentException("eventId, valid action and positive postId required");
        }
    }
}
