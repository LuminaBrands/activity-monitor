from setuptools import setup, find_packages

setup(
    name="activity-monitor",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "flask>=3.0.0",
        "flask-socketio>=5.3.0",
        "pynput>=1.7.6",
        "mss>=9.0.0",
        "Pillow>=10.0.0",
        "psutil>=5.9.0",
        "anthropic>=0.40.0",
        "sqlalchemy>=2.0.0",
        "pyyaml>=6.0.0",
        "apscheduler>=3.10.0",
        "click>=8.1.0",
    ],
    entry_points={
        "console_scripts": [
            "activity-monitor=main:cli",
        ],
    },
)
