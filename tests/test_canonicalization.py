from factcheck_scrape.utils import canonicalize_url


def test_canonicalize_url():
    url = "https://example.com/path/?utm_source=x&b=2&a=1#frag"
    assert canonicalize_url(url) == "https://example.com/path?a=1&b=2"
