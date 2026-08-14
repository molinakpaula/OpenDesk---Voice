"""Regression tests for documented module boundaries and architecture records."""

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ArchitectureTests(unittest.TestCase):
    def test_root_main_remains_a_thin_entry_point(self) -> None:
        main_text = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")
        meaningful_lines = [
            line
            for line in main_text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

        self.assertLessEqual(len(meaningful_lines), 5)
        self.assertIn("from maderaflow.api import app", main_text)

    def test_expected_application_modules_exist(self) -> None:
        expected_modules = {
            "api.py",
            "config.py",
            "errors.py",
            "models.py",
            "repositories.py",
            "support.py",
        }
        module_directory = PROJECT_ROOT / "maderaflow"

        self.assertTrue(module_directory.is_dir())
        self.assertTrue(
            expected_modules.issubset(
                {path.name for path in module_directory.glob("*.py")}
            )
        )

    def test_architecture_and_decision_records_exist(self) -> None:
        required_documents = [
            PROJECT_ROOT / "docs" / "architecture.md",
            PROJECT_ROOT / "docs" / "data-model.md",
            PROJECT_ROOT / "docs" / "decisions" / "README.md",
        ]
        decision_records = list(
            (PROJECT_ROOT / "docs" / "decisions").glob("[0-9][0-9][0-9]-*.md")
        )

        for document in required_documents:
            with self.subTest(document=document.name):
                self.assertTrue(document.is_file())
        self.assertGreaterEqual(len(decision_records), 6)

    def test_config_layer_does_not_import_fastapi(self) -> None:
        config_text = (PROJECT_ROOT / "maderaflow" / "config.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("from fastapi", config_text)
        self.assertNotIn("import fastapi", config_text)

    def test_repository_layer_does_not_import_fastapi(self) -> None:
        repository_text = (
            PROJECT_ROOT / "maderaflow" / "repositories.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("from fastapi", repository_text)
        self.assertNotIn("import fastapi", repository_text)


if __name__ == "__main__":
    unittest.main()
