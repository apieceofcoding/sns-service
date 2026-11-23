package com.apiece.springboot_sns_sample.domain.recommend;

import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum RecommendAction {
    IMPRESSION("impression"),
    CLICK("click");

    @JsonValue
    private final String value;
}
