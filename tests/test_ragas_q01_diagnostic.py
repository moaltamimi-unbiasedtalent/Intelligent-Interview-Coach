"""Offline Q01 data-path regressions using synthetic answers and scores."""

import json
import subprocess
import sys
from dataclasses import asdict, replace
from functools import partial
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from src.copilot.evaluation import ragas_adapter as ra
from src.copilot.evaluation import ragas_runner as runner
from src.copilot.knowledge import approval_filter
from src.copilot.service import CareerIntelligenceService, PipelineTrace
from src.knowledge_approval import MODE_ENFORCED, Register

CASE_IDS = ["role_us_data_analyst", "role_uk_operations_manager"]
CONTEXT = "Synthetic retrieved passage."
DEFAULT_MARKET = object()
SOURCES = {"US": "q01-synthetic-us", "UK": "q01-synthetic-uk"}
UNAPPROVED = "q01-synthetic-unapproved"
REFERENCE_FREE = [
    ra.METRIC_FAITHFULNESS,
    ra.METRIC_RESPONSE_RELEVANCY,
    ra.METRIC_CONTEXT_PRECISION,
]


@pytest.fixture
def cases():
    by_id = {case.case_id: case for case in ra.load_cases(runner.CASES_PATH)}
    return [by_id[case_id] for case_id in CASE_IDS]


@pytest.fixture
def diagnostic(tmp_path, monkeypatch):
    factory = Mock(side_effect=AssertionError("The default service must not be constructed."))
    monkeypatch.setattr(runner, "_default_service", factory)
    monkeypatch.setattr(runner, "_q01_network_denied", lambda: True)
    service = SimpleNamespace(answer=Mock(side_effect=lambda question, *, market: _answer(market)))
    evaluator = Mock(side_effect=partial(_score_with(), config=None))
    monkeypatch.setattr(runner, "_q01_fixture_answer", service.answer)
    monkeypatch.setattr(runner, "_q01_fixture_score", evaluator)

    def run():
        result = runner._run_q01_worker()
        factory.assert_not_called()
        assert not result.persisted
        assert list(tmp_path.iterdir()) == []
        return result

    return run, service, evaluator


def _run_q01(**overrides):
    options = dict(config=None, evaluator_config=None, case_ids=CASE_IDS,
                   persist=False, q01_diagnostic=True)
    return runner.run_live_ragas(**(options | overrides))


def _answer(market, *, effective=DEFAULT_MARKET, contexts=(CONTEXT,), retrieved=(), detected="CA"):
    effective = market if effective is DEFAULT_MARKET else effective
    dropped = [source for key, source in SOURCES.items() if key != market] + [UNAPPROVED]
    return SimpleNamespace(
        trace=PipelineTrace(detected_country=detected, source_approval_market=effective),
        approval=approval_filter.FilterReport(
            market=effective, enforced=True, dropped_sources=dropped, dropped_count=len(dropped),
        ),
        response=SimpleNamespace(
            answer="Synthetic answer.",
            evidence=[SimpleNamespace(text=text, source_id=SOURCES[market]) for text in contexts],
            retrieved=[SimpleNamespace(chunk=SimpleNamespace(
                text=text, metadata={"manifest_source_id": SOURCES[market]},
            )) for text in retrieved],
        ),
    )


def _score_with(overrides=None):
    def build_metrics(*, reference_free_only):
        names = REFERENCE_FREE if reference_free_only else [ra.METRIC_CONTEXT_RECALL]
        return [(name, None) for name in names]

    def evaluate(samples, metrics, llm, embeddings):
        assert llm is embeddings is None
        assert all(sample.retrieved_contexts == [CONTEXT] for sample in samples)
        names = [name for name, _ in metrics]
        assert all(sample.has_reference for sample in samples)
        return {
            index: {
                name: (overrides or {}).get((sample.case_id, name), 0.0)
                for name in names
            }
            for index, sample in enumerate(samples)
        }

    def run(cases, *, config):
        assert config is None
        return ra.run_ragas(
            cases, config=object(), evaluate_fn=evaluate, build_metrics_fn=build_metrics,
            to_sample_fn=lambda case, **_: case,
        )

    return run


