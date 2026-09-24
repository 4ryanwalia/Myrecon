"""
Regression tests for the outbound-request guard.

Everything here is checked against literal addresses rather than hostnames, so
the suite does not depend on DNS being reachable from the machine running it.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.netguard import BlockedRequest, _refuse_internal  # noqa: E402

BLOCKED = [
    "http://169.254.169.254/latest/meta-data/",   # the one that matters: cloud metadata
    "http://[::ffff:169.254.169.254]/",           # same host, IPv4-mapped
    "http://127.0.0.1:5000/api/health",
    "http://[::1]/",
    "http://10.0.0.5/",
    "http://192.168.1.1/",
    "http://172.16.0.1/",
    "http://0.0.0.0/",
    "file:///etc/passwd",
    "gopher://127.0.0.1:11211/",
    "ftp://127.0.0.1/",
    "//evil.example/no-scheme",
]

ALLOWED = [
    "http://93.184.216.34/x",
    "https://8.8.8.8/y.png",
]


@pytest.mark.parametrize("url", BLOCKED)
def test_internal_and_odd_schemes_are_refused(url):
    with pytest.raises(BlockedRequest):
        _refuse_internal(url)


@pytest.mark.parametrize("url", ALLOWED)
def test_public_addresses_are_allowed(url):
    _refuse_internal(url)


def test_unresolvable_host_fails_closed():
    # A name that cannot be resolved is refused rather than handed to requests,
    # so a DNS hiccup can never become an unchecked fetch.
    with pytest.raises(BlockedRequest):
        _refuse_internal("http://host.invalid./")
