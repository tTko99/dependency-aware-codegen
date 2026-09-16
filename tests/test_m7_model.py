import json
from pathlib import Path

from depguard.agent.contracts import AgentDecision
from depguard.models.cloud import CloudToolCallingModel
from depguard.models.scripted import ScriptedTestModel
from evaluation.interview_benchmark import evaluate_case


def test_cloud_text_condition_uses_same_parameters_without_tools(monkeypatch):
    monkeypatch.setenv("M7_FAKE_KEY", "test-only-key")
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return json.dumps({"model":"pinned-model", "usage":{"prompt_tokens":11,"completion_tokens":7},
                "choices":[{"message":{"content":"result = 2", "reasoning_content":"hidden"}}]}).encode()
    def transport(request, *, timeout):
        payload = json.loads(request.data)
        assert "tools" not in payload and "tool_choice" not in payload
        assert payload["max_tokens"] == 1024 and payload["temperature"] == 0
        return Response()
    model = CloudToolCallingModel("pinned-model", api_key_env="M7_FAKE_KEY", transport=transport)
    decision = model.decide([],[],timeout_seconds=3)
    assert decision.kind == "text" and decision.raw_response["usage"]["prompt_tokens"] == 11
    assert "hidden" not in str(decision.raw_response)


def test_one_shot_uses_same_host_checks_and_never_writes_inputs(tmp_path):
    source, test = tmp_path/"input.py", tmp_path/"test_input.py"
    source.write_text("result = 1\n")
    test.write_text("from solution import result\ndef test_result():\n    assert result == 2\n")
    from evaluation.prepare_interview import CHECKS
    case = {"id":"test", "cohort":"hard", "is_control":False, "code_file":str(source),
            "test_file":str(test), "requirement":"Return two", "required_checks":CHECKS}
    model = ScriptedTestModel([AgentDecision(kind="text", raw_response={"content":"result = 2"})])
    config = json.loads(Path("configs/m7_ollama.json").read_text())
    result = evaluate_case(case, "one-shot", config, model, mode="infrastructure")
    assert result["model_calls"] == 1 and result["status"] == "PASS"
    assert result["unchanged"] and source.read_text() == "result = 1\n"
    assert set(result["final_verification"]["checks"]) == set(CHECKS)
