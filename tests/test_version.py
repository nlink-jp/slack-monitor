"""The version the package reports matches the one it is installed as."""

from importlib.metadata import version

from slack_monitor import __version__


def test_version_matches_package_metadata() -> None:
    assert __version__ == version("slack-monitor")
