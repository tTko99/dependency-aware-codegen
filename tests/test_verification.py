from depguard.analysis import DependencyAnalyzer
from depguard.verification import APIVerifier, PackageVerifier


def test_package_verifier_valid_and_invalid_package() -> None:
    verifier = PackageVerifier()

    assert verifier.verify_package("math").exists is True
    invalid = verifier.verify_package("definitely_not_a_real_pkg_9900")
    assert invalid.exists is False
    assert invalid.status == "hallucinated_package"


def test_api_verifier_valid_and_invalid_function() -> None:
    analyzer = DependencyAnalyzer()
    references = analyzer.analyze("import math\nprint(math.sqrt(4))\nprint(math.square_root(4))\n").api_references
    results = {result.reference.canonical_path: result for result in APIVerifier().verify_many(references)}

    assert results["math.sqrt"].api_valid is True
    assert results["math.square_root"].api_valid is False
    assert results["math.square_root"].status == "hallucinated_function"
    assert "math.sqrt" in results["math.square_root"].suggestions


def test_api_verifier_detects_incorrect_arguments() -> None:
    references = DependencyAnalyzer().analyze("import math\nmath.sqrt()\n").api_references
    result = APIVerifier().verify(references[0])

    assert result.api_valid is False
    assert result.status == "incorrect_arguments"


def test_api_verifier_validates_imported_class_and_method() -> None:
    code = "from pathlib import Path\np = Path('.')\np.exists()\n"
    references = DependencyAnalyzer().analyze(code).api_references
    results = {result.reference.canonical_path: result for result in APIVerifier().verify_many(references)}

    assert results["pathlib.Path"].api_valid is True
    assert results["pathlib.Path.exists"].api_valid is True
