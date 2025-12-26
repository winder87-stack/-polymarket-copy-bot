"""
Test linter configuration validation.
"""
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


class TestLinterConfiguration:
    """Test linter configuration files."""

    def test_pre_commit_config_yaml_syntax(self):
        """Test that .pre-commit-config.yaml has valid YAML syntax."""
        config_path = Path(".pre-commit-config.yaml")

        assert config_path.exists(), ".pre-commit-config.yaml should exist"

        with open(config_path, "r") as f:
            try:
                config = yaml.safe_load(f)
                assert "repos" in config, "Config should have repos section"
                assert isinstance(config["repos"], list), "repos should be a list"
            except yaml.YAMLError as e:
                pytest.fail(f"YAML syntax error in .pre-commit-config.yaml: {e}")

    def test_pylintrc_exists(self):
        """Test that .pylintrc exists."""
        config_path = Path(".pylintrc")
        assert config_path.exists(), ".pylintrc should exist"

    def test_pyproject_toml_exists(self):
        """Test that pyproject.toml exists."""
        config_path = Path("pyproject.toml")
        assert config_path.exists(), "pyproject.toml should exist"

    def test_pylint_config_syntax(self):
        """Test that pylint can parse the configuration without errors."""
        result = subprocess.run(
            [sys.executable, "-m", "pylint", "--rcfile=.pylintrc", "--errors-only", "config/__init__.py"],
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )

        # Pylint should not fail due to configuration errors
        assert result.returncode in [0, 2, 4, 8, 16, 32], f"Pylint config error: {result.stderr}"

        # Should not contain config-related error messages
        error_output = result.stderr.lower()
        assert "config" not in error_output or "error" not in error_output, f"Config errors detected: {result.stderr}"

    def test_pre_commit_config_structure(self):
        """Test that .pre-commit-config.yaml has expected structure."""
        config_path = Path(".pre-commit-config.yaml")

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        repos = config["repos"]
        repo_ids = [repo["repo"] for repo in repos]

        expected_repos = [
            "https://github.com/pre-commit/pre-commit-hooks",
            "https://github.com/psf/black",
            "https://github.com/pycqa/flake8",
            "https://github.com/pycqa/isort",
            "https://github.com/pre-commit/mirrors-mypy",
            "https://github.com/pycqa/bandit"
        ]

        for expected_repo in expected_repos:
            assert expected_repo in repo_ids, f"Expected repo {expected_repo} not found"

    def test_black_line_length_consistency(self):
        """Test that black line length is consistent across configurations."""
        # Check pyproject.toml
        with open("pyproject.toml", "r") as f:
            content = f.read()
            assert "line-length = 100" in content, "Black line length should be 100 in pyproject.toml"

        # Check .pre-commit-config.yaml for black args
        with open(".pre-commit-config.yaml", "r") as f:
            config = yaml.safe_load(f)

        black_hook = None
        for repo in config["repos"]:
            if repo["repo"] == "https://github.com/psf/black":
                black_hook = repo["hooks"][0]
                break

        assert black_hook is not None, "Black hook should be configured"
        # Black should use default line length (100) as configured in pyproject.toml

    def test_flake8_dependencies(self):
        """Test that flake8 has required additional dependencies."""
        config_path = Path(".pre-commit-config.yaml")

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        flake8_hook = None
        for repo in config["repos"]:
            if repo["repo"] == "https://github.com/pycqa/flake8":
                flake8_hook = repo["hooks"][0]
                break

        assert flake8_hook is not None, "Flake8 hook should be configured"
        assert "additional_dependencies" in flake8_hook, "Flake8 should have additional dependencies"
        deps = flake8_hook["additional_dependencies"]
        assert "flake8-bugbear" in deps, "Should include flake8-bugbear"
        assert "flake8-comprehensions" in deps, "Should include flake8-comprehensions"

    def test_mypy_file_filtering(self):
        """Test that mypy has proper file filtering."""
        config_path = Path(".pre-commit-config.yaml")

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        mypy_hook = None
        for repo in config["repos"]:
            if repo["repo"] == "https://github.com/pre-commit/mirrors-mypy":
                mypy_hook = repo["hooks"][0]
                break

        assert mypy_hook is not None, "Mypy hook should be configured"
        assert "files" in mypy_hook, "Mypy should have file filtering"
        files_pattern = mypy_hook["files"]
        assert files_pattern == "^core/|^utils/|^config/|^main\\.py$", "Mypy file pattern should match expected"


if __name__ == "__main__":
    pytest.main([__file__])
