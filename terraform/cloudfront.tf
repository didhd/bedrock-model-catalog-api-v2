# Origin Access Control
resource "aws_cloudfront_origin_access_control" "catalog" {
  name                              = "${var.project_name}-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# Response headers policy (security headers)
resource "aws_cloudfront_response_headers_policy" "security" {
  name = "${var.project_name}-security-headers"

  security_headers_config {
    content_type_options {
      override = true
    }
    frame_options {
      frame_option = "DENY"
      override     = true
    }
    strict_transport_security {
      access_control_max_age_sec = 31536000
      include_subdomains         = true
      preload                    = true
      override                   = true
    }
    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }
    content_security_policy {
      content_security_policy = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
      override                = true
    }
  }

  cors_config {
    access_control_allow_credentials = false
    access_control_max_age_sec       = 86400

    access_control_allow_headers {
      items = ["*"]
    }
    access_control_allow_methods {
      items = ["GET", "HEAD", "OPTIONS"]
    }
    access_control_allow_origins {
      items = ["*"]
    }
    origin_override = true
  }
}

# CloudFront Function: append .json to extensionless URIs
resource "aws_cloudfront_function" "uri_rewrite" {
  name    = "${var.project_name}-uri-rewrite"
  runtime = "cloudfront-js-2.0"
  publish = true
  code    = <<-EOF
    function handler(event) {
      var request = event.request;
      var uri = request.uri;
      // API paths: append .json if no extension
      if (uri.match(/^\/(v1|v2)\//)) {
        if (!uri.match(/\.(json)$/)) {
          request.uri = uri + '.json';
        }
        return request;
      }
      // Static assets: serve as-is
      if (uri.match(/\.(json|html|svg|png|jpg|css|js|ico|txt|md|zip|woff2?)$/)) {
        return request;
      }
      // SPA routes: serve index.html
      request.uri = '/index.html';
      return request;
    }
  EOF
}

# CloudFront Distribution
resource "aws_cloudfront_distribution" "catalog" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "Bedrock Model Catalog API"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"
  http_version        = "http2and3"
  aliases = var.domain_name != "" ? [var.domain_name] : []

  origin {
    domain_name              = aws_s3_bucket.catalog.bucket_regional_domain_name
    origin_id                = "s3-catalog"
    origin_access_control_id = aws_cloudfront_origin_access_control.catalog.id
  }

  default_cache_behavior {
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD"]
    target_origin_id           = "s3-catalog"
    viewer_protocol_policy     = "redirect-to-https"
    compress                   = true
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id

    cache_policy_id = aws_cloudfront_cache_policy.catalog.id

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.uri_rewrite.arn
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = var.domain_name == ""
    acm_certificate_arn            = var.domain_name != "" ? aws_acm_certificate_validation.main[0].certificate_arn : null
    ssl_support_method             = var.domain_name != "" ? "sni-only" : null
    minimum_protocol_version       = var.domain_name != "" ? "TLSv1.2_2021" : "TLSv1"
  }

  logging_config {
    bucket          = aws_s3_bucket.access_logs.bucket_domain_name
    prefix          = "cloudfront/"
    include_cookies = false
  }
}

# Cache policy: 24h TTL
resource "aws_cloudfront_cache_policy" "catalog" {
  name        = "${var.project_name}-cache-policy"
  default_ttl = 86400
  max_ttl     = 86400
  min_ttl     = 3600

  parameters_in_cache_key_and_forwarded_to_origin {
    cookies_config {
      cookie_behavior = "none"
    }
    headers_config {
      header_behavior = "none"
    }
    query_strings_config {
      query_string_behavior = "none"
    }
    enable_accept_encoding_brotli = true
    enable_accept_encoding_gzip   = true
  }
}
