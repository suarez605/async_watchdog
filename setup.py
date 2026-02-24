# setup.py
from setuptools import setup, find_packages

setup(
    name="async_watchdog",
    version="0.1.0",
    author="Álvaro Suárez Lozano",
    author_email="…",
    description="Fast and simple async watchdog to monitor heartbeats in async applications.",
    packages=find_packages(),  # busca en el root
    python_requires=">=3.10",
    install_requires=[],
)
