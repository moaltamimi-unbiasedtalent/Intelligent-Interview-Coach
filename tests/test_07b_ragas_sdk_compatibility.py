"""Genuine RAGAS orchestration against the offline 07B receiver and a disposable ledger."""

from __future__ import annotations

import asyncio
import json
import os
import threading
from dataclasses import replace
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from src.copilot.evaluation import ragas_adapter as ra
from src.llm.budget import governor as G
from src.llm.budget import script_guard
from src.llm.budget.errors import BudgetError
from src.persistence import AiBudgetEntry
from tests.test_07b_governed_provider_transport import EMBED, KEY, MODEL, URL, _build, env  # noqa: F401
from tests.test_ai_budget_governor_05c import body_usage

pytestmark = pytest.mark.skipif(
    os.environ.get("ASK4MO_TEST_GENUINE_RAGAS") != "1",
    reason="requires the explicitly selected, native-network-denied SDK qualification worker",
)

QUESTION = "What color is the synthetic square?"
OTHER_QUESTION = "Which shape is the synthetic figure?"
CASE = ra.RagasEvalCase("synthetic-square", QUESTION, "The square is blue.", ["The square is blue."])


class Receiver:
    def __init__(self, factory):
        self.factory = factory
        self.outcome = "valid"
        self.calls = []
        self.repairs = 0
        self.generated_question = "Which color is described?"
        self.malformed_at = 1
        self.started = threading.Event()
        self.temperatures = []
        self.metric_override = None
        self.embedding_override = None

    def __call__(self, request):
        body = json.loads(request.content)
        assert request.url.host == "openrouter.ai"
        assert request.headers.get("x-stainless-retry-count", "0") == "0"
        expected = {
            "/api/v1/chat/completions": ("ragas", "evaluation", MODEL),
            "/api/v1/embeddings": ("evaluator_embedding", "embedding", EMBED),
        }[request.url.path]
        self.check_reservation(expected, body["model"])
        self.calls.append(expected[0])
        if self.outcome == "timeout":
            raise httpx.ReadTimeout("synthetic", request=request)
        if self.outcome == "cancel":
            return self.wait_for_cancellation()
        if self.outcome == "rate_limit":
            return httpx.Response(429, json={"error": {"message": "synthetic"}})
        if self.outcome == "conflicting_charge":
            return httpx.Response(429, content=b'{"usage":{"cost":0.001,"cost":0},"error":{}}')
        if self.outcome == "server_error":
            return httpx.Response(503, json={"error": {"message": "synthetic"}})
        if self.outcome == "redirect":
            return httpx.Response(307, headers={"location": "https://fixture.invalid/redirect"})
        if expected[0] == "evaluator_embedding":
            result = {
                "object": "list", "model": EMBED,
                "data": [
                    {"object": "embedding", "index": i,
                     "embedding": [0.0, 1.0] if text == OTHER_QUESTION else [1.0, 0.0]}
                    for i, text in enumerate(body["input"])
                ],
                "usage": {"prompt_tokens": 20, "total_tokens": 20},
            }
            if self.embedding_override is not None:
                self.embedding_override(result)
            return httpx.Response(200, json=result)
        assert 0 < body["max_completion_tokens"] <= 500
        self.temperatures.append(body["temperature"])
        prompt = body["messages"][-1]["content"]
        if prompt.startswith("The output string did not satisfy"):
            self.repairs += 1
        content = {"question": self.generated_question, "noncommittal": 0}
        if prompt.startswith("Given a question and an answer"):
            content = {"statements": ["The square is blue."]}
        elif prompt.startswith("Your task is to judge the faithfulness"):
            content = {"statements": [{"statement": "The square is blue.", "reason": "synthetic", "verdict": 1}]}
        elif prompt.startswith("Given question, answer and context"):
            content = {"reason": "synthetic", "verdict": 1}
        elif prompt.startswith("Given a context, and an answer"):
            content = {"classifications": [{"statement": "The square is blue.", "reason": "synthetic", "attributed": 1}]}
        if self.metric_override is not None:
            self.metric_override(content)
        response = body_usage()
        response["choices"][0]["message"]["content"] = json.dumps(content)
        if self.outcome == "missing_usage":
            response.pop("usage")
        if self.outcome == "conflicting_success":
            response["usage"]["input_tokens"] = response["usage"]["prompt_tokens"] + 1
        if self.outcome == "contradictory_total":
            response["usage"]["total_tokens"] = 0
        if self.outcome == "unfinished":
            response["choices"][0]["finish_reason"] = "length"
        if self.outcome == "malformed_output" and len(self.calls) == self.malformed_at:
            response["choices"][0]["message"]["content"] = "invalid structured output"
        if self.outcome == "truncated":
            response["choices"][0]["message"]["content"] = json.dumps(content)[:-1]
        if self.outcome == "coerced":
            response["choices"][0]["message"]["content"] = json.dumps({**content, "noncommittal": "0"})
        if self.outcome == "nonfinite":
            response["choices"][0]["message"]["content"] = json.dumps({**content, "invalid": float("nan")})
        if self.outcome == "empty_question":
            response["choices"][0]["message"]["content"] = json.dumps({**content, "question": " "})
        if self.outcome == "conflicting_cost":
            usage = json.dumps(response["usage"]).removesuffix("}") + ',"cost":0.005,"cost":0}'
            response.pop("usage")
            wire = json.dumps(response).removesuffix("}") + ',"usage":' + usage + "}"
            return httpx.Response(200, content=wire)
        return httpx.Response(200, json=response)

    def check_reservation(self, expected, model):
        with self.factory() as session:
            row = session.scalars(select(AiBudgetEntry).where(AiBudgetEntry.state == "reserved")).one()
            assert (row.operation, row.category, row.model) == expected
            assert row.model == model
            assert row.reserved_micro_usd > 0

    async def wait_for_cancellation(self):
        self.started.set()
        await asyncio.Future()

    def rows(self):
        with self.factory() as session:
            return session.scalars(select(AiBudgetEntry).order_by(AiBudgetEntry.id)).all()


