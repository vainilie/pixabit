from setuptools import setup, find_packages

setup(
    name="pixabit",  
    version="1.0.0",
    description="A CLI app for Habitica with task and challenge management features.",
    author="vainilie",
    url="https://github.com/vainilie/pixabit",  # Replace with your repository URL
    packages=find_packages(),  # Automatically discovers all packages and subpackages
    install_requires=[
        # Dependencies from requirements.txt
        "requests",
        "rich",
    ],
    entry_points={
        "console_scripts": [
            "habitica-cli=project_name.main:main",  # Entry point for CLI
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",  # Specify minimum Python version
)
