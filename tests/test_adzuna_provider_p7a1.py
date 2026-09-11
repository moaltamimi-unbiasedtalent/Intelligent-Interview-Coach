"""Adzuna provider — mocked, credential-safe (Phase 7A.1, §40).

No live Adzuna calls: a fake transport returns canned (status, body). Covers credentials
absent, successful Germany search, auth failures, endpoint-404, rate limit, timeout,
malformed JSON, empty results, salary parsing, secret redaction and sanitized provenance.
"""

from __future__ import annotations

import json

import pytest

from src.copilot.knowledge.providers import adzuna


@pytest.fixture(autouse=True)
def _creds(monkeypatch):
    monkeypatch.setenv("ADZUNA_APP_ID", "TESTID123")
    monkeypatch.setenv("ADZUNA_APP_KEY", "TESTKEYSECRET456")


def _transport(status, body):
    def _t(url, headers):
        # The request must carry credentials but they must never be surfaced elsewhere.
        assert "app_id=TESTID123" in url and "app_key=TESTKEYSECRET456" in url
        return status, body
    return _t


def _ok_body(count=3169, with_salary=True):
    job = {"title": "Product Manager", "company": {"display_name": "X"},
           "location": {"display_name": "Berlin"}}
    if with_salary:
        job.update({"salary_min": 60000, "salary_max": 90000, "salary_is_predicted": "0"})
    return json.dumps({"count": count, "results": [job]})


def test_credentials_absent(monkeypatch):
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    assert adzuna.credentials_configured() is False
    with pytest.raises(adzuna.AdzunaConfigError):
        adzuna.AdzunaProvider(transport=_transport(200, _ok_body())).search_jobs(country="de")


def test_germany_search_success():
    p = adzuna.AdzunaProvider(transport=_transport(200, _ok_body()))
    res = p.search_jobs(country="de", what="product manager", results_per_page=1)
    assert res.ok and res.status == 200 and res.count == 3169


def test_empty_search_result():
    p = adzuna.AdzunaProvider(transport=_transport(200, _ok_body(count=0, with_salary=False)))
    res = p.search_jobs(country="de", what="nonexistent-role-xyz")
    assert res.ok and res.count == 0


@pytest.mark.parametrize("status,category", [(401, "auth"), (403, "auth"), (404, "not_found")])
def test_auth_and_unsupported_endpoints(status, category):
    p = adzuna.AdzunaProvider(transport=_transport(status, "{}"))
    with pytest.raises(adzuna.AdzunaError) as e:
        p.search_jobs(country="de", what="x")
    assert e.value.category == category and e.value.status == status


def test_rate_limit_after_bounded_retries():
    calls = {"n": 0}

    def t(url, headers):
        calls["n"] += 1
        return 429, "{}"
    p = adzuna.AdzunaProvider(transport=t, max_retries=2)
    with pytest.raises(adzuna.AdzunaError) as e:
        p.search_jobs(country="de", what="x")
    assert e.value.category == "rate_limit"
    assert calls["n"] == 3  # initial + 2 bounded retries, then stop (no infinite loop)


def test_timeout_is_safe_network_error():
    def t(url, headers):
        raise TimeoutError("timed out")
    with pytest.raises(adzuna.AdzunaError) as e:
        adzuna.AdzunaProvider(transport=t).search_jobs(country="de", what="x")
    assert e.value.category == "network"


def test_malformed_json():
    p = adzuna.AdzunaProvider(transport=_transport(200, "<<not json>>"))
    with pytest.raises(adzuna.AdzunaError) as e:
        p.search_jobs(country="de", what="x")
    assert e.value.category == "malformed"


def test_version_endpoint_404_does_not_block_search():
    # A 404 on the version endpoint is endpoint-specific; a separate search still works.
    version_provider = adzuna.AdzunaProvider(transport=_transport(404, "{}"))
    with pytest.raises(adzuna.AdzunaError):
        version_provider._request("/jobs/de/version", {})
    search_provider = adzuna.AdzunaProvider(transport=_transport(200, _ok_body()))
    assert search_provider.search_jobs(country="de", what="x").ok


def test_salary_parsing():
    p = adzuna.AdzunaProvider(transport=_transport(200, _ok_body()))
    res = p.search_jobs(country="de", what="x")
    sal = adzuna.parse_salary(res.data["results"][0])
    assert sal["salary_min"] == 60000 and sal["salary_max"] == 90000
    assert sal["salary_is_predicted"] is False


def test_secret_redaction():
    leaked = "error at https://api.adzuna.com/v1/api/jobs/de/search/1?app_id=TESTID123&app_key=TESTKEYSECRET456"
    red = adzuna._redact(leaked)
    assert "TESTID123" not in red and "TESTKEYSECRET456" not in red
    assert "app_id=***" in red and "app_key=***" in red


def test_sanitized_provenance_has_no_credentials():
    prov = adzuna.sanitized_provenance(
        endpoint="/jobs/de/search/1", country="de", query="product manager", count=3169)
    blob = json.dumps(prov)
    assert "TESTID123" not in blob and "TESTKEYSECRET456" not in blob
    assert prov["source"] == "adzuna" and prov["source_quality"] == "authorized_market_api"
    assert prov["record_count"] == 3169
