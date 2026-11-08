package com.apiece.springboot_sns_sample.controller;

import com.apiece.springboot_sns_sample.config.auth.AuthUser;
import com.apiece.springboot_sns_sample.controller.dto.RecommendActionRequest;
import com.apiece.springboot_sns_sample.domain.recommend.RecommendActionRepository;
import com.apiece.springboot_sns_sample.domain.user.User;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequiredArgsConstructor
public class RecommendActionController {
    private final RecommendActionRepository actions;

    @PostMapping("/api/v1/recommend/actions")
    public ResponseEntity<Void> create(@AuthUser User user, @RequestBody RecommendActionRequest request) {
        if (user == null) throw new ResponseStatusException(HttpStatus.UNAUTHORIZED);
        actions.record(request.eventId(), request.action(), user.getId(), request.postId());
        return ResponseEntity.noContent().build();
    }
}