def test_exact_cases_and_markets_report_only_actual_deduplicated_contexts(diagnostic, cases):
    run, service, evaluator = diagnostic
    service.answer.side_effect = [
        _answer("US"),
        _answer("UK", contexts=(CONTEXT, f" {CONTEXT} "), retrieved=(CONTEXT,)),
    ]

    result = run()

    assert service.answer.call_args_list == [
        call(cases[0].question, market="US"), call(cases[1].question, market="UK"),
    ]
    evaluator.assert_called_once()
    adapted_cases = evaluator.call_args.args[0]
    assert [case.case_id for case in adapted_cases] == CASE_IDS
    assert [case.reference for case in adapted_cases] == [case.reference for case in cases]
    assert result.q01_diagnostics == [
        dict(case_id=case_id, intended_market=market, detected_country="CA",
             source_approval_market=market, retrieved_context_count=1,
             source_ids=[SOURCES[market]], approval_enforced=True,
             dropped_source_ids=[SOURCES["UK" if market == "US" else "US"], UNAPPROVED])
        for case_id, market in zip(CASE_IDS, ("US", "UK"), strict=True)
    ]
    assert result.status == ra.STATUS_COMPLETE
    assert result.expected_score_count == result.valid_score_count == 8
    assert result.referenced_case_count == 2 and result.context_recall_run
    assert len(result.metrics) == 4 and all(value == 0.0 for value in result.metrics.values())


def test_explicit_gb_normalizes_to_uk_even_when_loaded_out_of_order(diagnostic, cases, monkeypatch):
    run, service, _ = diagnostic
    uk = replace(cases[1], metadata=cases[1].metadata | {"geography": "GB"})
    monkeypatch.setattr(ra, "load_cases", lambda path: [uk, cases[0]])

    result = run()

    assert result.status == ra.STATUS_COMPLETE
    assert service.answer.call_args_list == [
        call(cases[0].question, market="US"), call(cases[1].question, market="UK"),
    ]


def test_rejects_injected_dependencies_before_inspection_or_launch(monkeypatch):
    class ServiceWithAnswerProperty(CareerIntelligenceService):
        @property
        def answer(self):
            raise AssertionError("An injected service must be rejected before inspection.")

    class FalseyEvaluator:
        def __bool__(self):
            raise AssertionError("An injected evaluator must be rejected before inspection.")

        def __call__(self, cases, *, config):
            raise AssertionError("An injected evaluator must never be called.")

    launch = Mock()
    callback = Mock()
    monkeypatch.setattr(runner, "_launch_q01", launch)
    for options in [
        {"service": ServiceWithAnswerProperty()},
        {"service_factory": callback},
        {"run_ragas_fn": partial(callback, config=None)},
        {"run_ragas_fn": FalseyEvaluator()},
    ]:
        assert _run_q01(**options).error_category == "q01_invalid_options"
    launch.assert_not_called()
    callback.assert_not_called()


@pytest.mark.parametrize("ids", [
    None, [], set(CASE_IDS), CASE_IDS[:1], CASE_IDS[::-1], CASE_IDS[:1] * 2,
    [CASE_IDS[0], "unknown"], CASE_IDS + ["unknown"],
])
def test_invalid_selection_stops_before_worker_launch(monkeypatch, ids):
    launch = Mock()
    monkeypatch.setattr(runner, "_launch_q01", launch)
    assert _run_q01(case_ids=ids).error_category == "q01_invalid_selection"
    launch.assert_not_called()


def test_case_id_types_are_rejected_without_executing_custom_methods(monkeypatch):
    class Impostor:
        def __eq__(self, other):
            pytest.fail("Q01 must never compare an impostor ID.")

    class StringSubclass(str):
        def __eq__(self, other):
            pytest.fail("Q01 must never compare a string subclass.")

    class ListSubclass(list):
        def __iter__(self):
            pytest.fail("Q01 must never iterate a list subclass.")

        def __len__(self):
            pytest.fail("Q01 must never inspect a list subclass.")

    class Meta(type):
        def __eq__(self, other):
            pytest.fail("Q01 must compare container types by identity.")

    class CustomContainer(metaclass=Meta):
        pass

    launch = Mock()
    monkeypatch.setattr(runner, "_launch_q01", launch)
    for ids in (
        [Impostor(), Impostor()], [StringSubclass(CASE_IDS[0]), CASE_IDS[1]],
        ListSubclass(CASE_IDS), iter(CASE_IDS), CustomContainer(),
    ):
        assert _run_q01(case_ids=ids).error_category == "q01_invalid_selection"
    launch.assert_not_called()


