package com.apiece.springboot_sns_sample.domain.recommend;

import com.fasterxml.jackson.annotation.JsonValue;

public enum RecommendAction {
    IMPRESSION("impression"),
    CLICK("click");

    private final String value;

    RecommendAction(String value) {
        this.value = value;
    }

    // The same lowercase value is used in the request body and in post_actions.action.
    @JsonValue
    public String value() {
        return value;
    }
}
