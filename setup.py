from setuptools import setup, find_packages

setup(
    name="mixmate",
    version="1.0.0",
    description="AI驱动的自动视频剪辑系统 - 先理解素材，再操刀剪辑",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "opencv-python>=4.8.0",
        "numpy>=1.24.0",
        "librosa>=0.10.0",
        "scipy>=1.11.0",
        "flask>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "mixmate=mixmate.cli:main",
        ],
    },
)