@pytest.fixture
def governed(env, monkeypatch, request):  # noqa: F811
    from ragas._analytics import do_not_track
    from src.copilot.evaluation.ragas_runner import _q01_network_denied

    assert _q01_network_denied()
    assert do_not_track()

    def deny(*args, **kwargs):
        pytest.fail("unexpected DNS, socket connection or non-governed transport")

    monkeypatch.setattr("socket.getaddrinfo", deny)
    monkeypatch.setattr("socket.socket.connect", deny)
    monkeypatch.setattr("socket.socket.connect_ex", deny)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", deny)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", deny)
    monkeypatch.setattr(script_guard, "getproxies", dict)
    if getattr(request, "param", None) == "one_request":
        from pathlib import Path

        from src.llm.budget.config import CONFIG_PATH_ENV

        path = Path(env[CONFIG_PATH_ENV])
        policy = json.loads(path.read_text())
        policy["total"]["max_requests"] = 1
        path.write_text(json.dumps(policy))
    _, engine, factory = _build(env)
    receiver = Receiver(factory)
    try:
        governor = script_guard.require_paid_budget(
            "genuine-sdk-fixture", environ=env, session_factory=factory,
            governed_07b=True, prototype_handler=receiver,
        )
        yield governor, receiver
    finally:
        G.uninstall()
        engine.dispose()


def _run_relevancy(*, strictness=1, question=QUESTION, answer=CASE.answer):
    from ragas.dataset_schema import SingleTurnSample
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import ResponseRelevancy

    llm, embeddings = ra._build_evaluator(ra.EvaluatorConfig(KEY, MODEL, URL, EMBED))
    assert type(llm) is LangchainLLMWrapper
    assert type(embeddings) is LangchainEmbeddingsWrapper
    assert llm.langchain_llm.max_retries == embeddings.embeddings.max_retries == 0
    case = ra.RagasEvalCase(CASE.case_id, question, answer, CASE.retrieved_contexts)
    sample = ra._to_sample(case, with_reference=False)
    assert type(sample) is SingleTurnSample
    metric = ResponseRelevancy(strictness=strictness)
    return ra._default_evaluate([sample], [("relevancy", metric)], llm, embeddings)


def test_single_real_metric_reserves_and_settles_chat_and_embeddings(governed):
    governor, receiver = governed
    assert _run_relevancy()[0]["relevancy"] == pytest.approx(1)
    assert receiver.calls == ["ragas", "evaluator_embedding", "evaluator_embedding"]
    rows = receiver.rows()
    assert [(r.state, r.committed_micro_usd) for r in rows] == [("settled", 20), ("settled", 2), ("settled", 2)]
    assert governor.status()["calls_by_state"] == {"settled": 3}
    assert governor.status()["integrity"]["consistent"]
    print("single_metric dispatches=3 settled=3")


@pytest.mark.parametrize(("response", "state", "reason"), [
    ("missing_usage", "unknown", "outcome_unknown"),
    ("rate_limit", "rejected", None),
    ("conflicting_charge", "unknown", "outcome_unknown"),
    ("server_error", "unknown", "outcome_unknown"),
    ("timeout", "unknown", None),
    ("redirect", "unknown", "outcome_unknown"),
])
def test_genuine_metric_transport_failure_has_one_dispatch(governed, response, state, reason):
    from openai import APIConnectionError, APITimeoutError, RateLimitError

    governor, receiver = governed
    receiver.outcome = response
    failure = {"rate_limit": RateLimitError, "timeout": APITimeoutError}.get(response, APIConnectionError)
    with pytest.raises(failure) as error:
        _run_relevancy()
    if reason:
        assert isinstance(error.value.__cause__, BudgetError)
        assert error.value.__cause__.reason == reason
    assert receiver.calls == ["ragas"]
    row, = receiver.rows()
    assert row.state == state
    assert row.provider_cost_micro_usd is None
    status = governor.status()
    assert status["integrity"]["consistent"]
    if state == "unknown":
        assert row.reserved_micro_usd > 0
        assert Decimal(status["unknown_held_usd"]) > 0
    else:
        assert Decimal(status["held_usd"]) == 0
    # Existing SQLite uses a non-null zero placeholder; UNKNOWN exposure
    # remains held independently. The PG16 test below requires SQL NULL.
    assert row.committed_micro_usd == 0
    with pytest.raises(BudgetError) as blocked:
        _run_relevancy(question=QUESTION + " Again?")
    assert blocked.value.reason == "evaluation_stopped"
    assert governor.status()["calls_by_state"] == {state: 1}
    print(f"{response} dispatches=1 state={state} error_category={row.error_category}")


def test_genuine_metric_refuses_kill_committed_before_handoff(governed, monkeypatch):
    from openai import APIConnectionError

    governor, receiver = governed
    handoff = governor.ledger.accept_07b_handoff

    def killed_handoff(reservation, accept):
        governor.ledger.kill("synthetic kill")
        return handoff(reservation, accept)

    monkeypatch.setattr(governor.ledger, "accept_07b_handoff", killed_handoff)
    with pytest.raises(APIConnectionError) as error:
        _run_relevancy()
    assert isinstance(error.value.__cause__, BudgetError)
    assert error.value.__cause__.reason == "kill_switch"
    assert receiver.calls == []
    row, = receiver.rows()
    assert (row.state, row.error_category) == ("rejected", "admission_changed")
    print("pre_handoff_kill dispatches=0 rejected=1")