@pytest.mark.parametrize("options", [
    {"persist": True}, {"output_dir": "unexpected"}, {"category": "role_responsibilities"},
    {"limit": 2}, {"cases_path": "replacement.json"}, {"runs_dir": "unexpected"},
    {"timestamp": "unexpected"}, {"config": object()}, {"evaluator_config": object()},
    {"run_ragas_fn": ra.run_ragas},
])
def test_incompatible_options_stop_before_worker_launch(monkeypatch, options):
    launch = Mock()
    monkeypatch.setattr(runner, "_launch_q01", launch)
    result = _run_q01(**options)
    assert result.is_failed and result.error_category == "q01_invalid_options"
    launch.assert_not_called()


@pytest.mark.parametrize("error", [
    FileNotFoundError("private launcher detail"),
    subprocess.CalledProcessError(1, "private command detail"),
    subprocess.TimeoutExpired("private command detail", 30),
])
def test_launcher_failure_never_falls_back_in_process(monkeypatch, error):
    spawn = Mock(side_effect=error)
    fixture_answer = Mock()
    fixture_score = Mock()
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(subprocess, "run", spawn)
    monkeypatch.setattr(runner, "_q01_fixture_answer", fixture_answer)
    monkeypatch.setattr(runner, "_q01_fixture_score", fixture_score)

    result = _run_q01()

    assert result.is_failed and result.error_category == "q01_offline_unavailable"
    assert "private" not in json.dumps(asdict(result))
    spawn.assert_called_once()
    fixture_answer.assert_not_called()
    fixture_score.assert_not_called()


def _reply_from_worker(monkeypatch, stdout):
    monkeypatch.setattr(sys, "platform", "darwin")
    spawn = Mock(return_value=subprocess.CompletedProcess([], 0, stdout=stdout))
    monkeypatch.setattr(subprocess, "run", spawn)
    result = _run_q01()
    spawn.assert_called_once()
    return result


@pytest.mark.parametrize("payload", [
    b'{"status":"COMPLETE"}', b'{"status":"FAILED","status":"COMPLETE"}',
    b"not json", b"[" * 1100 + b"]" * 1100, b" " * 8193,
])
def test_parent_refuses_incomplete_malformed_or_oversized_worker_output(monkeypatch, payload):
    result = _reply_from_worker(monkeypatch, payload)
    assert result.is_failed and result.error_category == "q01_offline_unavailable"
    assert not result.persisted


@pytest.mark.parametrize("damage", [
    lambda reply: reply.pop("per_case"),
    lambda reply: reply.update(per_case=[]),
    lambda reply: reply["per_case"].reverse(),
    lambda reply: reply["q01_diagnostics"].reverse(),
    lambda reply: reply["q01_diagnostics"][1].update(source_approval_market="US"),
    lambda reply: reply["q01_diagnostics"][1].update(source_ids=[UNAPPROVED]),
    lambda reply: reply["q01_diagnostics"][1].update(retrieved_context_count=0),
    lambda reply: reply["q01_diagnostics"][1].update(dropped_source_ids=[]),
    lambda reply: reply["q01_diagnostics"][1].update(approval_enforced=False),
    lambda reply: reply.update(expected_score_count=9),
    lambda reply: reply.update(valid_score_count=7),
    lambda reply: reply.update(failed_score_count=1),
    lambda reply: reply.update(score_coverage=0.5),
    lambda reply: reply.update(status=ra.STATUS_PARTIAL),
    lambda reply: reply.update(status="ACCEPTED"),
    lambda reply: reply.update(case_count="2"),
    lambda reply: reply.update(context_recall_run=1),
    lambda reply: reply["metrics"].update(faithfulness=False),
    lambda reply: reply["metrics"].update(faithfulness=0.5),
    lambda reply: reply["per_case"][0].update(faithfulness=float("inf")),
    lambda reply: reply.update(output_directory="unexpected"),
    lambda reply: reply.update(accepted=True),
], ids=[
    "missing-case-list", "empty-case-list", "wrong-case-order", "wrong-diagnostic-order",
    "wrong-market", "wrong-source", "zero-context", "no-source-refusal", "unenforced",
    "wrong-total", "wrong-valid", "wrong-failed", "wrong-coverage", "contradictory-status",
    "unknown-status", "invalid-count-type", "invalid-bool-type", "invalid-score-type",
    "inconsistent-aggregate", "non-finite", "output-path", "extra-acceptance-field",
])
def test_parent_refuses_contradictory_worker_reply(diagnostic, monkeypatch, damage):
    run, _, _ = diagnostic
    reply = asdict(run())
    assert reply["status"] == ra.STATUS_COMPLETE
    damage(reply)

    result = _reply_from_worker(monkeypatch, json.dumps(reply).encode())

    assert result.is_failed and result.error_category == "q01_offline_unavailable"
    assert not result.persisted


