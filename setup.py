from setuptools import setup
from pathlib import Path

parent = Path(__file__).parent

description = (parent / "README.md").read_text()
requirements = (parent / "requirements.txt").read_text().splitlines()

setup(
    name="venai",
    version="1.28.3",
    author="Mert Sirakaya",
    author_email="contact@tomris.dev",
    maintainer="Mert Sirakaya",
    maintainer_email="contact@tomris.dev",
    description="VenusAI is a secure and extensible Agent framework built for modern AI applications.",
    packages=["venus", "venus.helpers", "venus.helpers.sandbox", "venus.models"],
    fullname="VenusAI",
    install_requires=requirements,
    long_description=description,
    long_description_content_type="text/markdown",
    url="https://github.com/VenusAgent/VenusAI",
    classifiers=[
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
    include_package_data=True,
    license="MIT",
    keywords="safety, ai, agent, llm, agentic ai, pydantic, pydantic-ai, self-healing, sandbox, ai agent",
    project_urls={
        "Documentation": "https://venai.tech/docs",
        "Source": "https://github.com/VenusAgent/VenusAI",
        "Tracker": "https://github.com/VenusAgent/VenusAI/issues",
    },
    entry_points={
        "console_scripts": [
            "venus=venus.__main__:main",
            "venai=venus.__main__:main",
        ],
    },
    
)