def test_genuine_wrapper_cancellation_retains_unknown(governed):
    from langchain_core.prompt_values import StringPromptValue
    from ragas.run_config import RunConfig

    governor, receiver = governed
    receiver.outcome = "cancel"
    llm, _ = ra._build_evaluator(ra.EvaluatorConfig(KEY, MODEL, URL, EMBED))
    llm.set_run_config(RunConfig(max_workers=1, max_retries=1, timeout=2))

    async def cancel():
        task = asyncio.create_task(llm.generate(StringPromptValue(text="Synthetic cancellation")))
        async with asyncio.timeout(2):
            while not receiver.started.is_set():
                await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(cancel())
    assert receiver.calls == ["ragas"]
    row, = receiver.rows()
    assert row.state == "unknown" and row.reserved_micro_usd > 0 and row.committed_micro_usd == 0
    assert row.provider_cost_micro_usd is None
    assert governor.status()["calls_by_state"] == {"unknown": 1}
    print(f"cancel dispatches=1 state=unknown error_category={row.error_category}")


def test_default_response_relevancy_can_complete_under_no_replay_contract(governed):
    from ragas.metrics import ResponseRelevancy

    _, receiver = governed
    assert _run_relevancy(strictness=ResponseRelevancy().strictness)[0]["relevancy"] == pytest.approx(1)
    assert receiver.calls == ["ragas", "evaluator_embedding", "evaluator_embedding"]


def test_relevancy_reuses_an_identical_embedding_without_replay(governed):
    _, receiver = governed
    receiver.generated_question = QUESTION

    assert _run_relevancy()[0]["relevancy"] == pytest.approx(1)
    assert receiver.calls == ["ragas", "evaluator_embedding"]
    assert [row.state for row in receiver.rows()] == ["settled", "settled"]


def test_parser_repair_cannot_add_an_unapproved_model_dispatch(governed):
    from ragas.exceptions import RagasOutputParserException

    _, receiver = governed
    receiver.outcome = "malformed_output"
    with pytest.raises(RagasOutputParserException):
        _run_relevancy()
    assert receiver.calls == ["ragas"] and receiver.repairs == 0
    assert [row.state for row in receiver.rows()] == ["settled"]


@pytest.mark.parametrize("governed", ["one_request"], indirect=True)
def test_genuine_metric_cannot_exceed_aggregate_request_cap(governed):
    from openai import APIConnectionError

    governor, receiver = governed
    with pytest.raises(APIConnectionError) as error:
        _run_relevancy()
    assert isinstance(error.value.__cause__, BudgetError)
    assert error.value.__cause__.reason == "total_request_cap"
    assert receiver.calls == ["ragas"]
    assert governor.status()["calls_by_state"] == {"settled": 1}


def test_genuine_wrapper_token_overflow_and_foreign_transport_are_refused(governed):
    from langchain_core.prompt_values import StringPromptValue
    from openai import APIConnectionError

    _, receiver = governed
    llm, _ = ra._build_evaluator(ra.EvaluatorConfig(KEY, MODEL, URL, EMBED))
    with pytest.raises(APIConnectionError) as over:
        asyncio.run(llm.generate(StringPromptValue(text="synthetic " * 10000)))
    assert isinstance(over.value.__cause__, BudgetError)
    assert over.value.__cause__.reason == "input_too_large"
    with httpx.Client(transport=httpx.MockTransport(receiver), trust_env=False) as alternate:
        with pytest.raises(BudgetError) as refused:
            alternate.get("https://fixture.invalid/")
    assert refused.value.reason == "provider_host_not_allowed"
    with httpx.Client(transport=httpx.MockTransport(receiver), trust_env=False) as alternate:
        with pytest.raises(BudgetError) as unapproved:
            alternate.post(f"{URL}/chat/completions", json={})
    assert unapproved.value.reason == "transport_not_qualified"
    assert receiver.calls == [] and receiver.rows() == []


@pytest.mark.parametrize("outcome", ["valid", "malformed_output"])
def test_ragas_worker_lifetime_is_bounded(governed, monkeypatch, outcome):
    import ragas
    from ragas import _analytics
    from ragas.exceptions import RagasOutputParserException

    _, receiver = governed
    receiver.outcome = outcome
    # The SDK normally creates this daemon at import. Give each case a new
    # instance so a prior success cannot hide a missing failure-path cleanup.
    batcher = _analytics.AnalyticsBatcher()
    monkeypatch.setattr(_analytics, "_analytics_batcher", batcher)
    assert batcher._flush_thread.is_alive()
    original_evaluate = ragas.evaluate
    loops = []

    def inspect_loop(*args, **kwargs):
        loops.append(asyncio.get_event_loop())
        return original_evaluate(*args, **kwargs)

    monkeypatch.setattr(ragas, "evaluate", inspect_loop)
    try:
        if outcome == "valid":
            _run_relevancy()
        else:
            with pytest.raises(RagasOutputParserException):
                _run_relevancy()
        assert not batcher.buffer
        assert not batcher._flush_thread.is_alive()
        assert len(loops) == 1 and loops[0].is_closed()
    finally:
        batcher.shutdown()
        batcher._flush_thread.join(timeout=2)


@pytest.mark.parametrize("reference", [None, CASE.answer], ids=["reference-free", "with-reference"])
def test_default_adapter_completes_its_real_metric_set(governed, reference):
    governor, receiver = governed
    case = ra.RagasEvalCase(CASE.case_id, QUESTION, CASE.answer, CASE.retrieved_contexts, reference=reference)

    run = ra.run_ragas([case], config=ra.EvaluatorConfig(KEY, MODEL, URL, EMBED))

    assert run["status"] == ra.STATUS_COMPLETE
    assert run["valid_score_count"] == run["expected_score_count"] == (4 if reference else 3)
    assert receiver.calls.count("ragas") == (5 if reference else 4)
    assert receiver.calls.count("evaluator_embedding") == 2
    assert governor.status()["calls_by_state"] == {"settled": len(receiver.calls)}


