"""Small host-owned validation projection; historical records never authorize PASS."""
from depguard.agent.regression import regression_guard


def validation_summary(state):
    checks = {}
    for name in sorted(state.required_checks):
        record = state.check_results.get(name)
        if (state.passed_checks.get(name) == state.version
                and state.check_state_versions.get(name) == state.context_version):
            checks[name] = "passed"
        elif record is not None:
            checks[name] = ("stale" if record.candidate_version != state.version
                or state.check_result_contexts.get(name) != state.context_version else "failed")
        elif name in state.passed_checks or name in state.check_state_versions:
            checks[name] = "stale"
        else:
            checks[name] = "missing"
    blocked = regression_guard(state)["blocked"]
    return {"candidate_version": state.version, "required_checks": checks,
            "ready_to_finish_successfully": bool(checks) and all(
                value == "passed" for value in checks.values()) and not blocked,
            "regression_blocked": blocked}


def finish_outcome(args):
    """Explicit failure wins; legacy conclusion-only finish remains supported."""
    if args.get("success") is False or args.get("outcome") in {"failure", "abandoned"}:
        return "failure"
    if args.get("conclusion", "").strip().lower() in {"fail", "failed", "abandoned", "unable"}:
        return "failure"
    return "success"
