# Project Setup Guide

## 1. (Recommended) Create a Virtual Environment

```bash
python -m venv .venv
.\.venv\Scripts\activate
```

## 2. Install `uv` Tool

```bash
pip install uv
```

## 3. Install Project Dependencies

Make sure you are in the project root directory (where `pyproject.toml` and `uv.lock` are located):

```bash
uv pip install .
```

## 4. Verify Installation

```bash
uv pip list
```

---

For more details, please refer to the project documentation or contact the maintainer.