from setuptools import setup

version = "0.0.4"

setup(
    name="raffiot",
    packages=["raffiot"],
    version=version,
    license="Apache 2.0",
    description="Robust And Fast Functional IO Toolkit",
    author="chrilves",
    author_email="calves@crans.org",
    url="https://github.com/chrilves/raffiot.py",
    download_url=f"https://github.com/chrilves/raffiot.py/archive/v{version}.tar.gz",
    keywords=["IO", "MONAD", "FUNCTIONAL PROGRAMMING"],
    classifiers=[
        "Development Status :: 3 - Alpha",  # Chose either "3 - Alpha", "4 - Beta" or "5 - Production/Stable" as the current state of your package
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    install_requires=['typing-extensions']
)
