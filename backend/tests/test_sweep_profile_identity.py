import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parents[1]))
from modules.sweep import CATALOGUE, Sweep


def test_rubygems_numeric_prefix_cannot_verify_a_different_profile():
    platform = next(p for p in CATALOGUE if p["name"] == "RubyGems")
    sweep = Sweep("4ryanwalia")
    response = Mock(status_code=200, encoding="utf-8", url=platform["url"].replace("{username}", "4ryanwalia"))
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.iter_content.return_value = iter([b"<title>Profile of fermion | RubyGems.org | your community gem host</title><h1>Profile of fermion</h1>"])
    sweep._html_get = Mock(return_value=response)
    result = sweep.probe(platform)
    assert result["verdict"] == "unknown"
    assert result["reason_code"] == "ambiguous"
    sweep.session.close()


def test_rubygems_exact_handle_still_verifies():
    platform = next(p for p in CATALOGUE if p["name"] == "RubyGems")
    sweep = Sweep("fermion")
    response = Mock(status_code=200, encoding="utf-8", url="https://rubygems.org/profiles/fermion")
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.iter_content.return_value = iter([b'<title>Profile of fermion | RubyGems.org | your community gem host</title><meta property="og:type" content="profile">'])
    sweep._html_get = Mock(return_value=response)
    result = sweep.probe(platform)
    assert result["verdict"] == "found"
    sweep.session.close()
