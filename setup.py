"""Package configuration for Nagatha Assistant.

All runtime dependencies are listed in *requirements.txt* so that we maintain
a single authoritative source.  ``setup.py`` reads that file at build time and
uses it for *install_requires*.
"""

from pathlib import Path

from setuptools import find_packages, setup


def load_requirements() -> list[str]:
    req_path = Path(__file__).with_name("requirements.txt")
    with req_path.open() as fh:
        return [
            line.strip()
            for line in fh
            if line.strip() and not line.strip().startswith("#")
        ]


setup(
    name="nagatha_assistant",
    version="0.6.0",
    description="A personal AI assistant using OpenAI",
    author="AZcoigreach",
    author_email="azcoigreach@gmail.com",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
    install_requires=load_requirements(),
    entry_points={
        "console_scripts": [
            "nagatha=nagatha_assistant.cli:cli",
        ],
    },
    python_requires=">=3.11",
)