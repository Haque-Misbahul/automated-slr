# NLP-Based Automation of Systematic Literature Reviews (SLR)

This repository implements a **locally deployable automation framework** for conducting **Systematic Literature Reviews (SLRs)** in **Computer Science**, following the conceptual design presented in the Master’s thesis *“NLP-Based Automation of Systematic Literature Reviews in Computer Science”* (Chemnitz University of Technology, 2025).

The goal of this project is to automate both **phases** of the SLR process proposed by *Carrera-Rivera et al. (2022)*:

1. **Planning / Preparation Phase** → Automates the definition of PICOC elements, synonym generation, and multi-database search-string formulation.  
2. **Conducting Phase** → Automates literature retrieval, screening, extraction, and taxonomy generation.

All stages are implemented as modular Streamlit interfaces with backend agents driven by **Large Language Models (LLMs)** and **Sentence-BERT (SBERT)** for semantic filtering.

---

## 🚀 Key Features

| Phase | Step | Functionality |
|-------|------|----------------|
| **Planning** | Step 1: PICOC & Synonyms | Generate PICOC elements (Population, Intervention, Comparison, Outcome, Context) and facet-wise synonyms using an LLM. |
|  | Step 2: Search String Builder | Build structured, Boolean, database-specific search strings automatically. |
| **Conducting** | Step 3: Selection & Refinement | Perform screening, duplicate removal, and refinement of retrieved papers. |
|  | Step 4: Taxonomy Generation | Generate a hierarchical, interactive taxonomy of the selected literature. |

Each phase is fully interactive through the Streamlit UI and stores intermediate results (JSON) for reproducibility.

---

## 🧠 Core Technologies

| Category | Tools & Libraries |
|-----------|------------------|
| **Frontend** | [Streamlit](https://streamlit.io) for interactive multi-step UI |
| **LLM Interface** | OpenAI-compatible endpoint hosted on `https://kiste.informatik.tu-chemnitz.de/v1` |
| **Language Model** | `gpt-oss-120b` (local API endpoint) |
| **Semantic Similarity** | `sentence-transformers/all-MiniLM-L6-v2` via **SBERT** |
| **Environment** | Python 3.9 + virtualenv |
| **Data Handling** | `pandas`, `json`, `torch` |
| **Version Control** | Git / GitHub |

---

## ⚙️ Installation

### 1. Clone the repository
```bash
git clone https://github.com/Haque-Misbahul/automated-slr.git
cd automated-slr

2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # (Mac/Linux)
# or
.\.venv\Scripts\Activate.ps1   # (Windows)

3. Install dependencies
pip install -r requirements.txt

4. Configure environment variables

Create a file named .env or export the variables manually:

export KISTE_API_KEY="YOUR_API_KEY_HERE"
export OPENAI_BASE_URL="https://kiste.informatik.tu-chemnitz.de/v1"


(Replace the key with the one provided by your TU Chemnitz account.)

5. Launch the application
streamlit run slr/ui/app.py


Access the interface at http://localhost:8501.

🧩 Repository Structure
automated-slr/
│
├── slr/
│   ├── agents/                # Intelligent LLM-based task agents
│   │   ├── agent.py
│   │   └── ...
│   ├── llm/                   # Low-level API client wrapper
│   │   └── client.py
│   ├── ui/                    # Streamlit multi-step pages
│   │   ├── picoc_synonyms.py  # Step 1 – Define PICOC & Synonyms
│   │   ├── search_builder.py  # Step 2 – Query generation
│   │   ├── c02_screen_refine.py  # Step 3 – Screening/Refinement
│   │   └── taxonomy_generate.py  # Step 4 – Taxonomy output
│   ├── data/                  # Input datasets and outputs
│   └── utils/                 # Helper functions
│
├── requirements.txt
├── README.md
└── PROCESS_FLOW.md


# automated-slr implementation


cd automated-slr
source .venv/bin/activate
export KISTE_API_KEY="Wy5ybxmAB3Pc_XPhkWaJpT4rjUM8k4qcPFA4fzU3kW...."
streamlit run slr/ui/Picoc_Synonyms.py




Run/install/test Python code.

git add . && git commit -m "..." && git push
(venv can be active or not — doesn’t matter here.)

streamlit run slr/ui/picoc_synonyms.py

Base URL: https://kiste.informatik.tu-chemnitz.de/v1
API Key: Wy5ybxmAB3Pc_XPhkWaJpT4rjUM8k4qcPFA4fzU3kW...

please only use the glm-4.5-air model.
