import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import download


class ModelDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.models_directory = Path(self.temporary_directory.name)
        self.model_bytes = b"complete-model-weights"
        self.specification = {"path": "checkpoints/anime.safetensors", "size": len(self.model_bytes),
                              "sha256": hashlib.sha256(self.model_bytes).hexdigest(), "url": "https://models.example/anime"}
        self.model_path = self.models_directory / self.specification["path"]
        self.model_path.parent.mkdir()

    def test_skips_an_existing_verified_model_without_network(self):
        self.model_path.write_bytes(self.model_bytes)
        with patch.object(download.subprocess, "run") as transfer:
            download.install_model(self.models_directory, self.specification)
        transfer.assert_not_called()
        self.assertEqual(self.model_path.read_bytes(), self.model_bytes)

    def test_resumes_partial_download_and_installs_only_after_verification(self):
        pending_path = self.model_path.with_suffix(".safetensors.part")
        pending_path.write_bytes(self.model_bytes[:4])

        def finish_download(command, **options):
            self.assertEqual(pending_path.read_bytes(), self.model_bytes[:4])
            self.assertIn("--continue-at", command)
            pending_path.write_bytes(self.model_bytes)

        with patch.object(download.subprocess, "run", side_effect=finish_download):
            download.install_model(self.models_directory, self.specification)
        self.assertEqual(self.model_path.read_bytes(), self.model_bytes)
        self.assertFalse(pending_path.exists())

    def test_invalid_download_preserves_previous_model(self):
        self.model_path.write_bytes(b"previous-model")
        pending_path = self.model_path.with_suffix(".safetensors.part")
        with patch.object(download.subprocess, "run", side_effect=lambda *arguments, **options: pending_path.write_bytes(b"corrupt")):
            with self.assertRaises(ValueError):
                download.install_model(self.models_directory, self.specification)
        self.assertEqual(self.model_path.read_bytes(), b"previous-model")

    def test_interrupted_download_keeps_partial_file_for_next_start(self):
        pending_path = self.model_path.with_suffix(".safetensors.part")
        pending_path.write_bytes(b"partial")
        with patch.object(download.subprocess, "run", side_effect=subprocess.CalledProcessError(28, "curl")):
            with self.assertRaises(subprocess.CalledProcessError):
                download.install_model(self.models_directory, self.specification)
        self.assertEqual(pending_path.read_bytes(), b"partial")
        self.assertFalse(self.model_path.exists())

    def test_refuses_a_path_outside_the_models_directory(self):
        self.specification["path"] = "../outside.safetensors"
        with self.assertRaises(ValueError):
            download.install_model(self.models_directory, self.specification)

    def test_environment_file_is_read_without_executing_commands(self):
        configuration_file = self.models_directory / ".env"
        configuration_file.write_text("COMFY_MODELS_DIR='./custom models'\nUNUSED=$(touch should-not-exist)\n")
        configuration = download.read_environment(configuration_file)
        self.assertEqual(configuration["COMFY_MODELS_DIR"], "./custom models")
        self.assertEqual(configuration["UNUSED"], "$(touch should-not-exist)")


if __name__ == "__main__":
    unittest.main()
