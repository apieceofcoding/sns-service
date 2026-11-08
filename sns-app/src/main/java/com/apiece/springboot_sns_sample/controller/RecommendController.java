package com.apiece.springboot_sns_sample.controller;

import com.apiece.springboot_sns_sample.api.post.PostResponse;
import com.apiece.springboot_sns_sample.config.auth.AuthUser;
import com.apiece.springboot_sns_sample.controller.dto.RecommendResponse;
import com.apiece.springboot_sns_sample.domain.post.PostService;
import com.apiece.springboot_sns_sample.domain.recommend.RecommendFeedService;
import com.apiece.springboot_sns_sample.domain.user.User;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequiredArgsConstructor
public class RecommendController {

    private final RecommendFeedService recommend;
    private final PostService posts;

    @GetMapping("/api/v1/recommend")
    public ResponseEntity<RecommendResponse> get(@AuthUser User user,
            @RequestParam(required = false) String cursor,
            @RequestParam(defaultValue = "20") int limit) {
        if (user == null) throw new ResponseStatusException(HttpStatus.UNAUTHORIZED);
        var page = recommend.get(user.getId(), limit, cursor);
        var result = posts.enrichWithUserContext(page.posts(), user).stream().map(PostResponse::from).toList();
        return ResponseEntity.ok(new RecommendResponse(result, page.nextCursor(),
                page.nextCursor() != null, page.mode()));
    }
}
