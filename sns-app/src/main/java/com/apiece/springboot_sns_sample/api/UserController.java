package com.apiece.springboot_sns_sample.api;

import com.apiece.springboot_sns_sample.api.post.PostResponse;
import com.apiece.springboot_sns_sample.api.reply.ReplyResponse;
import com.apiece.springboot_sns_sample.api.user.UserResponse;
import com.apiece.springboot_sns_sample.api.user.UserSignupRequest;
import com.apiece.springboot_sns_sample.config.auth.AuthUser;
import com.apiece.springboot_sns_sample.domain.follow.Follow;
import com.apiece.springboot_sns_sample.domain.follow.FollowService;
import com.apiece.springboot_sns_sample.domain.post.PostService;
import com.apiece.springboot_sns_sample.domain.post.PostWithViewCount;
import com.apiece.springboot_sns_sample.domain.user.User;
import com.apiece.springboot_sns_sample.domain.user.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.List;
import java.util.stream.Stream;

import static java.util.Comparator.comparing;
import static java.util.Comparator.reverseOrder;

@RestController
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;
    private final PostService postService;
    private final FollowService followService;

    @PostMapping("/api/v1/users/signup")
    public UserResponse signupUser(@RequestBody UserSignupRequest request) {
        User user = userService.signup(request.username(), request.password());
        return UserResponse.from(user, null);
    }

    @GetMapping("/api/v1/users/me")
    public UserResponse getMyInfo(@AuthUser User user) {
        String profileImageUrl = userService.getProfileImageUrl(user);
        return UserResponse.from(user, profileImageUrl);
    }

    @GetMapping("/api/v1/users/{userId}")
    public UserResponse getUserById(@PathVariable Long userId) {
        User user = userService.getById(userId);
        String profileImageUrl = userService.getProfileImageUrl(user);
        return UserResponse.from(user, profileImageUrl);
    }

    @GetMapping("/api/v1/users/{userId}/posts")
    public List<PostResponse> getUserPosts(@PathVariable Long userId, @AuthUser User currentUser) {
        List<PostWithViewCount> postsWithViewCount = new ArrayList<>(postService.getPostsByUserId(userId));

        return postsWithViewCount.stream()
                .sorted(comparing(pvc -> pvc.post().getCreatedAt(), reverseOrder()))
                .map(pvc -> postService.enrichWithUserContext(pvc.post(), currentUser))
                .map(PostResponse::from)
                .toList();
    }

    @GetMapping("/api/v1/users/{userId}/replies")
    public List<ReplyResponse> getUserReplies(@PathVariable Long userId) {
        return postService.getRepliesByUserId(userId).stream()
                .map(ReplyResponse::from)
                .toList();
    }

    @GetMapping("/api/v1/users/{userId}/followers")
    public List<UserResponse> getFollowers(@PathVariable Long userId) {
        return toUsers(followService.getFollowers(userService.getById(userId)).stream().map(Follow::getFollowerId));
    }

    @GetMapping("/api/v1/users/{userId}/following")
    public List<UserResponse> getFollowing(@PathVariable Long userId) {
        return toUsers(followService.getFollowees(userService.getById(userId)).stream().map(Follow::getFolloweeId));
    }

    private List<UserResponse> toUsers(Stream<Long> userIds) {
        return userIds.map(userService::getById)
                .map(user -> UserResponse.from(user, userService.getProfileImageUrl(user)))
                .toList();
    }
}
