# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
import os
import sys

sys.path.insert(0, os.path.abspath("../src/"))

project = "FinTwit Bot"
copyright = "2023, Stephan Akkerman"
author = "Stephan Akkerman"
release = "1.1"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autosummary",
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.todo",
    "sphinx_automodapi.automodapi",
    "sphinx.ext.graphviz",
    "sphinx.ext.napoleon",
    "sphinx.ext.githubpages",
    "sphinx_autodoc_typehints",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

autosummary_generate = True


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "pydata_sphinx_theme"
html_static_path = ["_static"]

autodoc_mock_imports = ["torch", "transformers"]


def skip_member(app, what, name, obj, skip, options):
    # Ignore all setup methods
    if name == "setup":
        return True
    return skip


def setup(app):
    app.connect("autodoc-skip-member", skip_member)


# Commands:
# set SPHINX_APIDOC_OPTIONS=members,show-inheritance
# sphinx-apidoc -o . ../src/

# make clean html
# make html

# https://github.com/unit8co/darts/blob/master/docs/source/conf.py
# https://unit8co.github.io/darts/index.html
