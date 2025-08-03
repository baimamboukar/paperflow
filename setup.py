"""
Paperflow Setup
Installation script for Paperflow academic paper website generator
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="paperflow",
    version="1.0.0",
    description="Generate beautiful academic paper websites with ease",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Paperflow Team",
    author_email="contact@paperflow.dev",
    url="https://github.com/paperflow/paperflow",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Education",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering",
        "Topic :: Text Processing :: Markup :: LaTeX",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
    ],
    python_requires=">=3.8",
    install_requires=[
        "Flask>=2.3.0",
        "Flask-CORS>=4.0.0", 
        "PyYAML>=6.0.0",
        "pathlib>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=23.0.0", 
            "flake8>=6.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "paperflow=launch:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.html", "*.css", "*.js", "*.yaml", "*.md"],
    },
    keywords="academic research paper website latex html generator",
    project_urls={
        "Bug Reports": "https://github.com/paperflow/paperflow/issues",
        "Source": "https://github.com/paperflow/paperflow",
        "Documentation": "https://paperflow.github.io/docs",
    },
)