def test_reference_recall_direct_multiple_prompt_has_no_parser_repair(governed):
    from ragas.exceptions import RagasOutputParserException

    _, receiver = governed
    receiver.outcome = "malformed_output"
    receiver.malformed_at = 7
    case = ra.RagasEvalCase(CASE.case_id, QUESTION, CASE.answer, CASE.retrieved_contexts, reference=CASE.answer)

    with pytest.raises(RagasOutputParserException):
        ra.run_ragas([case], config=ra.EvaluatorConfig(KEY, MODEL, URL, EMBED))
    assert len(receiver.calls) == 7 and receiver.calls[-1] == "ragas"
    assert receiver.repairs == 0



def _paired_cases(*, shared_answer=True, with_reference=False):
    first = replace(CASE, reference=CASE.answer if with_reference else None)
    other = replace(
        first, case_id="synthetic-other", question=OTHER_QUESTION,
        answer=first.answer if shared_answer else "The figure is a synthetic square.",
    )
    return [first, other]


def _assert_sample_scores(run, cases, *, with_reference):
    assert run["status"] == ra.STATUS_COMPLETE
    assert run["valid_score_count"] == run["expected_score_count"] == (8 if with_reference else 6)
    assert [row["case_id"] for row in run["per_case"]] == [case.case_id for case in cases]
    assert [row[ra.METRIC_RESPONSE_RELEVANCY] for row in run["per_case"]] == pytest.approx([1, 0])
    assert run["metrics"][ra.METRIC_RESPONSE_RELEVANCY] == pytest.approx(0.5)
    for metric in (ra.METRIC_FAITHFULNESS, ra.METRIC_CONTEXT_PRECISION):
        assert run["metrics"][metric] == pytest.approx(1)
    if with_reference:
        assert run["metrics"][ra.METRIC_CONTEXT_RECALL] == pytest.approx(1)


@pytest.mark.parametrize(("shared_answer", "with_reference"), [(True, False), (False, False), (True, True)])
def test_multicase_complete_sdk_metrics(governed, shared_answer, with_reference, tmp_path):
    from src.copilot.evaluation.ragas_runner import write_artifacts

    governor, receiver = governed
    cases = _paired_cases(shared_answer=shared_answer, with_reference=with_reference)
    config = ra.EvaluatorConfig(KEY, MODEL, URL, EMBED)
    run = ra.run_ragas(cases, config=config)

    _assert_sample_scores(run, cases, with_reference=with_reference)
    method = run["evaluation_method"]
    assert method["ragas_sdk_version"] == "0.2.15"
    assert (method["protocol_id"], method["protocol_version"], method["scope"]) == (
        "ask4mo-ragas-07b", 1, "governed_07b",
    )
    assert method["response_relevancy_generated_questions"] == 1 and method["settled_response_reuse"] is True
    assert method["metric_config"]["metrics"] == run["metric_names"]
    chat_calls = 8 + (2 if with_reference else 0) - (2 if shared_answer else 1)
    assert receiver.calls.count("ragas") == chat_calls
    assert receiver.calls.count("evaluator_embedding") == 3
    assert method["reuse_hits"] == {"chat": 8 + (2 if with_reference else 0) - chat_calls, "embeddings": 1}
    rows = receiver.rows()
    assert len(rows) == len(receiver.calls)
    assert all(row.state == "settled" and row.committed_micro_usd == (
        20 if row.operation == "ragas" else 2) for row in rows)
    assert governor.status()["calls_by_state"] == {"settled": len(rows)}
    assert governor.status()["integrity"]["consistent"]

    write_artifacts(tmp_path, run, config, "synthetic")
    run_config = json.loads((tmp_path / "run_config.json").read_text())
    assert run_config["evaluation_method"] == method
    assert json.loads((tmp_path / "results.json").read_text())["run_config"] == run_config
    summary = (tmp_path / "summary.md").read_text()
    assert "ask4mo-ragas-07b" in summary and "1 generated question" in summary
    assert "Historical three-question thresholds require separate qualification" in summary


def _prompt_for(reuse, *, answer=CASE.answer):
    from ragas.metrics import ResponseRelevancy
    from ragas.metrics._answer_relevance import ResponseRelevanceInput
    from ragas.run_config import RunConfig

    llm, _ = ra._build_evaluator(ra.EvaluatorConfig(KEY, MODEL, URL, EMBED))
    llm.set_run_config(RunConfig(max_workers=1, max_retries=1, timeout=2))
    metric = ResponseRelevancy()
    guarded = ra._without_output_repair(metric.question_generation, reuse,
                                        ("ragas", metric.name, "question_generation"))
    data = ResponseRelevanceInput(response=answer)

    async def generate(temperature=None):
        return await guarded.generate(llm, data, temperature=temperature)

    return generate


def test_exact_reuse_only_inside_run_and_with_matching_parameters(governed):
    from openai import APIConnectionError

    governor, receiver = governed
    reuse = ra._EvaluationReuse(governor)

    async def exercise():
        generate = _prompt_for(reuse)
        assert (await generate(0.0)).question == receiver.generated_question
        first_row, = receiver.rows()
        assert (await generate(0.0)).question == receiver.generated_question
        same_row, = receiver.rows()
        assert (same_row.id, same_row.committed_micro_usd, same_row.state) == (
            first_row.id, 20, "settled",
        )
        assert (await generate(0.5)).question == receiver.generated_question
        next_run = ra._EvaluationReuse(governor)
        with pytest.raises(APIConnectionError) as error:
            await _prompt_for(next_run)(0.0)
        assert error.value.__cause__.reason == "retry_limit"
        assert next_run.hits == {"chat": 0, "embeddings": 0} and not next_run.results

        governor.ledger.kill("synthetic kill after settlement")
        with pytest.raises(BudgetError, match="kill switch") as kill:
            await generate(0.0)
        assert kill.value.reason == "kill_switch"

    asyncio.run(exercise())
    assert receiver.calls == ["ragas", "ragas"] and receiver.temperatures == [0.0, 0.5]
    assert reuse.hits == {"chat": 1, "embeddings": 0}
    assert [(r.state, r.committed_micro_usd) for r in receiver.rows()] == [("settled", 20)] * 2


