"""Heuristic regression evidence, not a proof of correctness or absence of cheating."""
import ast

from depguard.agent.patching import normalized_diff
from depguard.agent.paths import path_guard


def regression_guard(state):
    findings = []

    def add(code, severity, **details):
        findings.append({"code": code, "severity": severity, **details})

    refusal = path_guard(state, state.source_path.relative_to(state.project_root).as_posix())
    if refusal:
        add(refusal.evidence["error_code"], "error")
    try:
        after = ast.parse(state.candidate_code)
    except SyntaxError:
        add("INVALID_SYNTAX", "error")
        return {"blocked": True, "findings": findings}
    try:
        before = ast.parse(state.original_code)
    except SyntaxError:
        before = ast.Module(body=[], type_ignores=[])
        add("ORIGINAL_SYNTAX_UNAVAILABLE", "warning")

    def public(tree):
        return {n.name for n in tree.body if isinstance(
            n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not n.name.startswith("_")}

    removed = sorted(public(before) - public(after))
    if removed:
        add("PUBLIC_API_REMOVED", "error", names=removed)

    def signals(tree):
        rows = []
        aliases = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                aliases.update({n.asname or n.name: n.name for n in node.names})
            if isinstance(node, ast.ImportFrom):
                aliases.update({n.asname or n.name: f"{node.module}.{n.name}" for n in node.names})

        def name(node):
            if isinstance(node, ast.Name):
                return aliases.get(node.id, node.id)
            if isinstance(node, ast.Attribute):
                return name(node.value) + "." + node.attr
            return ""

        for node in ast.walk(tree):
            if isinstance(node, (ast.Call, ast.Attribute)):
                target = name(node.func if isinstance(node, ast.Call) else node)
                if target.startswith("pytest.") and target.split(".")[-1] in {"skip", "skipif", "xfail"}:
                    rows.append(("TEST_BYPASS", "error", ast.dump(node)))
            if isinstance(node, ast.ExceptHandler) and not any(isinstance(n, ast.Raise)
                    for statement in node.body for n in ast.walk(statement)):
                rows.append(("EXCEPTION_SUPPRESSED", "warning", ast.dump(node)))
        return rows

    existing = {row[2] for row in signals(before)}
    for code, severity, signature in signals(after):
        if signature not in existing and not any(f["code"] == code for f in findings):
            add(code, severity)
    # A changed computation replaced by a literal matching a visible assertion is
    # suspicious, but may be a legitimate fix: warn, never treat it as proof of cheating.
    try:
        tests = ast.parse(state.test_code or "")
        expected = {repr(n.value) for a in ast.walk(tests) if isinstance(a, ast.Assert)
                    for n in ast.walk(a.test) if isinstance(n, ast.Constant)}
        old_nodes = {ast.dump(n) for n in ast.walk(before)}
        if any(isinstance(n, (ast.Assign, ast.Return)) and isinstance(n.value, ast.Constant)
               and repr(n.value.value) in expected and ast.dump(n) not in old_nodes
               for n in ast.walk(after)):
            add("ASSERTION_CONSTANT_MATCH", "warning")
    except SyntaxError:
        add("TEST_SYNTAX_UNAVAILABLE", "warning")
    diff = normalized_diff(state.original_code, state.candidate_code, "source.py")
    changed = sum(row.startswith(("+", "-")) and not row.startswith(("+++", "---"))
                  for row in diff.splitlines())
    files = int(state.original_code != state.candidate_code)
    if changed > state.regression_config.get("max_patch_lines", 500):
        add("PATCH_SIZE_EXCEEDED", "error", changed_lines=changed)
    if files > state.regression_config.get("max_files", 1):
        add("FILE_COUNT_EXCEEDED", "error", changed_files=files)
    return {"blocked": any(f["severity"] == "error" for f in findings), "findings": findings,
            "changed_lines": changed, "changed_files": files, "heuristic": True}


def verification(state):
    missing = sorted(name for name in state.required_checks
                     if state.passed_checks.get(name) != state.version
                     or state.check_state_versions.get(name) != state.context_version)
    regression = regression_guard(state)
    return {"required_checks": sorted(state.required_checks), "missing_checks": missing,
            "candidate_version": state.version, "context_version": state.context_version,
            "regression_guard": regression,
            "host_status": "FAIL" if missing or regression["blocked"] else "PASS"}
