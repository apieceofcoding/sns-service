package com.apiece.springboot_sns_sample.controller;

import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.server.ResponseStatusException;

@RestControllerAdvice(assignableTypes = {RecommendController.class, RecommendActionController.class})
public class RecommendExceptionHandler {

    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<ProblemDetail> handle(ResponseStatusException exception) {
        var body = ProblemDetail.forStatusAndDetail(exception.getStatusCode(),
                exception.getReason() == null ? "인증이 필요합니다" : exception.getReason());
        return ResponseEntity.status(exception.getStatusCode()).body(body);
    }
}
