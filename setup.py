from setuptools import setup, find_packages

with open("agentcomm/requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="agentcomm",
    version="0.1.0",
    description="AgentComm - A2A Client with Base LLM Integration",
    author="AgentComm Team",
    packages=find_packages(),
    install_requires=requirements,
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "agentcomm=agentcomm.main:main",
        ],
    },
)


