import json

from depguard import cli
from depguard.agent.safety import sha256_file


def test_apply_with_failed_finish_leaves_source_untouched(tmp_path, capsys):
    source = tmp_path / "input.py"
    source.write_text("result = missing\n")
    script = tmp_path / "script.json"
    script.write_text(json.dumps({"actions": [{"name": "finish", "arguments": {"success": True}},
        {"name": "finish", "arguments": {"success": False}}]}))
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"agent": {"provider": "scripted", "script": str(script)}}))
    initial = sha256_file(source)
    assert cli.main(["agent", "--config", str(config), "--code-file", str(source),
                     "--project-root", str(tmp_path), "--apply"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["final_status"] == "FAIL" and not result["applied"]
    assert result["candidate_revision"] == 0 and result["candidate_sha256"] == initial
    assert result["config_hashes"][str(config.resolve())] == sha256_file(config)
    assert sha256_file(source) == initial and not list(tmp_path.glob(".depguard-*"))
