# DNS

Target: `aff.pramool.bid`. Set **A aff → 103.40.118.129** in the `pramool.bid` zone. Cloudflare proxy is supported; Full (strict) origin TLS is recommended. Do not change other zone records. Only add AAAA if the VPS has working public IPv6 and routing. Proxied public resolution returns Cloudflare addresses rather than the origin. Verify the dedicated host reaches this server using an ACME webroot challenge before issuance.
