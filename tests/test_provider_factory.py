import unittest

import context  # noqa: F401

from llm.factory import create_provider
from llm.ollama_provider import OllamaNegotiationProvider
from llm.provider import MockNegotiationProvider


class ProviderFactoryTest(unittest.TestCase):
    def test_create_mock_provider(self) -> None:
        provider = create_provider("mock")

        self.assertIsInstance(provider, MockNegotiationProvider)

    def test_create_ollama_provider(self) -> None:
        provider = create_provider(
            "ollama",
            model_name="fake-model",
            base_url="http://localhost:11434",
            temperature=0.0,
            timeout_seconds=1.0,
        )

        self.assertIsInstance(provider, OllamaNegotiationProvider)

    def test_unknown_provider_kind_raises(self) -> None:
        with self.assertRaises(ValueError):
            create_provider("unknown")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