@pytest.mark.parametrize(("valid", "status"), [
    (8, ra.STATUS_COMPLETE), (7, ra.STATUS_PARTIAL), (0, ra.STATUS_FAILED),
])
def test_parent_preserves_valid_worker_score_states(diagnostic, monkeypatch, valid, status):
    run, _, evaluator = diagnostic
    slots = [(case_id, name) for case_id in CASE_IDS for name in [*REFERENCE_FREE, ra.METRIC_CONTEXT_RECALL]]
    evaluator.side_effect = partial(_score_with(dict.fromkeys(slots[valid:], None)), config=None)
    expected = run()
    assert expected.status == status and expected.valid_score_count == valid

    result = _reply_from_worker(monkeypatch, json.dumps(asdict(expected), allow_nan=False).encode())

    assert result == expected
    assert result.failed_score_count == 8 - valid


def test_parent_preserves_valid_worker_refusal(diagnostic, monkeypatch):
    run, service, _ = diagnostic
    service.answer.side_effect = [_answer("US"), _answer("UK", effective=None)]
    expected = run()
    assert expected.error_category == "q01_unverified_market"
    assert _reply_from_worker(monkeypatch, json.dumps(asdict(expected)).encode()) == expected


def test_unsupported_platform_fails_without_launch(monkeypatch):
    spawn = Mock()
    monkeypatch.setattr(sys, "platform", "unsupported")
    monkeypatch.setattr(subprocess, "run", spawn)
    assert _run_q01().error_category == "q01_offline_unavailable"
    spawn.assert_not_called()


def test_worker_refuses_before_loading_cases_or_calling_fixtures_if_denial_unproven(
    diagnostic, monkeypatch,
):
    run, service, evaluator = diagnostic
    load_cases = Mock()
    monkeypatch.setattr(runner, "_q01_network_denied", lambda: False)
    monkeypatch.setattr(ra, "load_cases", load_cases)
    assert run().error_category == "q01_offline_unavailable"
    load_cases.assert_not_called()
    service.answer.assert_not_called()
    evaluator.assert_not_called()


@pytest.mark.skipif(sys.platform != "darwin", reason="requires the macOS worker boundary")
def test_fixed_worker_runs_with_os_network_and_write_denial(tmp_path):
    # The outer test process can write here. The nested policy must deny it.
    outside = tmp_path / "outside"
    outside.write_bytes(b"untouched")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    check = """
import errno
import os
import socket
import sys
from pathlib import Path

with socket.socket() as probe:
    assert probe.connect_ex(("127.0.0.1", 1)) in (errno.EPERM, errno.EACCES)
try:
    descriptor = os.open(sys.argv[1], os.O_WRONLY)
except PermissionError:
    pass
else:
    os.close(descriptor)
    raise AssertionError("Write outside the worker directory was permitted.")
Path(sys.argv[2]).write_bytes(b"allowed")
"""
    subprocess.run(
        ["/usr/bin/sandbox-exec", "-p", runner._q01_worker_profile(str(scratch.resolve())),
         sys.executable, "-I", "-B", "-c", check, str(outside), str(scratch / "inside")],
        check=True, timeout=30,
    )
    assert outside.read_bytes() == b"untouched"
    assert (scratch / "inside").read_bytes() == b"allowed"

    result = _run_q01()

    assert result.status == ra.STATUS_COMPLETE
    assert result.expected_score_count == result.valid_score_count == 8
    assert all(score == 0.0 for score in result.metrics.values())
    assert [item["case_id"] for item in result.q01_diagnostics] == CASE_IDS
    assert [item["source_approval_market"] for item in result.q01_diagnostics] == ["US", "UK"]
    assert all(item["retrieved_context_count"] == 1 for item in result.q01_diagnostics)
    assert [item["source_ids"] for item in result.q01_diagnostics] == [[SOURCES["US"]], [SOURCES["UK"]]]
    assert [item["dropped_source_ids"] for item in result.q01_diagnostics] == [
        [SOURCES["UK"], UNAPPROVED], [SOURCES["US"], UNAPPROVED],
    ]
    assert not result.persisted