def test_stop_committed_between_approval_check_and_status_blocks_reuse(governed, monkeypatch):
    from src.llm.budget.ledger import DbBudgetLedger

    governor, receiver = governed
    writer = DbBudgetLedger(receiver.factory)
    reuse = ra._EvaluationReuse(governor)
    open_or_refuse = governor._open_or_refuse
    status = governor.status
    observed = []

    def authorize_then_stop():
        open_or_refuse()
        writer.kill("synthetic independent stop")

    def observe_status():
        snapshot = status()
        observed.append(snapshot["state"])
        return snapshot

    async def exercise():
        generate = _prompt_for(reuse)
        await generate()
        row, = receiver.rows()
        monkeypatch.setattr(governor, "_open_or_refuse", authorize_then_stop)
        monkeypatch.setattr(governor, "status", observe_status)
        with pytest.raises(BudgetError) as refused:
            await generate()
        assert refused.value.reason == "kill_switch"
        current, = receiver.rows()
        assert (current.id, current.fingerprint, current.state, current.committed_micro_usd) == (
            row.id, row.fingerprint, "settled", 20,
        )

    asyncio.run(exercise())
    assert observed == ["killed"] and receiver.calls == ["ragas"]
    assert reuse.hits["chat"] == 0 and len(reuse.results) == 1


def test_expiry_blocks_a_previously_settled_hit(governed, monkeypatch):
    governor, receiver = governed
    reuse = ra._EvaluationReuse(governor)

    async def exercise():
        generate = _prompt_for(reuse)
        await generate()
        monkeypatch.setitem(governor.config.approval, "expires_at", "2000-01-01T00:00:00Z")
        with pytest.raises(BudgetError) as refused:
            await generate()
        assert refused.value.reason == "approval_invalid"

    asyncio.run(exercise())
    assert receiver.calls == ["ragas"] and reuse.hits["chat"] == 0
    assert [(row.state, row.committed_micro_usd) for row in receiver.rows()] == [("settled", 20)]


def test_pending_duplicate_and_cancellation_cannot_publish_result(governed):
    governor, receiver = governed
    receiver.outcome = "cancel"
    reuse = ra._EvaluationReuse(governor)

    async def exercise():
        generate = _prompt_for(reuse)
        task = asyncio.create_task(generate())
        async with asyncio.timeout(2):
            try:
                while not receiver.started.is_set():
                    await asyncio.sleep(0)
                with pytest.raises(BudgetError) as pending:
                    await generate()
                assert pending.value.reason == "evaluation_request_pending"
                assert governor.status()["calls_by_state"] == {"reserved": 1}
            finally:
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
        with pytest.raises(BudgetError) as stopped:
            await generate()
        assert stopped.value.reason == "evaluation_stopped"

    asyncio.run(exercise())
    assert not reuse.pending and not reuse.results and reuse.hits == {"chat": 0, "embeddings": 0}
    assert receiver.calls == ["ragas"]
    row, = receiver.rows()
    assert row.state == "unknown" and row.committed_micro_usd == 0
    assert governor.status()["calls_by_state"] == {"unknown": 1}


@pytest.mark.parametrize("outcome", ["malformed_output", "truncated", "coerced", "nonfinite", "empty_question"])
def test_invalid_structured_response_never_becomes_a_hit(governed, outcome):
    from openai import APIConnectionError
    from ragas.exceptions import RagasOutputParserException

    governor, receiver = governed
    receiver.outcome = outcome
    reuse = ra._EvaluationReuse(governor)

    async def exercise():
        generate = _prompt_for(reuse)
        with pytest.raises(RagasOutputParserException):
            await generate()
        with pytest.raises(APIConnectionError) as repeat:
            await generate()
        assert repeat.value.__cause__.reason == "retry_limit"

    asyncio.run(exercise())
    assert receiver.calls == ["ragas"] and receiver.repairs == 0
    assert not reuse.results and reuse.hits == {"chat": 0, "embeddings": 0}
    assert governor.status()["calls_by_state"] == {"settled": 1}


@pytest.mark.parametrize("outcome", ["missing_usage", "rate_limit", "server_error", "timeout"])
def test_error_disables_reuse_of_a_previous_settlement(governed, outcome):
    from openai import APIConnectionError, APITimeoutError, RateLimitError

    governor, receiver = governed
    reuse = ra._EvaluationReuse(governor)
    error = {"timeout": APITimeoutError, "rate_limit": RateLimitError}.get(outcome, APIConnectionError)

    async def exercise():
        generate = _prompt_for(reuse)
        await generate(0.0)
        receiver.outcome = outcome
        with pytest.raises(error):
            await generate(0.2)
        with pytest.raises(BudgetError) as refused:
            await generate(0.0)
        assert refused.value.reason == "evaluation_stopped"

    asyncio.run(exercise())
    state = "rejected" if outcome == "rate_limit" else "unknown"
    assert [(r.state, r.committed_micro_usd) for r in receiver.rows()] == [("settled", 20), (state, 0)]
    assert receiver.calls == ["ragas", "ragas"]
    assert len(reuse.results) == 1 and reuse.hits == {"chat": 0, "embeddings": 0}
    assert governor.status()["calls_by_state"] == {"settled": 1, state: 1}


def test_settled_but_unusable_response_cannot_be_reused(governed):
    from openai import APIConnectionError
    from ragas.exceptions import LLMDidNotFinishException

    governor, receiver = governed
    receiver.outcome = "unfinished"
    reuse = ra._EvaluationReuse(governor)

    async def exercise():
        generate = _prompt_for(reuse)
        with pytest.raises(LLMDidNotFinishException):
            await generate()
        with pytest.raises(APIConnectionError) as replay:
            await generate()
        assert replay.value.__cause__.reason == "retry_limit"

    asyncio.run(exercise())
    assert receiver.calls == ["ragas"]
    assert not reuse.results and reuse.hits == {"chat": 0, "embeddings": 0}
    assert governor.status()["calls_by_state"] == {"settled": 1}


