from setuptools import setup, find_packages

setup(
    name="nagatha_assistant",
    version="0.1.0",
    description="A personal AI assistant using OpenAI",
    author="AZcoigreach",
    author_email="azcoigreach@gmail.com",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
    install_requires=[
        "click",
        "python-dotenv",
        "openai",
        "textual",
        "rich",
        "SQLAlchemy",
        "alembic",
        "aiosqlite"
    ],
    entry_points={
        "console_scripts": [
            "nagatha=nagatha_assistant.cli:cli"
        ]
    },
    python_requires=">=3.11",
)