def test_real_filter_binds_both_cases_and_scores_only_approved_evidence(monkeypatch):
    real_apply = Mock(wraps=approval_filter.apply)
    real_score = Mock(wraps=runner._q01_fixture_score)
    monkeypatch.setattr(runner, "_q01_network_denied", lambda: True)
    monkeypatch.setattr(approval_filter, "apply", real_apply)
    monkeypatch.setattr(runner, "_q01_fixture_score", real_score)
    monkeypatch.setattr(
        approval_filter.ka, "current",
        Mock(side_effect=AssertionError("The production approval register must not be used.")),
    )

    result = runner._run_q01_worker()

    assert result.status == ra.STATUS_COMPLETE
    assert [entry.kwargs["selected_market"] for entry in real_apply.call_args_list] == ["US", "UK"]
    assert all(entry.kwargs["register"].enabled == {(source, market) for market, source in SOURCES.items()}
               for entry in real_apply.call_args_list)
    real_score.assert_called_once()
    for market, adapted, diag in zip(SOURCES, real_score.call_args.args[0], result.q01_diagnostics, strict=True):
        source = SOURCES[market]
        assert adapted.retrieved_contexts == [f"Synthetic Q01 evidence from {source}."]
        assert adapted.source_ids == diag["source_ids"] == [source]
        assert diag["approval_enforced"] is True
        assert set(diag["dropped_source_ids"]) == set(SOURCES.values()) - {source} | {UNAPPROVED}


@pytest.mark.parametrize(("change", "expected"), [
    ("no_op", "q01_unverified_approval"),
    ("wrong_market", "q01_unverified_market"),
    ("missing_market", "q01_unverified_market"),
    ("empty_approval", "q01_no_context"),
])
def test_worker_refuses_unverified_filter_output_before_evaluation(monkeypatch, change, expected):
    real_apply = approval_filter.apply
    evaluator = Mock()
    monkeypatch.setattr(runner, "_q01_network_denied", lambda: True)
    monkeypatch.setattr(runner, "_q01_fixture_score", evaluator)

    def apply(results, evidence, **options):
        if change == "no_op":
            return results, evidence, approval_filter.FilterReport(
                market=options["selected_market"], enforced=True,
            )
        if change == "empty_approval":
            options["register"] = Register(mode=MODE_ENFORCED)
        else:
            options["selected_market"] = "UK" if change == "wrong_market" else None
            options["detected_country"] = None
        return real_apply(results, evidence, **options)

    spy = Mock(side_effect=apply)
    monkeypatch.setattr(approval_filter, "apply", spy)

    result = runner._run_q01_worker()

    assert result.is_failed and result.error_category == expected
    spy.assert_called_once()
    evaluator.assert_not_called()
    if change == "empty_approval":
        assert result.q01_diagnostics[0]["retrieved_context_count"] == 0
        assert set(result.q01_diagnostics[0]["dropped_source_ids"]) == {*SOURCES.values(), UNAPPROVED}


@pytest.mark.parametrize("geography", [None, "", "GLOBAL", "DE"])
def test_second_case_invalid_market_stops_before_either_service_call(
    diagnostic, cases, monkeypatch, geography,
):
    run, service, evaluator = diagnostic
    case = replace(cases[1], metadata={"geography": geography} if geography is not None else {})
    monkeypatch.setattr(ra, "load_cases", lambda path: [cases[0], case])
    assert run().error_category == "q01_invalid_market"
    service.answer.assert_not_called()
    evaluator.assert_not_called()


