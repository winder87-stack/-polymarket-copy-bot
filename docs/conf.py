# -*- coding: utf-8 -*-
import datetime
import os
import sys

# Add project root to Python path
sys.path.insert(0, os.path.abspath(".."))

# Project information
project = "Polymarket Copy Trading Bot"
copyright = f"{datetime.datetime.now().year}, Contributors"
author = "Polymarket Bot Contributors"
release = "1.0.0"

# General configuration
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
    "sphinx.ext.intersphinx",
    "sphinx.ext.githubpages",
    "sphinx_autodoc_typehints",
    "sphinx_copybutton",
]

# Napoleon settings for Google-style docstrings
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = True

# Autodoc settings
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
    "show-inheritance": True,
    "inherited-members": True,
    "private-members": False,
}

autodoc_typehints = "description"
autodoc_typehints_description_target = "documented"
autodoc_mock_imports = ["web3", "py_clob_client", "telegram", "aiohttp"]

# Intersphinx mapping
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "web3": ("https://web3py.readthedocs.io/en/stable/", None),
}

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# HTML output options
html_theme = "furo"
html_title = "Polymarket Copy Bot API Documentation"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_js_files = ["custom.js"]
html_favicon = "_static/favicon.ico"
html_logo = "_static/logo.png"

# Theme options
html_theme_options = {
    "navigation_with_keys": True,
    "top_of_page_button": "edit",
    "sidebar_hide_name": False,
    "light_css_variables": {
        "color-brand-primary": "#2980b9",
        "color-brand-content": "#1f618d",
        "color-api-background": "#2c3e50",
        "color-api-name": "#3498db",
        "color-api-pre-name": "#2980b9",
    },
    "dark_css_variables": {
        "color-brand-primary": "#3498db",
        "color-brand-content": "#2980b9",
        "color-api-background": "#1a1a1a",
        "color-api-name": "#3498db",
        "color-api-pre-name": "#2980b9",
    },
}
