import pytest
from core.validation import username, ValidationError
@pytest.mark.parametrize("value,expected", [("@alice", "alice"), ("alice", "alice"), ("https://www.instagram.com/example.name/?utm_source=x", "example.name"), ("https://www.tiktok.com/@example.name", "example.name"), ("https://github.com/example-name", "example-name")])
def test_valid(value, expected):
    assert username(value) == expected
@pytest.mark.parametrize("value", ["https://github.com/search", "https://instagram.com/p/123", "https://instagram.com/reel/123", "https://tiktok.com/@alice/video/123", "https://github.com/alice/repo", "https://github.com.evil.test/alice", "https://github.com@evil.test/alice", "https://github.com/%61lice", "https://github.com/a/../alice", "https://github.com//alice", "https://vm.tiktok.com/abc", "ftp://github.com/alice", "https://[bad", "https://github.com:8443/alice", "@@alice", "https://github.com/alice https://github.com/bob"])
def test_reject(value):
    with pytest.raises(ValidationError): username(value)
