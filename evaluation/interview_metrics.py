"""M7 evidence-based counts; never use model prose or infrastructure demonstrations as rescues."""
from collections import Counter
from statistics import mean, median

CHECKS = {"validate_packages", "validate_apis", "execute", "run_pytest"}


def ratio(n, d):
    return {"numerator": n, "denominator": d, "rate": n / d if d else None}


def real_pass(row):
    checks = row.get("final_verification", {})
    return (row.get("status") in {"PASS", "NO_REPAIR_NEEDED"}
            and row.get("unchanged", False) and checks.get("host_status") == "PASS"
            and checks.get("candidate_version") == row.get("candidate_version")
            and not checks.get("regression_guard", {}).get("blocked", False)
            and all(checks.get("checks", {}).get(n, {}).get("status") == "success"
                    and checks["checks"][n].get("evidence", {}).get("passed") is True
                    and checks["checks"][n].get("candidate_version") == row.get("candidate_version")
                    for n in row.get("required_checks", CHECKS)))


def protocol_entered(row):
    return (row.get("capability_probe", {}).get("status") == "passed"
            and any(s.get("tool_call") and s["tool_result"].get("evidence", {}).get("kind")
                    != "protocol_error" for s in row.get("trajectory", [])))


def strict_rescue(a, b):
    patches = [s for s in b.get("trajectory", []) if (s.get("tool_call") or {}).get("name") == "apply_patch"
               and s["tool_result"]["status"] == "success"]
    detail = {"eligible": False, "rescued": False, "first_repair_status": "NOT_OBSERVED",
              "failure_observation_step": None, "rescued_patch_step": None}
    if patches:
        first = patches[0]
        # A failed real check must belong to the FIRST successfully patched candidate,
        # occur before a second patch, and be present in the next decision's messages.
        cutoff = patches[1]["step"] if len(patches) > 1 else float("inf")
        failures = [s for s in b.get("trajectory", []) if first["step"] < s["step"] < cutoff
                    and (s.get("tool_call") or {}).get("name") in CHECKS
                    and s["tool_result"]["status"] == "success"
                    and s["tool_result"].get("candidate_version") == first["tool_result"].get("candidate_version")
                    and s["tool_result"].get("evidence", {}).get("passed") is False
                    and s.get("observation", {}).get("evidence", {}).get("passed") is False]
        if failures:
            detail.update(first_repair_status="FAIL", failure_observation_step=failures[-1]["step"])
        elif real_pass(b) and len(patches) == 1:
            detail["first_repair_status"] = "PASS"
    else:
        failures = []
    comparable = (a.get("mode") == b.get("mode") == "live"
                  and a.get("comparison_identity") == b.get("comparison_identity")
                  and bool(a.get("comparison_identity"))
                  and a.get("cohort") == b.get("cohort") == "hard")
    eligible = (comparable and a.get("status") == "FAIL" and a.get("repair_attempted")
                and a.get("final_verification", {}).get("host_status") == "FAIL"
                and a.get("unchanged") and protocol_entered(b))
    detail["eligible"] = bool(eligible)
    finished = any((s.get("tool_call") or {}).get("name") == "finish"
                   and s["tool_result"]["status"] == "success"
                   for s in b.get("trajectory", []))
    if eligible and failures and len(patches) >= 2 and real_pass(b) and finished:
        later = next((p for p in patches[1:] if
                      p["tool_result"].get("candidate_version", "").split(":")[-1]
                      != patches[0]["tool_result"].get("candidate_version", "").split(":")[-1]
                      and failures[-1]["step"] in p.get("observed_steps", [])), None)
        if later:
            detail.update(rescued=True, rescued_patch_step=later["step"])
    return detail


