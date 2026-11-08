package com.apiece.springboot_sns_sample.controller;

import com.apiece.springboot_sns_sample.config.auth.AuthUser;
import com.apiece.springboot_sns_sample.domain.post.PostService;
import com.apiece.springboot_sns_sample.domain.recommend.RecommendFeedService.Page;
import com.apiece.springboot_sns_sample.domain.recommend.RecommendFeedService;
import com.apiece.springboot_sns_sample.domain.user.User;
import org.junit.jupiter.api.Test;
import org.springframework.core.MethodParameter;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.method.support.ModelAndViewContainer;

import java.util.List;

import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class RecommendControllerTest {

    @Test
    void usesAuthenticatedUserInsteadOfQueryUserId() throws Exception {
        var recommend = mock(RecommendFeedService.class);
        var posts = mock(PostService.class);
        User user = User.create("reader", "");
        ReflectionTestUtils.setField(user, "id", 7L);
        when(recommend.get(7, 20, null)).thenReturn(new Page(List.of(), "next", "recommend"));
        when(posts.enrichWithUserContext(List.of(), user)).thenReturn(List.of());

        MockMvcBuilders.standaloneSetup(new RecommendController(recommend, posts))
                .setControllerAdvice(new RecommendExceptionHandler())
                .setCustomArgumentResolvers(resolver(user)).build()
                .perform(get("/api/v1/recommend?userId=999"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.mode").value("recommend"))
                .andExpect(jsonPath("$.nextCursor").value("next"))
                .andExpect(jsonPath("$.hasMore").value(true));
        verify(recommend).get(7, 20, null);
    }

    @Test
    void rejectsMissingUserBeforeCallingRecommend() throws Exception {
        var recommend = mock(RecommendFeedService.class);
        MockMvcBuilders.standaloneSetup(new RecommendController(recommend, mock(PostService.class)))
                .setControllerAdvice(new RecommendExceptionHandler())
                .setCustomArgumentResolvers(resolver(null)).build()
                .perform(get("/api/v1/recommend"))
                .andExpect(status().isUnauthorized());
        verifyNoInteractions(recommend);
    }

    @Test
    void returnsExpiredCursorWithoutAnErrorDispatch() throws Exception {
        var recommend = mock(RecommendFeedService.class);
        User user = User.create("reader", "");
        ReflectionTestUtils.setField(user, "id", 7L);
        when(recommend.get(7, 20, "old")).thenThrow(new org.springframework.web.server.ResponseStatusException(
                org.springframework.http.HttpStatus.GONE, "추천 세션을 새로 시작하세요"));
        MockMvcBuilders.standaloneSetup(new RecommendController(recommend, mock(PostService.class)))
                .setControllerAdvice(new RecommendExceptionHandler())
                .setCustomArgumentResolvers(resolver(user)).build()
                .perform(get("/api/v1/recommend?cursor=old"))
                .andExpect(status().isGone())
                .andExpect(jsonPath("$.status").value(410));
    }

    @org.junit.jupiter.params.ParameterizedTest
    @org.junit.jupiter.params.provider.ValueSource(ints = {400, 410, 422, 500})
    void preservesClientErrorsAndMapsUpstreamFailureTo503(int status) throws Exception {
        var recommend = mock(RecommendFeedService.class);
        User user = User.create("reader", "");
        ReflectionTestUtils.setField(user, "id", 7L);
        when(recommend.get(7, 20, "cursor")).thenThrow(
                new org.springframework.web.client.RestClientResponseException(
                        "upstream", org.springframework.http.HttpStatusCode.valueOf(status), "", null, null, null));
        MockMvcBuilders.standaloneSetup(new RecommendController(recommend, mock(PostService.class)))
                .setControllerAdvice(new RecommendExceptionHandler())
                .setCustomArgumentResolvers(resolver(user)).build()
                .perform(get("/api/v1/recommend?cursor=cursor"))
                .andExpect(status().is(status == 500 ? 503 : status));
    }

    private HandlerMethodArgumentResolver resolver(User user) {
        return new HandlerMethodArgumentResolver() {
            public boolean supportsParameter(MethodParameter parameter) {
                return parameter.hasParameterAnnotation(AuthUser.class);
            }
            public Object resolveArgument(MethodParameter parameter, ModelAndViewContainer container,
                                          NativeWebRequest request, WebDataBinderFactory factory) {
                return user;
            }
        };
    }
}
