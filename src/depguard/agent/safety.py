"""Conservative static screening. This is not a proof of safety or a sandbox."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from depguard.agent.contracts import AgentState, ToolResult

# Only these installed modules may be imported by reflection/execution without an
# external sandbox. Unknown imports are findings, including local project modules.
TRUSTED_MODULES = {
    "math", "cmath", "statistics", "collections", "json", "textwrap", "pathlib",
    "urllib", "decimal", "fractions", "datetime", "itertools", "functools",
    "operator", "re", "string", "typing", "heapq", "bisect", "random", "pytest",
    "solution",
}
DANGEROUS_NAMES = {"eval", "exec", "compile", "__import__", "open", "input",
                   "globals", "locals", "vars", "setattr", "delattr", "breakpoint"}
DANGEROUS_MEMBERS = {
    "write", "writelines", "write_text", "write_bytes", "open", "touch", "mkdir",
    "unlink", "rmdir", "rename", "replace", "chmod", "symlink_to", "hardlink_to",
    "post", "put", "patch", "delete", "request", "urlopen", "urlretrieve", "send",
    "sendall", "connect", "system", "popen", "spawn", "load", "loads",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_state(source_path, test_path=None, *, project_root=None, permissions=None,
               config_paths=(), **options):
    root = Path(project_root or Path.cwd()).resolve()
    source = Path(source_path).resolve()
    tests = Path(test_path).resolve() if test_path else None
    allowed = set(permissions) if permissions is not None else {
        "read_source", "read_tests", "execute", "write_temp",
    }
    if "read_source" not in allowed or (tests and "read_tests" not in allowed):
        raise PermissionError("Input read permission denied")
    for path in (source, tests):
        if path and not path.is_relative_to(root):
            raise PermissionError("Input path must be inside project root")
    if tests == source:
        raise ValueError("Source and test must be separate files")
    # Hash the exact bytes that are decoded; do not read twice during initialization.
    data = {str(path): path.read_bytes() for path in (source, tests) if path}
    code = data[str(source)].decode("utf-8")
    options.setdefault("write_scope", {str(source)})
    regression = options.get("regression_config", {})
    for key in ("max_patch_lines", "max_files"):
        if key in regression and (type(regression[key]) is not int or regression[key] < 0):
            raise ValueError(f"regression_guard.{key} must be a nonnegative integer")
    return AgentState(
        code, code, root, source, tests, data[str(tests)].decode("utf-8") if tests else None,
        {path: hashlib.sha256(raw).hexdigest() for path, raw in data.items()},
        permissions=allowed, config_hashes={str(Path(p).resolve()): sha256_file(Path(p))
                                           for p in config_paths if p}, **options,
    )


def integrity_guard(state):
    expected_paths = {str(p) for p in (state.source_path, state.test_path) if p}
    if set(state.input_hashes) != expected_paths:
        return ToolResult("denied", "Missing frozen input hashes")
    for name, expected in state.input_hashes.items():
        try:
            path = Path(name)
            if path.resolve() != path or not path.is_relative_to(state.project_root):
                return ToolResult("denied", "Input path changed or escaped project root", {
                    "error_code": "TEST_INTEGRITY_MISMATCH" if path == state.test_path
                    else "SOURCE_INTEGRITY_MISMATCH"})
            actual = sha256_file(path)
        except OSError as exc:
            return ToolResult("denied", "Input unavailable", {"path": name, "error": str(exc),
                "error_code": "TEST_INTEGRITY_MISMATCH" if Path(name) == state.test_path
                else "SOURCE_INTEGRITY_MISMATCH"})
        if actual != expected:
            return ToolResult("denied", "Input SHA-256 changed", {
                "path": name, "expected": expected, "actual": actual,
                "error_code": "TEST_INTEGRITY_MISMATCH" if path == state.test_path
                else "SOURCE_INTEGRITY_MISMATCH",
            })
    for name, expected in state.config_hashes.items():
        try:
            actual = sha256_file(Path(name))
        except OSError:
            actual = None
        if actual != expected:
            return ToolResult("denied", "Configuration SHA-256 changed", {
                "error_code": "CONFIG_INTEGRITY_MISMATCH", "path": name,
                "expected": expected, "actual": actual,
            })
    return None


def risk_findings(code):
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [{"line": exc.lineno, "reason": "syntax_error", "detail": str(exc)}]
    aliases = {}
    findings = []

    def add(node, reason, detail):
        finding = {"line": getattr(node, "lineno", 0), "reason": reason, "detail": detail}
        if finding not in findings:
            findings.append(finding)

    def resolve(node):
        if isinstance(node, ast.Name):
            return aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            parent = resolve(node.value)
            return f"{parent}.{node.attr}" if parent else None
        if isinstance(node, ast.Call):
            target = resolve(node.func)
            if target == "getattr":
                if len(node.args) == 2 and constant_string(node.args[1]) is not None:
                    parent = resolve(node.args[0])
                    if parent and parent.split(".")[0] in TRUSTED_MODULES | {
                            "os", "subprocess", "shutil", "builtins", "socket", "requests"}:
                        return f"{parent}.{constant_string(node.args[1])}"
                    return None
                return None
            # Track constructor receivers (Path(...).write_text and assigned receivers).
            return target if target and (
                target.split(".")[-1][:1].isupper() or target.split(".")[0] in TRUSTED_MODULES
            ) else None
        return None

    def constant_string(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = constant_string(node.left), constant_string(node.right)
            if left is not None and right is not None:
                return left + right
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split(".")[0]] = (
                    item.name if item.asname else item.name.split(".")[0]
                )
                if item.name.split(".")[0] not in TRUSTED_MODULES:
                    add(node, "untrusted_import", item.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level or module.split(".")[0] not in TRUSTED_MODULES:
                add(node, "untrusted_import", module)
            for item in node.names:
                aliases[item.asname or item.name] = f"{module}.{item.name}"
                if item.name == "*":
                    add(node, "dynamic_import", "star import")
    # Fixed-point alias propagation handles f = os.system; g = f and getattr aliases.
    assignments = [n for n in ast.walk(tree) if isinstance(n, (ast.Assign, ast.AnnAssign))]
    for _ in range(len(assignments) + 1):
        changed = False
        for node in assignments:
            target = resolve(node.value)
            for dest in node.targets if isinstance(node, ast.Assign) else [node.target]:
                if isinstance(dest, ast.Name) and target and aliases.get(dest.id) != target:
                    aliases[dest.id] = target
                    changed = True
        if not changed:
            break
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in DANGEROUS_NAMES:
            add(node, "dangerous_reference", node.id)
        if isinstance(node, ast.Attribute) and node.attr in DANGEROUS_MEMBERS:
            target = resolve(node)
            if target not in {"json.loads", "json.load"}:
                add(node, "side_effect_reference", target or node.attr)
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            add(node, "dynamic_attribute", node.attr)
        if not isinstance(node, ast.Call):
            continue
        target = resolve(node.func)
        if target is None:
            add(node, "unresolved_call", ast.unparse(node.func))
            continue
        leaf = target.split(".")[-1]
        root = target.split(".")[0]
        if leaf in DANGEROUS_NAMES or root in {
            "subprocess", "os", "shutil", "socket", "requests", "http", "httpx",
            "pickle", "marshal", "ctypes", "importlib", "builtins",
        }:
            add(node, "dangerous_call", target)
        if leaf in DANGEROUS_MEMBERS and target not in {"json.loads", "json.load"}:
            add(node, "side_effect_call", target)
        if target == "getattr" and resolve(node) is None:
            add(node, "dynamic_attribute", "attribute name/receiver cannot be resolved")
        if "urllib." in target and not target.startswith("urllib.parse."):
            add(node, "network", target)
    return findings


def guard_tool(state, spec):
    missing = set(spec.permissions) - state.permissions
    # Every operation rechecks both inputs, including finish and cache hits.
    missing |= {"read_source"} - state.permissions
    if state.test_path:
        missing |= {"read_tests"} - state.permissions
    if missing:
        return ToolResult("denied", "Permission denied", {"missing_permissions": sorted(missing)})
    integrity = integrity_guard(state)
    if integrity:
        return integrity
    if spec.name not in {"execute", "run_pytest", "validate_apis", "validate_packages"}:
        return None
    findings = [{"input": "candidate", **f} for f in risk_findings(state.candidate_code)]
    if spec.name == "run_pytest" and state.test_code is not None:
        findings += [{"input": "tests", **f} for f in risk_findings(state.test_code)]
    if not findings:
        return None
    evidence = {"risk_policy": state.risk_policy, "findings": findings, "passed": False,
                "executed": False, "requires_sandbox": True, "error_code": "REQUIRES_SANDBOX"}
    if state.risk_policy == "mock":
        return ToolResult("mock", "MOCK ONLY: code was NOT executed; cannot establish PASS", evidence)
    return ToolResult("denied", "REQUIRES_SANDBOX: risk detected; execution refused", evidence)