@pytest.mark.parametrize("change", ["missing_row", "duplicate_row", "blank_reference"])
def test_prevalidates_both_benchmark_rows(diagnostic, cases, monkeypatch, change):
    run, service, evaluator = diagnostic
    rows = {
        "missing_row": cases[:1],
        "duplicate_row": cases + cases[1:],
        "blank_reference": [cases[0], replace(cases[1], reference=" \t")],
    }
    monkeypatch.setattr(ra, "load_cases", lambda path: rows[change])
    error = "q01_missing_reference" if change == "blank_reference" else "q01_invalid_benchmark"
    assert run().error_category == error
    service.answer.assert_not_called()
    evaluator.assert_not_called()


@pytest.mark.parametrize("effective", [None, "US"])
def test_missing_or_mismatched_effective_market_stops_before_scoring(diagnostic, effective):
    run, service, evaluator = diagnostic
    service.answer.side_effect = [_answer("US"), _answer("UK", effective=effective)]
    result = run()
    assert result.is_failed and result.error_category == "q01_unverified_market"
    assert result.q01_diagnostics[-1]["source_approval_market"] == effective
    assert result.q01_diagnostics[-1]["intended_market"] == "UK"
    evaluator.assert_not_called()


def test_diagnostics_redact_unexpected_trace_text_before_return(diagnostic):
    run, service, evaluator = diagnostic
    marker = "SYNTHETIC_FREE_TEXT_SENTINEL"
    service.answer.side_effect = [
        _answer("US", detected=marker), _answer("UK", detected=marker, effective=marker),
    ]

    result = run()

    assert result.error_category == "q01_unverified_market"
    assert result.q01_diagnostics[0]["source_approval_market"] == "US"
    assert result.q01_diagnostics[1]["source_approval_market"] is None
    assert all(item["detected_country"] is None for item in result.q01_diagnostics)
    assert marker not in json.dumps(asdict(result))
    evaluator.assert_not_called()


@pytest.mark.parametrize("contexts", [(), ("", " \t")])
def test_empty_or_placeholder_context_stops_before_scoring(diagnostic, contexts):
    run, service, evaluator = diagnostic
    service.answer.side_effect = [_answer("US"), _answer("UK", contexts=contexts)]
    result = run()
    assert result.is_failed and result.error_category == "q01_no_context"
    assert result.q01_diagnostics[-1]["retrieved_context_count"] == 0
    evaluator.assert_not_called()


class _NeverStringify:
    def __str__(self):
        raise AssertionError("Invalid evidence must be rejected before string coercion.")


class _NeverIterate:
    def __iter__(self):
        pytest.fail("Unsupported evidence containers must be refused before iteration.")

    def __bool__(self):
        pytest.fail("Unsupported evidence containers must be refused before truth testing.")


class _NeverIterateList(_NeverIterate, list):
    pass


@pytest.mark.parametrize("channel", ["evidence", "retrieved"])
@pytest.mark.parametrize("container", [
    _NeverIterate, _NeverIterateList, lambda: iter([SimpleNamespace(text=CONTEXT, source_id=SOURCES["US"])]),
    lambda: (item for item in ()), dict, str, int,
], ids=["arbitrary", "list-subclass", "iterator", "generator", "mapping", "string", "integer"])
def test_worker_rejects_unsupported_evidence_collections(diagnostic, channel, container):
    run, service, evaluator = diagnostic
    invalid_result = _answer("US")
    setattr(invalid_result.response, channel, container())
    service.answer.side_effect = [invalid_result]

    assert run().error_category == "q01_invalid_context"
    evaluator.assert_not_called()


def test_both_evidence_collections_are_validated_before_reading_entries():
    response = SimpleNamespace(evidence=[object()], retrieved=_NeverIterate())
    with pytest.raises(ra.InvalidContextText, match="list or tuple"):
        ra.case_from_service_result("example", "question", response, strict_context_text=True)


@pytest.mark.parametrize("channel", ["evidence", "retrieved"])
@pytest.mark.parametrize("kind", ["entry", "source_id"])
def test_worker_rejects_malformed_entries_and_source_ids(diagnostic, channel, kind):
    run, service, evaluator = diagnostic
    answer = _answer("US", retrieved=(CONTEXT,))
    entries = getattr(answer.response, channel)
    if kind == "entry":
        entries[0] = {}
    elif channel == "evidence":
        entries[0].source_id = _NeverStringify()
    else:
        entries[0].chunk.metadata["manifest_source_id"] = _NeverStringify()
    service.answer.side_effect = [answer]

    assert run().error_category == "q01_invalid_context"
    evaluator.assert_not_called()


