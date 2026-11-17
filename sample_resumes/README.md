# Sample resumes (synthetic)

All 12 resumes are **fictional**: invented people, companies, `@example.com` e-mail addresses
and made-up phone numbers. They're for testing and demonstration only.

Regenerate them with:

```bat
cd backend
python scripts\generate_sample_resumes.py
```

| # | File | Profile | What it tests |
|---|---|---|---|
| 1 | `01_arjun_mehta_python_backend.pdf` | Senior Python backend (Django, FastAPI, AWS) | 3 jobs, "Jan 2022 - Present" dates, LinkedIn link |
| 2 | `02_priya_nair_python_fastapi.docx` | Python developer (FastAPI, SQL) | `03/2023` dates on their own line, Word bullet lists |
| 3 | `03_karthik_iyer_java.pdf` | Java / Spring Boot developer | Java vs JavaScript, "Software Engineer - Java" title |
| 4 | `04_sneha_kulkarni_data_scientist.docx` | Data scientist (Python, ML, NLP) | Two degrees (M.Sc + B.Sc), two certifications |
| 5 | `05_vikram_singh_flask_backend.pdf` | Flask backend developer | **Overlapping** freelance job (merged, not double counted) |
| 6 | `06_ananya_reddy_fullstack.docx` | Full-stack (React, Node.js, MongoDB) | **Two-column table** layout, internship, project |
| 7 | `07_rohan_gupta_fresher.pdf` | Fresher with Python/ML projects | Fresher detection, internship section, projects |
| 8 | `08_meera_joshi_dotnet_sql.docx` | .NET / SQL Server engineer | **Name in Word page header**, year-only dates, US phone format |
| 9 | `09_aditya_rao_ml_engineer.pdf` | ML engineer (PyTorch, Sentence Transformers) | GitHub link not counted as a skill |
| 10 | `10_fatima_sheikh_embedded.docx` | Embedded systems (C, C++, RTOS) | **Unrelated** profile; C vs C++ |
| 11 | `11_neha_patil_no_contact.pdf` | Software developer | **No email/phone**, no dates, stated "4 years of experience" |
| 12 | `12_sanjay_verma_data_analyst.docx` | Data analyst (SQL, Power BI) | ALL-CAPS name and headings, "January 2023" dates |

Expected parsing results are written out in `backend/tests/test_sample_resumes.py`.
