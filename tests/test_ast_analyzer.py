from depguard.analysis import DependencyAnalyzer


def test_import_extraction_and_alias_resolution() -> None:
    code = """
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from pathlib import Path

df = pd.read_csv("input.csv")
arr = np.array([1, 2, 3])
df.drop(columns=["x"])
plt.plot([1], [2])
scaler = StandardScaler()
p = Path(".")
p.exists()
"""
    result = DependencyAnalyzer().analyze(code)

    assert result.syntax_error is None
    assert result.alias_table["pd"].canonical_path == "pandas"
    assert result.alias_table["np"].canonical_path == "numpy"
    assert result.alias_table["plt"].canonical_path == "matplotlib.pyplot"
    assert result.alias_table["StandardScaler"].canonical_path == (
        "sklearn.preprocessing.StandardScaler"
    )
    assert result.alias_table["Path"].canonical_path == "pathlib.Path"

    paths = {ref.canonical_path for ref in result.api_references}
    assert "pandas.read_csv" in paths
    assert "numpy.array" in paths
    assert "matplotlib.pyplot.plot" in paths
    assert "sklearn.preprocessing.StandardScaler" in paths
    assert "pandas.DataFrame.drop" in paths
    assert "pathlib.Path.exists" in paths


def test_syntax_error_is_structured() -> None:
    result = DependencyAnalyzer().analyze("def broken(:\n    pass")

    assert result.syntax_error is not None
    assert result.imports == []
    assert result.api_references == []