def test_strict_adapter_preserves_ordered_sources_from_both_channels():
    response = _answer("US", retrieved=(CONTEXT, "Additional retrieved text.")).response
    for entry in response.retrieved:
        entry.chunk.metadata = {"manifest_source_id": SOURCES["UK"]}
    response.citations = [SimpleNamespace(doc_id="unrelated-citation")]

    result = ra.case_from_service_result("example", "question", response, strict_context_text=True)

    assert result.retrieved_contexts == [CONTEXT, "Additional retrieved text."]
    assert result.source_ids == [SOURCES["US"], SOURCES["UK"]]


@pytest.mark.parametrize("malformed", [[""], _NeverStringify(), 0])
@pytest.mark.parametrize("channel", ["contexts", "retrieved"])
def test_worker_rejects_malformed_evidence_even_alongside_valid_text(diagnostic, malformed, channel):
    run, service, evaluator = diagnostic
    invalid_result = _answer("UK", **{channel: (CONTEXT, malformed)})
    service.answer.side_effect = [_answer("US"), invalid_result]

    result = run()

    assert result.is_failed and result.error_category == "q01_invalid_context"
    assert result.q01_diagnostics[-1]["retrieved_context_count"] == 0
    evaluator.assert_not_called()


def test_default_adapter_still_coerces_legacy_context_values():
    result = _answer("US", contexts=(["legacy"],))
    assert ra.case_from_service_result("example", "question", result).retrieved_contexts == ["['legacy']"]


@pytest.mark.parametrize(
    ("scores", "status", "valid"),
    [
        ({(CASE_IDS[1], ra.METRIC_CONTEXT_RECALL): None}, ra.STATUS_PARTIAL, 7),
        ({
            (CASE_IDS[0], ra.METRIC_CONTEXT_RECALL): float("nan"),
            (CASE_IDS[1], ra.METRIC_CONTEXT_RECALL): float("inf"),
        }, ra.STATUS_PARTIAL, 6),
        (dict.fromkeys(
            [(case_id, name) for case_id in CASE_IDS
             for name in [*REFERENCE_FREE, ra.METRIC_CONTEXT_RECALL]], float("nan"),
        ), ra.STATUS_FAILED, 0),
    ],
)
def test_existing_finite_score_accounting_applies_to_eight_slots(diagnostic, scores, status, valid):
    run, _, evaluator = diagnostic
    evaluator.side_effect = partial(_score_with(scores), config=None)
    result = run()
    assert result.status == status
    assert result.expected_score_count == 8
    assert result.valid_score_count == valid
    assert result.failed_score_count == 8 - valid
    assert result.metrics[ra.METRIC_CONTEXT_RECALL] == (0.0 if valid == 7 else None)
    assert all(ra.METRIC_CONTEXT_RECALL not in row for row in result.per_case if valid <= 6)
    if valid == 0:
        assert result.error_category == "no_valid_scores"
        assert result.safe_message == "Synthetic evaluator returned no valid scores."


def test_service_trace_keeps_question_country_separate_from_filter_market():
    service = CareerIntelligenceService()
    query = "What does a data analyst do in the United States?"
    explicit = service.retrieve_evidence(query, market="GB")
    ordinary = service.retrieve_evidence(query)

    assert explicit.trace.detected_country == ordinary.trace.detected_country == "US"
    assert explicit.trace.source_approval_market == "UK"
    assert ordinary.trace.source_approval_market == "US"


def test_ordinary_runner_still_accepts_question_only_service_and_limit(cases):
    def answer(question):
        return _answer("US")

    service = SimpleNamespace(answer=Mock(side_effect=answer))
    result = runner.run_live_ragas(
        config=None, evaluator_config=None, case_ids=CASE_IDS, limit=1, persist=False,
        service=service, run_ragas_fn=_score_with(),
    )

    service.answer.assert_called_once_with(cases[0].question)
    assert result.status == ra.STATUS_COMPLETE and result.case_count == 1
    assert result.q01_diagnostics == []