@pytest.mark.parametrize("outcome", ["conflicting_success", "contradictory_total", "conflicting_cost"])
def test_contradictory_usage_retains_sqlite_hold_and_blocks_reuse(governed, outcome):
    from openai import APIConnectionError

    governor, receiver = governed
    receiver.outcome = outcome
    reuse = ra._EvaluationReuse(governor)

    async def exercise():
        generate = _prompt_for(reuse)
        with pytest.raises(APIConnectionError) as exc:
            await generate()
        assert exc.value.__cause__.reason == "outcome_unknown"
        with pytest.raises(BudgetError) as blocked:
            await generate()
        assert blocked.value.reason == "evaluation_stopped"

    asyncio.run(exercise())
    row, = receiver.rows()
    assert (row.state, row.error_category, row.committed_micro_usd) == ("unknown", "contradictory_charge", 0)
    assert Decimal(governor.status()["unknown_held_usd"]) > 0
    if outcome == "conflicting_cost":
        assert row.provider_cost_micro_usd == 5000
        assert row.reserved_micro_usd >= 5000
    assert receiver.calls == ["ragas"] and not reuse.results and reuse.hits["chat"] == 0


@pytest.mark.parametrize(("metric_type", "value", "metric_name", "prompt_name"), [
    ("faithfulness", 2, "faithfulness", "nli_statements_prompt"),
    ("faithfulness", True, "faithfulness", "nli_statements_prompt"),
    ("faithfulness", "misaligned", "faithfulness", "nli_statements_prompt"),
    ("precision", -1, "llm_context_precision_without_reference", "context_precision_prompt"),
    ("precision", 0.5, "llm_context_precision_without_reference", "context_precision_prompt"),
    ("recall", 2, "context_recall", "context_recall_prompt"),
    ("recall", "1", "context_recall", "context_recall_prompt"),
])
def test_invalid_metric_verdict_keeps_charge_and_refuses_cache(governed, metric_type, value, metric_name, prompt_name):
    from ragas.exceptions import RagasOutputParserException

    governor, receiver = governed
    reuse = ra._EvaluationReuse(governor)

    def invalidate(content):
        if metric_type == "faithfulness" and isinstance(content.get("statements", [None])[0], dict):
            item = content["statements"][0]
            item["statement" if value == "misaligned" else "verdict"] = value
        if metric_type == "precision" and "verdict" in content:
            content["verdict"] = value
        if metric_type == "recall" and "classifications" in content:
            content["classifications"][0]["attributed"] = value

    receiver.metric_override = invalidate
    case = replace(CASE, reference=CASE.answer)
    llm, embeddings = ra._build_evaluator(ra.EvaluatorConfig(KEY, MODEL, URL, EMBED))
    binding, = [(name, metric) for name, metric in ra._build_metrics(reference_free_only=False)
                if metric.name == metric_name]
    with pytest.raises(RagasOutputParserException):
        ra._default_evaluate([ra._to_sample(case, with_reference=True)], [binding], llm, embeddings, reuse=reuse)
    namespace = "ragas", metric_name, prompt_name
    assert not any(key[0] == namespace for _, key in reuse.results)
    assert reuse.hits["chat"] == 0 and receiver.repairs == 0
    assert receiver.calls == ["ragas"] * (2 if metric_type == "faithfulness" else 1)
    assert [(row.state, row.committed_micro_usd) for row in receiver.rows()] == [
        ("settled", 20) for _ in receiver.calls
    ]


@pytest.mark.parametrize("fault", ["missing-index", "negative-index", "wrong-index", "duplicate-index",
                                   "missing-vector", "base64-nonfinite", "nonfinite-vector", "short-response"])
def test_invalid_raw_embedding_stays_settled_but_never_reusable(governed, fault):
    import base64
    import struct

    from openai import APIConnectionError

    governor, receiver = governed
    reuse = ra._EvaluationReuse(governor)
    _, embeddings = ra._build_evaluator(ra.EvaluatorConfig(KEY, MODEL, URL, EMBED))
    model = embeddings.embeddings

    def invalidate(body):
        entry = body["data"][0]
        if fault == "missing-index":
            del entry["index"]
        elif fault in ("negative-index", "wrong-index"):
            entry["index"] = -1 if fault == "negative-index" else 99
        elif fault == "duplicate-index":
            body["data"][1]["index"] = 0
        elif fault == "missing-vector":
            del entry["embedding"]
        elif fault == "base64-nonfinite":
            entry["embedding"] = base64.b64encode(struct.pack("<f", float("inf"))).decode()
        elif fault == "nonfinite-vector":
            entry["embedding"] = [10**700]  # Finite JSON integer, not representable as an SDK float.
        elif fault == "short-response":
            body["data"].pop()

    receiver.embedding_override = invalidate
    texts = [QUESTION, OTHER_QUESTION] if fault in ("duplicate-index", "short-response") else [QUESTION]
    payload = {"input": texts, "encoding_format": "base64", **model._invocation_params}
    key = reuse.key(("ragas", "relevancy_embeddings"), model.client._client, "embeddings", payload)
    with pytest.raises(APIConnectionError) as exc, reuse.request(key, model.http_client, "embeddings") as (_, publish):
        publish(model.embed_documents(texts))
    assert exc.value.__cause__.reason == "evaluation_result_unverified"
    assert not reuse.results and reuse.hits["embeddings"] == 0
    row, = receiver.rows()
    assert (row.state, row.committed_micro_usd) == ("settled", 2)
    assert receiver.calls == ["evaluator_embedding"]


