import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pysignalclirestapi",
    version="0.2",
    author="Bernhard B.",
    author_email="bernhard@liftingcoder.com",
    description="Small python library for the Signal Cli REST API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bbernhard/pysignalclirestapi",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.0',
)
