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
                .setCustomArgumentResolvers(resolver(user)).build()
                .perform(get("/api/v1/recommend?userId=999"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.mode").value("recommend"))
                .andExpect(jsonPath("$.nextCursor").value("next"))
                .andExpect(jsonPath("$.hasMore").value(true));
        verify(recommend).get(7, 20, null);
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
