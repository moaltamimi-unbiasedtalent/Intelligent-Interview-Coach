"""Synthetic JUnit contract tests; no Docker, PostgreSQL or provider access."""
from __future__ import annotations

from xml.etree import ElementTree as ET

import pytest

from tests.test_release_images_docker import REQUIRED_MIGRATION_TESTS, assert_migration_junit_report


def write_report(path, names, *, outcome=None, suite_counts=None, classname="tests.test_staging_migration_image"):
    root = ET.Element("testsuites")
    counts = {"tests": str(len(names)), "failures": str(outcome == "failure"),
              "errors": str(outcome == "error"), "skipped": str(outcome == "skipped")}
    counts.update(suite_counts or {})
    suite = ET.SubElement(root, "testsuite", counts)
    for i, name in enumerate(names):
        case = ET.SubElement(suite, "testcase", name=name, classname=classname)
        if outcome and i == 0:
            ET.SubElement(case, outcome)
    path.write_bytes(ET.tostring(root))


def test_required_migration_checks_pass(tmp_path):
    report = tmp_path / "junit.xml"
    write_report(report, sorted(REQUIRED_MIGRATION_TESTS))
    assert_migration_junit_report(report)


def test_additional_passing_migration_check_is_allowed(tmp_path):
    report = tmp_path / "junit.xml"
    write_report(report, sorted(REQUIRED_MIGRATION_TESTS) + ["test_future_qualification"])
    assert_migration_junit_report(report)


def test_missing_required_migration_check_is_refused(tmp_path):
    report = tmp_path / "junit.xml"
    write_report(report, sorted(REQUIRED_MIGRATION_TESTS)[:-1])
    with pytest.raises(AssertionError, match="Required migration tests missing"):
        assert_migration_junit_report(report)


@pytest.mark.parametrize("outcome", ["failure", "error", "skipped"])
def test_nonpassing_migration_check_is_refused(tmp_path, outcome):
    report = tmp_path / "junit.xml"
    write_report(report, sorted(REQUIRED_MIGRATION_TESTS), outcome=outcome)
    with pytest.raises(AssertionError, match="non-passing"):
        assert_migration_junit_report(report)


@pytest.mark.parametrize("invalid", ["malformed", "missing", "wrong_root", "empty"])
def test_missing_or_malformed_junit_is_refused(tmp_path, invalid):
    report = tmp_path / "junit.xml"
    if invalid == "malformed":
        report.write_text("<testsuite", encoding="utf-8")
    elif invalid == "wrong_root":
        report.write_text("<not-junit />", encoding="utf-8")
    elif invalid == "empty":
        write_report(report, [])
    with pytest.raises(AssertionError):
        assert_migration_junit_report(report)


def test_duplicate_migration_test_is_refused(tmp_path):
    report = tmp_path / "junit.xml"
    names = sorted(REQUIRED_MIGRATION_TESTS)
    write_report(report, names + [names[0]])
    with pytest.raises(AssertionError, match="Duplicate migration test"):
        assert_migration_junit_report(report)


def test_migration_test_from_wrong_module_is_refused(tmp_path):
    report = tmp_path / "junit.xml"
    write_report(report, sorted(REQUIRED_MIGRATION_TESTS), classname="tests.other_module")
    with pytest.raises(AssertionError, match="Unexpected migration test identity"):
        assert_migration_junit_report(report)


def test_junit_test_count_mismatch_is_refused(tmp_path):
    report = tmp_path / "junit.xml"
    write_report(report, sorted(REQUIRED_MIGRATION_TESTS), suite_counts={"tests": "3"})
    with pytest.raises(AssertionError, match="JUnit test count mismatch"):
        assert_migration_junit_report(report)


def test_case_failure_cannot_hide_behind_zero_suite_counters(tmp_path):
    report = tmp_path / "junit.xml"
    write_report(report, sorted(REQUIRED_MIGRATION_TESTS), outcome="failure", suite_counts={"failures": "0"})
    with pytest.raises(AssertionError, match="Migration test did not pass"):
        assert_migration_junit_report(report)