def test_wrong_embedding_index_aborts_real_multicase_evaluation(governed):
    from openai import APIConnectionError

    governor, receiver = governed

    def wrong_index(body):
        body["data"][0]["index"] = 99

    receiver.embedding_override = wrong_index
    with pytest.raises(APIConnectionError) as exc:
        ra.run_ragas(_paired_cases(), config=ra.EvaluatorConfig(KEY, MODEL, URL, EMBED))
    assert exc.value.__cause__.reason == "evaluation_result_unverified"
    assert receiver.calls.count("evaluator_embedding") == 1
    rows = receiver.rows()
    assert len(rows) == len(receiver.calls)
    assert all(row.state == "settled" for row in rows)
    assert governor.status()["calls_by_state"] == {"settled": len(rows)}


def test_out_of_order_embedding_response_reaches_real_sdk_in_input_order(governed):
    governor, receiver = governed
    reuse = ra._EvaluationReuse(governor)
    _, embeddings = ra._build_evaluator(ra.EvaluatorConfig(KEY, MODEL, URL, EMBED))
    model = embeddings.embeddings

    def reverse(body):
        body["data"].reverse()

    receiver.embedding_override = reverse
    texts = [QUESTION, OTHER_QUESTION]
    payload = {"input": texts, "encoding_format": "base64", **model._invocation_params}
    key = reuse.key(("ragas", "relevancy_embeddings"), model.client._client, "embeddings", payload)
    with reuse.request(key, model.http_client, "embeddings") as (_, publish):
        vectors = model.embed_documents(texts)
        assert vectors == [[1, 0], [0, 1]]
        publish(vectors)
    with reuse.request(key, model.http_client, "embeddings") as (cached, publish):
        assert cached == vectors and publish is None
    assert receiver.calls == ["evaluator_embedding"] and reuse.hits["embeddings"] == 1
    row, = receiver.rows()
    assert (row.state, row.committed_micro_usd) == ("settled", 2)


def test_unrelated_settlement_inside_cache_decision_does_not_replace_exact_receipt(governed, monkeypatch):
    from tests.test_07b_governed_provider_transport import _dispatch, _request

    governor, receiver = governed
    reuse = ra._EvaluationReuse(governor)
    settle_response = governor.settle_response
    interleaved = False

    def settle_then_interleave(*args):
        nonlocal interleaved
        receipt = settle_response(*args)
        if not interleaved:
            interleaved = True
            unrelated = _request(body={
                "model": MODEL, "messages": [{"role": "user", "content": "Synthetic unrelated request"}],
                "max_tokens": 32,
            })
            _dispatch(governor, unrelated, lambda _: httpx.Response(200, json=body_usage()))
        return receipt

    monkeypatch.setattr(governor, "settle_response", settle_then_interleave)

    async def score_twice():
        generate = _prompt_for(reuse)
        assert (await generate()).question == receiver.generated_question
        assert (await generate()).question == receiver.generated_question

    asyncio.run(score_twice())
    rows = receiver.rows()
    assert [(row.state, row.committed_micro_usd) for row in rows] == [("settled", 20)] * 2
    (receipt, _), = reuse.results.values()
    assert (receipt.entry_id, receipt.binding.fingerprint) == (rows[0].id, rows[0].fingerprint)
    assert not reuse.pending and reuse.hits["chat"] == 1 and receiver.calls == ["ragas"]


@pytest.mark.parametrize("fault", ["absent", "entry_id", "fingerprint", "ledger_identity", "policy_hash"])
def test_response_and_settlement_count_cannot_substitute_for_receiver_proof(governed, monkeypatch, fault):
    governor, receiver = governed
    reuse = ra._EvaluationReuse(governor)
    original = governor.settle_response

    def transform(reservation, model, response, started):
        receipt = original(reservation, model, response, started)
        assert receipt is not None
        response.extensions["settlement_receipt"] = receipt  # HTTP responses are not a receipt channel.
        if fault == "absent":
            return None
        if fault == "entry_id":
            return replace(receipt, entry_id=receipt.entry_id + 1)
        changed = {"fingerprint": "0" * 64, "policy_hash": "0" * 64, "ledger_identity": object()}
        return replace(receipt, binding=replace(receipt.binding, **{fault: changed[fault]}))

    monkeypatch.setattr(governor, "settle_response", transform)
    with pytest.raises(BudgetError) as exc:
        asyncio.run(_prompt_for(reuse)())
    assert exc.value.reason == "evaluation_result_unverified"
    assert not reuse.pending and not reuse.results and reuse.hits["chat"] == 0
    assert receiver.calls == ["ragas"]
    row, = receiver.rows()
    assert (row.state, row.committed_micro_usd) == ("settled", 20)


@pytest.mark.parametrize("first_state", ["reserved", "unknown"])
def test_unrelated_ledger_settles_while_evaluation_row_stays_unproven(governed, tmp_path, monkeypatch, first_state):
    from tests.test_07b_governed_provider_transport import _request

    governor, receiver = governed
    reuse = ra._EvaluationReuse(governor)
    directory = tmp_path / "other-ledger"
    directory.mkdir()
    other, engine, factory = _build(env.__wrapped__(directory))
    try:
        def settle_other(reservation, model, response, started):
            if first_state == "unknown":
                assert governor.ledger.settle(reservation, outcome="unknown", error_category="usage_missing") is None
            unrelated = _request()
            b, b_model, b_started = other.reserve(unrelated, "chat", {})
            other.ledger.accept_07b_handoff(b, lambda: None)
            receipt_b = other.settle_response(b, b_model, httpx.Response(200, json=body_usage()), b_started)
            assert receipt_b is not None
            return receipt_b

        monkeypatch.setattr(governor, "settle_response", settle_other)
        with pytest.raises(BudgetError) as refusal:
            asyncio.run(_prompt_for(reuse)())
        assert refusal.value.reason == "reconciliation_required"
        assert not reuse.results and reuse.hits["chat"] == 0
        row, = receiver.rows()
        other_row, = Receiver(factory).rows()
        assert (row.state, row.committed_micro_usd) == (first_state, 0)
        assert (other_row.state, other_row.committed_micro_usd) == ("settled", 20)
        assert other_row.fingerprint != row.fingerprint and receiver.calls == ["ragas"]
    finally:
        engine.dispose()


