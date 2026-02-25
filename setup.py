# setup.py
from setuptools import setup, find_packages

setup(
    name="async_watchdog",
    version="0.1.0",
    author="Álvaro Suárez Lozano",
    author_email="alvaro@example.com",
    description=(
        "Fast and simple async watchdog to monitor heartbeats "
        "in async applications."
    ),
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[],
    project_urls={
        "Bug Tracker": (
            "https://github.com/alvarosuarez/async_watchdog/issues"
        ),
        "Security": (
            "https://github.com/alvarosuarez/"
            "async_watchdog/security/advisories"
        ),
    },
)
