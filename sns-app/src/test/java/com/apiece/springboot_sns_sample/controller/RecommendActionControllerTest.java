package com.apiece.springboot_sns_sample.controller;

import com.apiece.springboot_sns_sample.config.auth.AuthUser;
import com.apiece.springboot_sns_sample.domain.recommend.RecommendActionRepository;
import com.apiece.springboot_sns_sample.domain.user.User;
import org.junit.jupiter.api.Test;
import org.springframework.core.MethodParameter;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.method.support.ModelAndViewContainer;
import java.util.UUID;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class RecommendActionControllerTest {
    private final RecommendActionRepository actions = mock(RecommendActionRepository.class);
    private final UUID eventId = UUID.randomUUID();

    private MockMvc mvc(Long userId) {
        User user = userId == null ? null : User.create("reader", "");
        if (user != null) ReflectionTestUtils.setField(user, "id", userId);
        return MockMvcBuilders.standaloneSetup(new RecommendActionController(actions))
            .setControllerAdvice(new RecommendExceptionHandler())
            .setCustomArgumentResolvers(new HandlerMethodArgumentResolver() {
                public boolean supportsParameter(MethodParameter parameter) {
                    return parameter.hasParameterAnnotation(AuthUser.class);
                }
                public Object resolveArgument(MethodParameter parameter, ModelAndViewContainer container,
                        NativeWebRequest request, WebDataBinderFactory factory) { return user; }
            }).build();
    }

    @Test
    void usesLoggedInUser() throws Exception {
        mvc(7L).perform(post("/api/v1/recommend/actions?userId=999").contentType("application/json")
            .content("{\"eventId\":\"" + eventId + "\",\"action\":\"click\",\"postId\":4,\"userId\":999}"))
            .andExpect(status().isNoContent());
        verify(actions).record(eventId, "click", 7L, 4L);
    }

    @Test
    void requiresLogin() throws Exception {
        mvc(null).perform(post("/api/v1/recommend/actions").contentType("application/json")
            .content("{\"eventId\":\"" + eventId + "\",\"action\":\"click\",\"postId\":4}"))
            .andExpect(status().isUnauthorized());
        verifyNoInteractions(actions);
    }

    @Test
    void rejectsLikesAndInvalidTargets() throws Exception {
        var mvc = mvc(7L);
        for (String body : new String[] {
            "{\"eventId\":\"" + eventId + "\",\"action\":\"like\",\"postId\":4}",
            "{\"eventId\":\"" + eventId + "\",\"action\":\"click\",\"postId\":0}",
            "{\"action\":\"click\",\"postId\":4}"
        }) mvc.perform(post("/api/v1/recommend/actions").contentType("application/json").content(body))
                .andExpect(status().isBadRequest());
        verifyNoInteractions(actions);
    }
}
