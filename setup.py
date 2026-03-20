from pathlib import Path
from setuptools import setup, find_packages

HERE = Path(__file__).parent
long_description = (HERE / "README.md").read_text(encoding="utf-8")

setup(
    name="ckanext-openapi-view",
    version="0.1.0",
    description=(
        "CKAN extension providing server-side OpenAPI 3.1 spec generation "
        "for DataStore resources with typed schemas, caching, and DCAT 3 integration"
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/gtxizang/ckanext-openapi-view",
    license="MIT",
    python_requires=">=3.8",
    packages=find_packages(include=["ckanext", "ckanext.*"]),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        "ckan>=2.10",
        "dogpile.cache>=1.0",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Framework :: CKAN",
    ],
    entry_points={
        "ckan.plugins": [
            "openapi_view = ckanext.openapi_view.plugin:OpenApiViewPlugin",
        ],
    },
)
