from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_requirements_include_runtime_dependencies():
    requirements_path = ROOT / "requirements.txt"

    assert requirements_path.exists()
    requirements = requirements_path.read_text(encoding="utf-8").lower().splitlines()

    for package in ["streamlit", "simpy", "pandas", "numpy", "plotly"]:
        assert package in requirements


def test_dev_requirements_include_pytest_dependencies():
    requirements_path = ROOT / "requirements-dev.txt"

    assert requirements_path.exists()
    requirements = requirements_path.read_text(encoding="utf-8").lower()

    assert "pytest" in requirements
    assert "pytest-cov" in requirements


def test_readme_contains_required_project_documentation():
    readme_path = ROOT / "README.md"

    assert readme_path.exists()
    readme = readme_path.read_text(encoding="utf-8").lower()

    assert "software server queue simulation dashboard" in readme
    assert "queueing models for software systems" in readme
    assert "m/m/c" in readme
    assert "utilization" in readme
    assert "streamlit run app.py" in readme
    assert "healthy system" in readme
    assert "overloaded system" in readme
    assert "optimized system" in readme
    assert "limitations" in readme
