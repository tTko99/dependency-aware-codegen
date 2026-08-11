from evaluation.metrics import aggregate_detection, precision_recall_f1, wilson_interval


def test_precision_recall_f1() -> None:
    scores = precision_recall_f1({"a", "b"}, {"b", "c"})

    assert scores["true_positive"] == 1
    assert scores["false_positive"] == 1
    assert scores["false_negative"] == 1
    assert scores["precision"] == 0.5
    assert scores["recall"] == 0.5
    assert scores["f1"] == 0.5


def test_aggregate_detection() -> None:
    records = [
        {"expected_invalid_apis": ["math.square_root"], "observed_invalid_apis": ["math.square_root"]},
        {"expected_invalid_apis": ["json.parse_json"], "observed_invalid_apis": []},
    ]

    scores = aggregate_detection(records, "apis")

    assert scores["true_positive"] == 1
    assert scores["false_negative"] == 1


def test_aggregate_detection_counts_repeated_occurrences() -> None:
    records = [
        {"expected_invalid_apis": ["math.fake"], "observed_invalid_apis": ["math.fake"]},
        {"expected_invalid_apis": ["math.fake"], "observed_invalid_apis": []},
    ]

    scores = aggregate_detection(records, "apis")

    assert scores["true_positive"] == 1
    assert scores["false_negative"] == 1


def test_wilson_interval_contains_observed_rate() -> None:
    interval = wilson_interval(50, 100)

    assert interval["low"] < 0.5 < interval["high"]
    assert interval["successes"] == 50
    assert interval["total"] == 100
