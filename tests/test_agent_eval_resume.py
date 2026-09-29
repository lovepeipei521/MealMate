from tests.agent_eval_runner import is_resumable_case


def make_case(requires_network=False):
    return {
        "case_id": "case-1",
        "category": "tool_selection",
        "question": "测试问题",
        "requires_network": requires_network,
    }


def make_record(case, *, status="completed", http_status=200, run_status="succeeded"):
    return {
        "case_id": case["case_id"],
        "repeat_index": 0,
        "evaluation_profile": "baseline",
        "status": status,
        "case": case,
        "result": {"http_status": http_status},
        "run": {"status": run_status},
    }


def test_resume_reuses_only_successful_completed_case():
    case = make_case()
    record = make_record(case)

    assert is_resumable_case(
        [record],
        case,
        include_network=False,
        evaluation_profile="baseline",
    )


def test_resume_retries_failed_or_skipped_case():
    case = make_case()

    for record in (
        make_record(case, http_status=503, run_status=None),
        make_record(case, run_status="failed"),
        make_record(case, status="skipped", http_status=None, run_status=None),
    ):
        assert not is_resumable_case(
            [record],
            case,
            include_network=False,
            evaluation_profile="baseline",
        )


def test_resume_retries_network_case_that_was_previously_skipped():
    case = make_case(requires_network=True)
    record = make_record(case, status="skipped", http_status=None, run_status=None)

    assert not is_resumable_case(
        [record],
        case,
        include_network=True,
        evaluation_profile="baseline",
    )