def test_ordinary_adapter_preserves_genuine_sdk_metric_configuration(monkeypatch):
    import ragas
    from ragas.metrics import ResponseRelevancy

    seen = []

    class Frame:
        columns = []
        def __len__(self):
            return 0

    class Result:
        def to_pandas(self):
            return Frame()

    def score(**kwargs):
        metric = next(item for item in kwargs["metrics"] if isinstance(item, ResponseRelevancy))
        seen.append(metric.strictness)
        assert set(kwargs) == {"dataset", "metrics", "llm", "embeddings"}
        return Result()

    monkeypatch.setattr(ragas, "evaluate", score)
    run = ra.run_ragas([CASE], config=ra.EvaluatorConfig(KEY, MODEL, URL, EMBED),
                       build_evaluator_fn=lambda _: (object(), object()))
    method = run["evaluation_method"]
    assert seen == [3]
    assert method["scope"] == "ordinary" and method["protocol_id"] == "ragas-sdk-default"
    assert method["response_relevancy_generated_questions"] == 3
    assert method["settled_response_reuse"] is False
    assert run["status"] == ra.STATUS_FAILED and run["valid_score_count"] == 0


def test_governed_worker_does_not_drain_an_active_ordinary_sdk_run(governed, monkeypatch):
    from ragas import _analytics

    _, receiver = governed
    batcher = _analytics.AnalyticsBatcher()
    monkeypatch.setattr(_analytics, "_analytics_batcher", batcher)
    try:
        with ra._sdk_activity(governed=False):
            with pytest.raises(ra.RagasNotConfigured, match="dedicated SDK worker"):
                _run_relevancy()
            assert batcher._flush_thread.is_alive()
        assert receiver.calls == [] and receiver.rows() == []
    finally:
        batcher.shutdown()
        batcher._flush_thread.join(timeout=2)

@pytest.mark.skipif(
    os.environ.get("ASK4MO_TEST_GENUINE_RAGAS_PG") != "1",
    reason="requires the fixture-owned PG16 loopback worker",
)
@pytest.mark.parametrize(("outcome", "reason"), [
    ("missing_usage", "usage_missing"),
    ("contradictory_total", "contradictory_charge"),
    ("conflicting_cost", "contradictory_charge"),
])
def test_genuine_sdk_with_postgresql_durable_settlement(request, outcome, reason):
    from openai import APIConnectionError

    database = request.getfixturevalue("database")

    class PostgresReceiver(Receiver):
        def check_reservation(self, expected, model):
            rows = database.query(
                "SELECT operation, category, model, reserved_micro_usd, accepted_at IS NOT NULL "
                "FROM ask4mo_07b.entry WHERE state = 'reserved'",
            )
            row, = rows
            assert row[:3] == expected and row[2] == model
            assert row[3] > 0 and row[4]

    receiver = PostgresReceiver(None)
    governor = script_guard.require_paid_budget(
        "genuine-sdk-pg-fixture", environ=database.env, governed_07b=True, prototype_handler=receiver,
    )
    cases = _paired_cases(with_reference=True)
    run = ra.run_ragas(cases, config=ra.EvaluatorConfig(KEY, MODEL, URL, EMBED))
    _assert_sample_scores(run, cases, with_reference=True)
    assert run["evaluation_method"]["reuse_hits"] == {"chat": 2, "embeddings": 1}
    assert receiver.calls.count("ragas") == 8 and receiver.calls.count("evaluator_embedding") == 3
    before = list(receiver.calls)

    receiver.outcome = outcome
    reuse = ra._EvaluationReuse(governor)
    with pytest.raises(APIConnectionError) as error:
        asyncio.run(_prompt_for(reuse, answer="The synthetic circle is green.")())
    assert not reuse.results and reuse.hits["chat"] == 0
    assert isinstance(error.value.__cause__, BudgetError) and error.value.__cause__.reason == "outcome_unknown"
    assert receiver.calls == before + ["ragas"]
    rows = database.query(
        "SELECT state, committed_micro_usd, held_micro_usd, error_category "
        "FROM ask4mo_07b.entry ORDER BY id",
    )
    assert rows[:-1] == [
        ("settled", 20 if operation == "ragas" else 2, 0, None)
        for operation in before
    ]
    state, committed, held, category = rows[-1]
    assert state == "unknown" and committed is None and held > 0 and category == reason
    assert database.query("SELECT killed FROM ask4mo_07b.control") == [(True,)]
    status = governor.status()
    assert status["calls_by_state"] == {"settled": len(before), "unknown": 1}
    assert status["integrity"]["consistent"]
    if outcome == "conflicting_cost":
        assert held >= 5000
        assert database.query("SELECT reported_micro_usd FROM ask4mo_07b.entry WHERE state = 'unknown'") == [(5000,)]
    if reason == "contradictory_charge":
        with pytest.raises(BudgetError) as stopped:
            asyncio.run(_prompt_for(reuse, answer="Another synthetic answer.")())
        assert stopped.value.reason == "evaluation_stopped"
        G.uninstall()
        with pytest.raises(BudgetError) as blocked:
            script_guard.require_paid_budget(
                "genuine-sdk-pg-restart", environ=database.env, governed_07b=True, prototype_handler=receiver,
            )
        assert blocked.value.reason == "kill_switch"
        assert database.query("SELECT killed FROM ask4mo_07b.control") == [(True,)]
        assert receiver.calls == before + ["ragas"] and database.query(
            "SELECT state, committed_micro_usd, held_micro_usd, error_category "
            "FROM ask4mo_07b.entry ORDER BY id",
        ) == rows
    print(f"genuine_pg {outcome} dispatches={len(receiver.calls)} settled={len(before)} unknown=1")
