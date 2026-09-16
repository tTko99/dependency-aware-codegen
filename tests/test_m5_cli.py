import json
from pathlib import Path

import pytest

from depguard import cli


def test_cli_scripted_example_and_artifact(tmp_path, capsys):
    output = tmp_path / "trajectory.json"
    source = Path("examples/m5/input.py")
    tests = Path("examples/m5/test_input.py")
    original = (source.read_bytes(), tests.read_bytes())
    exit_code = cli.main([
        "agent", "--config", "configs/m5_scripted.json", "--code-file", str(source),
        "--test-file", str(tests), "--trajectory-output", str(output),
        "--protocol-error-limit", "2", "--recent-steps", "2",
        "--observation-max-length", "2000",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0 and payload["final_status"] == "PASS"
    assert json.loads(output.read_text()) == payload
    assert payload["capability_probe"]["status"] == "passed"
    assert payload["capabilities"]["scripted_test_provider"]
    assert not payload["applied"]
    assert (source.read_bytes(), tests.read_bytes()) == original


def test_cli_cloud_missing_credential_is_clear_preflight_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("M5_NONEXISTENT_KEY", raising=False)
    config = tmp_path / "cloud.json"
    config.write_text(json.dumps({"agent": {"provider": "cloud", "model_name": "test-model",
                                           "cloud": {"api_key_env": "M5_NONEXISTENT_KEY"}}}))
    result = cli.main(["agent", "--config", str(config), "--code-file", "examples/m5/input.py",
                       "--test-file", "examples/m5/test_input.py"])
    payload = json.loads(capsys.readouterr().out)
    assert result == 1 and payload["termination_reason"] == "MODEL_TOOL_PROTOCOL_UNSUPPORTED"
    assert payload["trajectory"] == []
    assert payload["capabilities"]["native_tool_calling"] == "unknown"
    assert payload["capability_probe"]["model_response_kind"] == "provider_error"


def test_trajectory_output_cannot_overwrite_source(tmp_path):
    source = tmp_path / "input.py"
    source.write_text("result=1\n")
    with pytest.raises(SystemExit, match="must not overwrite"):
        cli.main(["agent", "--code-file", str(source), "--trajectory-output", str(source)])
    assert source.read_text() == "result=1\n"
