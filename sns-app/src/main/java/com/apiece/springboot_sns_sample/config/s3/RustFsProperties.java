package com.apiece.springboot_sns_sample.config.s3;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "rustfs")
public record RustFsProperties(
        String endpoint,
        String publicEndpoint,
        String accessKey,
        String secretKey,
        String bucket,
        String region,
        Long presignedUrlExpirationSeconds
) {
}