def costs(rows):
    if not rows:
        return {"runs": 0, "mean_steps": None, "median_steps": None, "mean_model_calls": None,
                "mean_seconds": None, "p95_seconds": None, "input_tokens": None, "output_tokens": None}
    times = sorted(r.get("latency", 0) for r in rows)
    usage = [r.get("tokens") for r in rows]
    return {"runs": len(rows), "mean_steps": mean(len(r.get("trajectory", [])) for r in rows),
            "median_steps": median(len(r.get("trajectory", [])) for r in rows),
            "mean_model_calls": mean(r.get("model_calls", 0) for r in rows),
            "mean_seconds": mean(times), "p95_seconds": times[-(-95*len(times)//100)-1] if len(times) >= 20 else None,
            "mean_validation_calls": mean(validation_counts(r)["total"] for r in rows),
            "p95_policy": "nearest rank; at least 20 completed attempts",
            "input_tokens": sum(u["input"] for u in usage) if all(u is not None for u in usage) else None,
            "output_tokens": sum(u["output"] for u in usage) if all(u is not None for u in usage) else None}


def validation_counts(row):
    formal = sum((s.get("tool_call") or {}).get("name") in CHECKS for s in row.get("trajectory", []))
    initial = len(row.get("initial_verification", {}).get("checks", {}))
    final = len(row.get("final_verification", {}).get("checks", {}))
    # NO_REPAIR_NEEDED reuses the initial evidence; it is not a second execution.
    if row.get("status") == "NO_REPAIR_NEEDED":
        final = 0
    return {"formal": formal, "initial_host": initial, "final_host": final,
            "total": formal + initial + final}


def correctly_denied(op):
    result = op.get("tool_result", {})
    return (result.get("status") == "denied" and bool(op.get("expected_code"))
            and result.get("evidence", {}).get("error_code") == op["expected_code"]
            and result.get("evidence", {}).get("executed") is not True)


def summarize(rows):
    live = [r for r in rows if r.get("mode") == "live" and r.get("attempted")]
    loops = [r for r in live if r["condition"] == "loop"]
    pairs = {(r["case_id"], r["condition"]): r for r in live}
    rescues = [strict_rescue(pairs[(b["case_id"], "one-shot")], b) for b in loops
               if (b["case_id"], "one-shot") in pairs]
    calls = [s for r in loops for s in r.get("trajectory", []) if s.get("tool_call")
             and s["tool_call"]["name"] == "apply_patch"]
    claims = [r for r in loops if any(s.get("tool_call") and s["tool_call"]["name"] == "finish"
              and (s["tool_call"].get("arguments", {}).get("success") is True
                   or s["tool_call"].get("arguments", {}).get("conclusion", "").strip().upper() == "PASS")
              for s in r.get("trajectory", []))]
    infra = [r for r in rows if r.get("condition") == "infrastructure"]
    expected = [op for r in infra for op in r.get("expected_operations", [])]
    rollback = [r for r in infra if r.get("rollback_required")]
    return {
        "capability_probe": ratio(sum(r.get("capability_probe", {}).get("status") == "passed"
                                      for r in loops), len(loops)),
        "tool_protocol": ratio(sum(protocol_entered(r) for r in loops), len(loops)),
        "probe_failures": dict(Counter(r.get("capability_probe", {}).get("stage", "unknown") + ":" +
            r.get("capability_probe", {}).get("reason", "unknown") for r in loops
            if r.get("capability_probe", {}).get("status") == "failed")),
        "patch_acceptance": ratio(sum(s["tool_result"]["status"] == "success" for s in calls), len(calls)),
        "patch_failures": dict(Counter(s["tool_result"].get("evidence", {}).get("error_code", "OTHER")
                                       for s in calls if s["tool_result"]["status"] != "success")),
        "strict_rescue": ratio(sum(d["rescued"] for d in rescues), sum(d["eligible"] for d in rescues)),
        "one_shot_failure_count": sum(r["condition"] == "one-shot" and r.get("cohort") == "hard"
                                      and r["status"] == "FAIL" and r.get("repair_attempted", False) for r in live),
        "false_success": ratio(sum(not real_pass(r) for r in claims), len(claims)),
        "conditions": {c: {"true_pass": ratio(sum(real_pass(r) for r in live if r["condition"] == c),
                                              sum(r["condition"] == c for r in live)),
            "hard_pass": ratio(sum(real_pass(r) for r in live if r["condition"] == c and r.get("cohort") == "hard"),
                               sum(r["condition"] == c and r.get("cohort") == "hard" for r in live)),
            "controls_unmodified": ratio(sum(not r.get("candidate_changed") and not r.get("patch_count", 0)
                                             and r.get("unchanged", False) for r in live
                                             if r["condition"] == c and r.get("is_control")),
                                         sum(r["condition"] == c and r.get("is_control", False) for r in live)),
            "controls": ratio(sum(real_pass(r) and not r.get("candidate_changed") and not r.get("patch_count", 0) for r in live
                                   if r["condition"] == c and r.get("is_control")),
                               sum(r["condition"] == c and r.get("is_control", False) for r in live)),
            "cost": costs([r for r in live if r["condition"] == c])} for c in ("one-shot", "loop")},
        "infrastructure_only": {"unauthorized_refusal": ratio(sum(correctly_denied(op) for op in expected), len(expected)),
            "rollback": ratio(sum(r.get("rollback", {}).get("attempted", False)
                                  and bool(r.get("original_sha256"))
                                  and r.get("restored_sha256") == r.get("original_sha256")
                                  and r.get("rollback", {}).get("succeeded", False) for r in rollback), len(rollback))},
        "not_run": dict(Counter(r["status"] for r in rows if not r.get("attempted", True))),
        "case_count": len(rows),
        "all_live_inputs_unchanged": all(r.get("unchanged", False) for r in live) if live else None,
    }
