package com.apiece.springboot_sns_sample.controller;

import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.server.ResponseStatusException;

@RestControllerAdvice(assignableTypes = {RecommendController.class, RecommendActionController.class})
public class RecommendExceptionHandler {

    @ExceptionHandler({ResponseStatusException.class, RestClientException.class})
    public ResponseEntity<ProblemDetail> handle(Exception exception) {
        HttpStatusCode status = HttpStatus.SERVICE_UNAVAILABLE;
        if (exception instanceof ResponseStatusException response) status = response.getStatusCode();
        if (exception instanceof RestClientResponseException response && response.getStatusCode().is4xxClientError()) {
            status = response.getStatusCode();
        }
        return ResponseEntity.status(status).body(ProblemDetail.forStatus(status));
    }
}
