# NutriScan AI: Edge-Native Dietary Auditor & Nutritional Screener

An edge-native, privacy-preserving multimodal dietary classifier and macro auditor designed to run locally on Apple Silicon and modern edge hardware without external cloud API dependencies.

---

## 🛠️ Updated Tech Stack & Dependencies

The project relies on a lightweight, offline-first stack combining deterministic rule checking, fast local ONNX vector embeddings, and an SLM (Small Language Model) fallback.

### Python Environment
* **Python**: `3.10` - `3.12`

### Core Libraries & Packages

| Library | Version / Spec | Purpose in NutriScan |
| :--- | :--- | :--- |
| **`streamlit`** | `>=1.35.0` | Interactive web dashboard, real-time plate logging, and macro visualizer. |
| **`fastembed`** | `>=0.3.0` | Ultra-fast ONNX runtime semantic embeddings (`bge-small-en-v1.5`) for dietary cosine matching without PyTorch overhead. |
| **`ollama`** | `>=0.2.0` | Local client interface to execute `qwen2.5:1.5b` for 2-step ingredient decomposition and edge reasoning. |
| **`pandas`** | `>=2.2.0` | Dataset manipulation, ingestion, and preprocessing of the `MM-Food-100K` benchmark. |
| **`numpy`** | `>=1.26.0` | Fast vector and array math operations for semantic similarity thresholds. |
| **`plotly`** | `>=5.20.0` | Interactive client-side macronutrient split donut charts and daily intake visualizations. |
| **`pillow`** (`PIL`) | `>=10.0.0` | Image ingestion, preprocessing, and rendering for multimodal plate auditing. |
| **`sqlite3`** | *Standard Library* | Zero-RAM disk-based B-Tree indexing engine querying 100,000 recipes in `< 1ms`. |
| **`requests`** | `>=2.31.0` | Optional upstream fallback client to seed and populate local grocery caches. |

---

## 📦 Installation & Setup

### 1. Clone & Set Up Virtual Environment

```bash
git clone <repo-url>
cd Calorie-AI
python3 -m venv cal
source cal/bin/activate