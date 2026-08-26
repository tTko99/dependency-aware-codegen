from __future__ import annotations

import json
from argparse import Namespace
from types import SimpleNamespace

import pytest

from depguard import cli


def test_run_reads_optional_test_file_and_preserves_source(tmp_path, capsys) -> None:
    source_path = tmp_path / "input.py"
    test_path = tmp_path / "test_input.py"
    source_text = "result = 1\n"
    source_path.write_text(source_text, encoding="utf-8")
    test_path.write_text(
        "from solution import result\n\ndef test_result():\n    assert result == 2\n",
        encoding="utf-8",
    )

    exit_code = cli.main(
        [
            "run",
            "--requirement",
            "Expose the integer two as result.",
            "--code-file",
            str(source_path),
            "--test-file",
            str(test_path),
            "--repair",
            "none",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["execution_result"]["status"] == "failed"
    assert payload["repair_attempted"] is False
    assert payload["final_status"] == "FAIL"
    assert source_path.read_text(encoding="utf-8") == source_text


def test_run_without_test_file_remains_supported(tmp_path, capsys) -> None:
    source_path = tmp_path / "input.py"
    source_path.write_text("result = 1\n", encoding="utf-8")

    exit_code = cli.main(
        ["run", "--code-file", str(source_path), "--repair", "none"]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["execution_result"]["status"] == "passed"
    assert payload["final_status"] == "NO_REPAIR_NEEDED"


def test_json_output_cannot_overwrite_source_file(tmp_path) -> None:
    source_path = tmp_path / "input.py"
    source_text = "result = 1\n"
    source_path.write_text(source_text, encoding="utf-8")

    with pytest.raises(SystemExit, match="must not overwrite"):
        cli.main(
            [
                "run",
                "--code-file",
                str(source_path),
                "--output",
                str(source_path),
                "--repair",
                "none",
            ]
        )

    assert source_path.read_text(encoding="utf-8") == source_text


def test_final_status_is_pass_for_successful_repair() -> None:
    result = SimpleNamespace(
        repaired_code="result = 2\n",
        repaired_analysis=SimpleNamespace(syntax_error=None),
        repaired_package_results=[],
        repaired_api_results=[],
        repaired_execution_result=SimpleNamespace(status="passed"),
    )

    assert cli._derive_final_status(result) == "PASS"


def test_external_code_never_loads_generator_from_config(monkeypatch) -> None:
    class UnexpectedGenerator:
        def __init__(self, **kwargs) -> None:
            raise AssertionError("Generator must not load for supplied code")

    monkeypatch.setattr(cli, "HFCausalCodeGenerator", UnexpectedGenerator)
    config = {
        "generation": {"kind": "hf", "hf": {"model_name": "unused-generator"}},
        "repair": {"kind": "none"},
        "execution": {"enabled": False},
    }
    args = Namespace(
        code=None,
        code_file="external.py",
        generator=None,
        repair=None,
        timeout=None,
    )

    pipeline = cli._build_pipeline(config, args)

    assert pipeline.generator is None
