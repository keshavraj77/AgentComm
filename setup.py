from setuptools import setup, find_packages
from pathlib import Path

# Read requirements
requirements_path = Path(__file__).parent / "agentcomm" / "requirements.txt"
with open(requirements_path) as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

# Read README for long description
readme_path = Path(__file__).parent / "README.md"
long_description = ""
if readme_path.exists():
    with open(readme_path, encoding='utf-8') as f:
        long_description = f.read()

setup(
    name="agentcomm",
    version="0.1.0",
    description="AgentComm - A2A Client with Multi-LLM Integration",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Keshav",
    author_email="keshavrajwebd@gmail.com",
    url="https://github.com/keshavraj77/agentcomm",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'agentcomm': [
            'config/*.json',
            'ui/*.svg',
            'ui/*.png',
        ],
    },
    install_requires=requirements,
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "agentcomm=agentcomm.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    keywords="agent llm ai chatbot a2a",
)


