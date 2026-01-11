"""Tests for the main module."""

from unittest.mock import patch

from src.main import main


class TestSampleData:
    """Tests demonstrating fixture usage."""

    def test_sample_data_has_key(self, sample_data: dict) -> None:
        """Test that sample_data fixture has expected key."""
        assert "key" in sample_data
        assert sample_data["key"] == "value"

    def test_sample_data_has_number(self, sample_data: dict) -> None:
        """Test that sample_data fixture has expected number."""
        assert sample_data["number"] == 42


class TestMain:
    """Tests for the main function."""

    @patch("src.main.cli_main")
    def test_main_calls_cli(self, mock_cli_main) -> None:
        """Test that main calls the CLI main function."""
        main()
        mock_cli_main.assert_called_once()
