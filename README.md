# pipeline-patterns

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Compose processing steps into typed pipelines with retry, fallback, abort, and a full execution trace — so data flow reads top-to-bottom instead of hiding inside nested callbacks.

## 🚀 Overview

Every ETL job, request handler, and batch process is secretly the same shape: run steps in order, handle one failing, sometimes stop early. `pipeline-patterns` makes that shape explicit. Stages are plain functions or `StageResult` emitters, failures wrap their original exception with the stage name for precise logs, and every run returns a trace you can inspect in tests.

## ✨ Features

- **One-line stages:** `stage("double", lambda n: n * 2)`
- **Full run trace:** each stage's outcome recorded as frozen `StageResult` (value + metadata + aborted flag)
- **Typed failure wrapping:** `StageFailedError` carries `.stage` and `.cause`
- **Cooperative abort:** raising `PipelineAbortedError` stops remaining stages cleanly
- **RetryStage:** bounded retries for transient failures; aborts pass through untouched
- **FallbackStage:** default value on failure; aborts still respected
- **Duplicate-name guard:** misconfigured pipelines fail at construction
- **Zero dependencies**

## 🚧 Structure

```
pipeline-patterns/
├── src/pipeline_patterns/
│   ├── __init__.py
│   └── core.py
├── tests/
│   └── test_core.py
├── README.md
└── pyproject.toml
```

## 📦 Installation

### For Development

```bash
git clone https://github.com/supremeloki/pipeline-patterns.git
cd pipeline-patterns
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

## 📋 Requirements

- Python 3.11+
- No runtime dependencies

## 🏃 Quick Start

```python
from pipeline_patterns import Pipeline, RetryStage, FallbackStage, stage

pipe = Pipeline([
    stage("parse", lambda raw: int(raw)),
    RetryStage(stage("fetch", flaky_fetch), attempts=3),
    FallbackStage(stage("enrich", risky_enrich), fallback_value={}),
])

trace = pipe.run("42")
print(pipe.final_value("42"))
```

### Cooperative abort

```python
from pipeline_patterns import PipelineAbortedError

def guard(record):
    if not record.get("id"):
        raise PipelineAbortedError()
    return record

pipe = Pipeline([stage("guard", guard), stage("process", work)])
```

## 🔧 Error Handling

```text
PipelineError
├── StageFailedError        # .stage name + original exception as .cause
└── PipelineAbortedError    # intentional early stop
```

## 🧪 Testing

```bash
pytest tests/ -v
```

## 📝 Code Quality

- Full type hints (`X | None` style), generics on `StageResult[T]`
- Zero comments — names carry the meaning
- `ruff` clean

## 📄 License

MIT — see [LICENSE](LICENSE).

## 👤 Author

**Kooroush Masoumi**

---

⭐ Star this repo if you find it useful!
