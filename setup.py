from setuptools import setup

version = "0.5.1"

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="raffiot",
    packages=["raffiot", "raffiot.untyped"],
    version=version,
    license="Apache 2.0",
    description="Robust And Fast Functional IO Toolkit",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="chrilves",
    author_email="calves@crans.org",
    url="https://github.com/chrilves/raffiot.py",
    download_url=f"https://github.com/chrilves/raffiot.py/archive/{version}.tar.gz",
    keywords=[
        "IO",
        "MONAD",
        "FUNCTIONAL PROGRAMMING",
        "RESULT",
        "RESOURCE MANAGEMENT",
        "RAILWAY",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",  # Chose either "3 - Alpha", "4 - Beta" or "5 - Production/Stable" as the current state of your package
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Operating System :: OS Independent",
    ],
    install_requires=["typing-extensions"],
    python_requires=">=3.7",
)
