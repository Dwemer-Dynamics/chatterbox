import tempfile
import unittest
from pathlib import Path

from voice_management import delete_voice_artifacts, normalize_voice_id


class VoiceManagementTest(unittest.TestCase):
    def test_delete_removes_wav_and_conditionals(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "sample.wav").write_bytes(b"wav")
            (root / "sample.pt").write_bytes(b"pt")

            removed = delete_voice_artifacts(root, "sample.wav")

            self.assertEqual(removed, ["sample.wav", "sample.pt"])
            self.assertFalse((root / "sample.wav").exists())
            self.assertFalse((root / "sample.pt").exists())

    def test_rejects_path_traversal(self):
        for value in ("../sample", "folder/sample", "folder\\sample", ".hidden"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_voice_id(value)


if __name__ == "__main__":
    unittest.main()
