"""
Generate the synthetic sample resumes in <repo>/sample_resumes/.

    cd backend
    python scripts/generate_sample_resumes.py

All people, companies, e-mail addresses (example.com) and phone numbers are
fictional. The resumes deliberately vary in layout and formatting so the
parser is tested on realistic differences: PDF vs DOCX, ALL-CAPS headings,
a two-column table layout, a name stored in the page header, four different
date formats, overlapping jobs, a fresher, and a resume without contact details.

Item format inside a section:  ("p", text) paragraph | ("h", text) entry heading | ("b", text) bullet
"""
import sys
from pathlib import Path

import docx
import pymupdf
from docx.shared import Pt

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "sample_resumes"

RESUMES = [
    {
        "file": "01_arjun_mehta_python_backend.pdf",
        "name": "Arjun Mehta",
        "headline": "Senior Python Backend Developer",
        "contact": ["arjun.mehta@example.com", "+91 98450 12345", "Bengaluru, India", "linkedin.com/in/arjun-mehta-demo"],
        "sections": [
            ("Professional Summary", [("p", "Backend engineer with 8+ years of experience designing scalable Python services, REST APIs and cloud deployments.")]),
            ("Technical Skills", [
                ("p", "Languages: Python, SQL"),
                ("p", "Frameworks: Django, FastAPI, Celery"),
                ("p", "Data & Cloud: PostgreSQL, Redis, Docker, AWS, Linux, Git"),
            ]),
            ("Work Experience", [
                ("h", "Senior Backend Engineer | CloudNova Technologies | Jan 2022 - Present"),
                ("b", "Designed REST APIs with FastAPI and PostgreSQL serving 2M requests per day."),
                ("b", "Containerised services with Docker and deployed them on AWS ECS."),
                ("h", "Backend Developer | Finlytics Pvt Ltd | Jul 2019 - Dec 2021"),
                ("b", "Built payment reconciliation services with Django REST Framework, Celery and Redis."),
                ("h", "Junior Python Developer | ByteForge Solutions | Jun 2018 - Jun 2019"),
                ("b", "Wrote Python automation scripts and SQL reports."),
            ]),
            ("Education", [("p", "B.Tech in Computer Science and Engineering, Deccan Institute of Technology, 2014 - 2018, CGPA 8.4/10")]),
            ("Certifications", [("b", "AWS Certified Developer - Associate")]),
        ],
    },
    {
        "file": "02_priya_nair_python_fastapi.docx",
        "name": "Priya Nair",
        "headline": "Python Developer",
        "contact": ["priya.nair@example.com", "+91-99000-22334", "Kochi, Kerala"],
        "sections": [
            ("Summary", [("p", "Python developer with 3 years of experience building FastAPI microservices backed by SQL databases.")]),
            ("Skills", [("p", "Python, FastAPI, SQL, PostgreSQL, SQLAlchemy, Pytest, Git, REST APIs")]),
            ("Experience", [
                ("h", "Python Developer, DataWeave Analytics"),
                ("p", "03/2023 - Present"),
                ("b", "Developed RESTful APIs in FastAPI with PostgreSQL and SQLAlchemy."),
                ("b", "Raised unit-test coverage to 90% using Pytest."),
                ("h", "Associate Software Engineer, Infobyte Systems"),
                ("p", "08/2022 - 02/2023"),
                ("b", "Maintained SQL stored procedures and Python ETL jobs."),
            ]),
            ("Education", [("p", "Bachelor of Science in Computer Science"), ("p", "Western Coast College, 2019 - 2022")]),
        ],
    },
    {
        "file": "03_karthik_iyer_java.pdf",
        "name": "Karthik Iyer",
        "headline": "Java Developer",
        "contact": ["karthik.iyer@example.com", "+91 91234 56789", "Chennai"],
        "sections": [
            ("Profile", [("p", "Java developer specialising in Spring Boot microservices. Basic knowledge of JavaScript for internal dashboards.")]),
            ("Technical Skills", [("p", "Java, Spring Boot, Hibernate, MySQL, Microservices, JUnit, Jenkins, Git, JavaScript")]),
            ("Professional Experience", [
                ("h", "Software Engineer - Java | Orion Softech | June 2021 - Present"),
                ("b", "Built order-management microservices using Spring Boot, Hibernate and MySQL."),
                ("b", "Set up CI pipelines in Jenkins with JUnit test gates."),
                ("h", "Trainee Engineer | Orion Softech | January 2021 - May 2021"),
                ("b", "Completed Java and Spring training; fixed production defects."),
            ]),
            ("Education", [("p", "B.E. in Information Technology, Coromandel Engineering College, 2016 - 2020")]),
            ("Certifications", [("b", "Oracle Certified Professional: Java SE 11 Developer")]),
        ],
    },
    {
        "file": "04_sneha_kulkarni_data_scientist.docx",
        "name": "Sneha Kulkarni",
        "headline": "Data Scientist",
        "contact": ["sneha.kulkarni@example.com", "+91 98220 44556", "Pune"],
        "sections": [
            ("Summary", [("p", "Data scientist applying machine learning and NLP to retail and marketing problems.")]),
            ("Technical Skills", [
                ("p", "Python, SQL, Machine Learning, Deep Learning, NLP, Statistics"),
                ("p", "Scikit-learn, TensorFlow, Pandas, NumPy, Tableau"),
            ]),
            ("Work Experience", [
                ("h", "Data Scientist, InsightLoop Analytics"),
                ("p", "Apr 2022 - Present"),
                ("b", "Built churn-prediction models with scikit-learn and TensorFlow (AUC 0.91)."),
                ("b", "Created NLP pipelines to classify 50k customer reviews per month."),
                ("h", "Data Analyst, RetailMetrics"),
                ("p", "Jul 2020 - Mar 2022"),
                ("b", "Automated SQL and Pandas reporting; built Tableau dashboards."),
            ]),
            ("Education", [
                ("p", "M.Sc in Data Science, Sahyadri University, 2018 - 2020"),
                ("p", "B.Sc in Statistics, Sahyadri University, 2015 - 2018"),
            ]),
            ("Certifications", [("b", "TensorFlow Developer Certificate"), ("b", "Google Data Analytics Professional Certificate")]),
        ],
    },
    {
        "file": "05_vikram_singh_flask_backend.pdf",
        "name": "Vikram Singh",
        "headline": "Backend Developer (Flask)",
        "contact": ["vikram.singh@example.com", "+91 97111 23456", "New Delhi"],
        "sections": [
            ("Skills", [("p", "Python, Flask, MySQL, REST APIs, Docker, Redis, Git, Linux")]),
            ("Experience", [
                ("h", "Backend Developer | ShopSphere | Mar 2024 - Present"),
                ("b", "Building Flask REST APIs for the e-commerce checkout platform."),
                ("h", "Freelance Python Developer (part-time) | Self-employed | Jun 2022 - Dec 2022"),
                ("b", "Delivered small Flask and MySQL projects for local businesses."),
                ("h", "Backend Developer | Quantra Labs | Feb 2021 - Jan 2024"),
                ("b", "Developed Flask services with MySQL and Redis caching, deployed with Docker."),
            ]),
            ("Education", [("p", "BCA, Rajdhani College of Computer Applications, 2017 - 2020")]),
        ],
    },
    {
        "file": "06_ananya_reddy_fullstack.docx",
        "layout": "table",
        "name": "Ananya Reddy",
        "headline": "Full Stack Developer",
        "contact": ["ananya.reddy@example.com", "+91 90000 11223", "Hyderabad"],
        "left_sections": [
            ("Skills", [("p", "JavaScript, TypeScript, React, Node.js, Express.js, MongoDB, HTML, CSS, Tailwind CSS, Git")]),
            ("Education", [("p", "B.Tech in Computer Science, Golconda Institute of Technology, 2019 - 2023")]),
        ],
        "sections": [
            ("Summary", [("p", "Full stack JavaScript developer building responsive web applications with React and Node.js.")]),
            ("Experience", [
                ("h", "Full Stack Developer at PixelCraft Studios"),
                ("p", "Sep 2023 - Present"),
                ("b", "Built React and TypeScript dashboards with an Express.js and MongoDB backend."),
                ("h", "Frontend Developer Intern at WebNest"),
                ("p", "Jan 2023 - Jun 2023"),
                ("b", "Converted Figma designs into React components with Tailwind CSS."),
            ]),
            ("Projects", [
                ("h", "Event Booking Platform"),
                ("b", "MERN application with JWT authentication and Stripe test payments (React, Node.js, MongoDB)."),
            ]),
        ],
    },
    {
        "file": "07_rohan_gupta_fresher.pdf",
        "name": "Rohan Gupta",
        "headline": "Recent Graduate - Python & Machine Learning",
        "contact": ["rohan.gupta@example.com", "9876501234", "Pune"],
        "sections": [
            ("Career Objective", [("p", "Recent graduate seeking an entry-level Python developer role where I can apply my machine learning project experience.")]),
            ("Education", [
                ("p", "B.Tech in Computer Engineering, Indrayani Institute of Engineering, 2021 - 2025, CGPA 8.9/10"),
                ("p", "Class XII (Higher Secondary), Pune Public School, 2021"),
            ]),
            ("Internships", [
                ("h", "Machine Learning Intern | Analytica AI | May 2024 - Oct 2024"),
                ("b", "Cleaned datasets with Pandas and trained scikit-learn classifiers."),
            ]),
            ("Academic Projects", [
                ("h", "Resume Screening Tool"),
                ("b", "Python and Flask web app that ranks resumes using TF-IDF and scikit-learn."),
                ("h", "Weather Dashboard"),
                ("b", "Fetched data from public REST APIs and visualised trends with Pandas and Matplotlib."),
            ]),
            ("Skills", [("p", "Python, SQL, Flask, Pandas, Scikit-learn, Git, Data Structures, OOP")]),
        ],
    },
    {
        "file": "08_meera_joshi_dotnet_sql.docx",
        "name_in_header": True,
        "name": "Meera Joshi",
        "headline": "Software Engineer",
        "contact": ["meera.joshi@example.com", "+1 (415) 555-0142", "Remote"],
        "sections": [
            ("Summary", [("p", "Software engineer building secure REST APIs on .NET and SQL Server for fintech clients.")]),
            ("Technical Skills", [("p", "C#, ASP.NET Core, SQL, SQL Server, REST APIs, Azure, Git, Agile")]),
            ("Work Experience", [
                ("h", "Software Engineer, LedgerLine Systems, 2021 - Present"),
                ("b", "Designed RESTful APIs with ASP.NET Core and optimised T-SQL queries."),
                ("h", "Junior Developer, CoinTrack Solutions, 2019 - 2021"),
                ("b", "Maintained C# services and SQL reporting jobs on Azure."),
            ]),
            ("Education", [("p", "Bachelor of Engineering (B.E.) in Computer Engineering, Western Plateau University, 2015 - 2019")]),
        ],
    },
    {
        "file": "09_aditya_rao_ml_engineer.pdf",
        "name": "Aditya Rao",
        "headline": "Machine Learning Engineer",
        "contact": ["aditya.rao@example.com", "+91 99860 77889", "Bengaluru", "github.com/aditya-rao-demo"],
        "sections": [
            ("Summary", [("p", "ML engineer deploying NLP and deep learning models to production with strong MLOps practices.")]),
            ("Technical Skills", [("p", "Python, PyTorch, TensorFlow, NLP, Sentence Transformers, Hugging Face, Docker, Kubernetes, AWS, MLflow, FastAPI")]),
            ("Work Experience", [
                ("h", "Machine Learning Engineer | NeuralNest AI | Aug 2021 - Present"),
                ("b", "Built semantic search with Sentence Transformers and served it via FastAPI on Kubernetes."),
                ("b", "Tracked experiments and model versions in MLflow."),
                ("h", "Research Assistant (NLP) | National Language Research Lab | Jan 2020 - Jul 2021"),
                ("b", "Fine-tuned PyTorch transformer models for text classification."),
            ]),
            ("Education", [
                ("p", "M.Tech in Artificial Intelligence, Kaveri Institute of Science, 2018 - 2020"),
                ("p", "B.Tech in Electronics and Communication, Kaveri Institute of Science, 2014 - 2018"),
            ]),
            ("Certifications", [("b", "Deep Learning Specialization (Coursera)")]),
        ],
    },
    {
        "file": "10_fatima_sheikh_embedded.docx",
        "name": "Fatima Sheikh",
        "headline": "Embedded Systems Engineer",
        "contact": ["fatima.sheikh@example.com", "+91 93222 98765", "Ahmedabad"],
        "sections": [
            ("Summary", [("p", "Embedded engineer developing firmware for automotive control units.")]),
            ("Technical Skills", [("p", "Embedded C, C, C++, RTOS, Arduino, Raspberry Pi, MATLAB, Verilog")]),
            ("Work Experience", [
                ("h", "Embedded Systems Engineer | VoltEdge Automotive | Oct 2020 - Present"),
                ("b", "Wrote Embedded C firmware on FreeRTOS for battery-management systems."),
                ("b", "Validated control algorithms in MATLAB before deployment."),
            ]),
            ("Education", [("p", "B.E. in Electronics and Communication, Sabarmati Engineering College, 2016 - 2020")]),
        ],
    },
    {
        "file": "11_neha_patil_no_contact.pdf",
        "name": "Neha Patil",
        "headline": "Software Developer",
        "contact": [],
        "sections": [
            ("Summary", [("p", "Software developer with 4 years of experience in Python and SQL, building internal tools for retail operations.")]),
            ("Skills", [("p", "Python, SQL, Django, Git")]),
            ("Experience", [
                ("h", "Software Developer, Nimbus Retail Tech"),
                ("b", "Built Django admin tools and SQL reports for store operations."),
            ]),
            ("Education", [("p", "Bachelor of Computer Applications (BCA), Godavari College")]),
        ],
    },
    {
        "file": "12_sanjay_verma_data_analyst.docx",
        "caps": True,
        "name": "Sanjay Verma",
        "headline": "Data Analyst",
        "contact": ["sanjay.verma@example.com", "+91 98100 65432", "Jaipur"],
        "sections": [
            ("Summary", [("p", "Data analyst turning sales data into dashboards and insights for business teams.")]),
            ("Skills", [("p", "SQL, Excel, Power BI, Tableau, Python, Pandas, Statistics")]),
            ("Experience", [
                ("h", "Data Analyst | BrightCart Retail | January 2023 - Present"),
                ("b", "Built Power BI dashboards tracking weekly sales for 120 stores."),
                ("b", "Wrote SQL queries and Pandas scripts to clean point-of-sale data."),
            ]),
            ("Education", [("p", "B.Com, Aravalli University, 2018 - 2021")]),
            ("Certifications", [("b", "Microsoft Certified: Power BI Data Analyst Associate")]),
        ],
    },
]


# --- HTML -> PDF (PyMuPDF Story) ---------------------------------------------------------------
CSS = """
* { font-family: sans-serif; }
h1 { font-size: 20px; margin: 0; color: #0b1b3f; }
h2 { font-size: 13px; margin: 12px 0 4px 0; color: #1d3a78; border-bottom: 1px solid #ccc; }
p, li { font-size: 10.5px; margin: 2px 0; }
.headline { font-size: 12px; color: #444; }
.entry { font-weight: bold; margin-top: 6px; }
"""


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _items_to_html(items) -> str:
    html, in_list = [], False
    for kind, text in items:
        if kind == "b" and not in_list:
            html.append("<ul>")
            in_list = True
        if kind != "b" and in_list:
            html.append("</ul>")
            in_list = False
        if kind == "b":
            html.append(f"<li>{_escape(text)}</li>")
        elif kind == "h":
            html.append(f'<p class="entry">{_escape(text)}</p>')
        else:
            html.append(f"<p>{_escape(text)}</p>")
    if in_list:
        html.append("</ul>")
    return "".join(html)


def write_pdf(resume: dict, path: Path) -> None:
    parts = [f"<h1>{_escape(resume['name'])}</h1>", f'<p class="headline">{_escape(resume["headline"])}</p>']
    if resume["contact"]:
        parts.append(f"<p>{_escape(' | '.join(resume['contact']))}</p>")
    for heading, items in resume["sections"]:
        parts.append(f"<h2>{_escape(heading.upper() if resume.get('caps') else heading)}</h2>")
        parts.append(_items_to_html(items))

    story = pymupdf.Story(html="".join(parts), user_css=CSS)
    writer = pymupdf.DocumentWriter(str(path))
    mediabox = pymupdf.paper_rect("a4")
    content_area = mediabox + (50, 50, -50, -50)
    more = True
    while more:
        device = writer.begin_page(mediabox)
        more, _ = story.place(content_area)
        story.draw(device)
        writer.end_page()
    writer.close()


# --- DOCX (python-docx) -------------------------------------------------------------------------
def _add_items(container, items) -> None:
    for kind, text in items:
        if kind == "b":
            container.add_paragraph(text, style="List Bullet")
        elif kind == "h":
            container.add_paragraph().add_run(text).bold = True
        else:
            container.add_paragraph(text)


def _add_heading(container, text: str, caps: bool) -> None:
    run = container.add_paragraph().add_run(text.upper() if caps else text)
    run.bold, run.font.size = True, Pt(13)


def write_docx(resume: dict, path: Path) -> None:
    document = docx.Document()
    caps = resume.get("caps", False)
    display_name = resume["name"].upper() if caps else resume["name"]

    if resume.get("name_in_header"):
        # Name and contacts live in the page header, as in many Word templates.
        header = document.sections[0].header
        header.paragraphs[0].text = display_name
        header.add_paragraph(" | ".join(resume["contact"]))
        document.add_paragraph(resume["headline"])
    elif resume.get("layout") == "table":
        # Two-column template: left column = contacts, skills, education; right = the rest.
        table = document.add_table(rows=1, cols=2)
        left, right = table.rows[0].cells
        left.paragraphs[0].add_run(display_name).bold = True
        left.add_paragraph(resume["headline"])
        for line in resume["contact"]:
            left.add_paragraph(line)
        for heading, items in resume["left_sections"]:
            _add_heading(left, heading, caps)
            _add_items(left, items)
        right.paragraphs[0].text = ""
        for heading, items in resume["sections"]:
            _add_heading(right, heading, caps)
            _add_items(right, items)
        document.save(path)
        return
    else:
        title = document.add_paragraph()
        title_run = title.add_run(display_name)
        title_run.bold, title_run.font.size = True, Pt(20)
        document.add_paragraph(resume["headline"])
        if resume["contact"]:
            document.add_paragraph(" | ".join(resume["contact"]))

    for heading, items in resume["sections"]:
        _add_heading(document, heading, caps)
        _add_items(document, items)
    document.save(path)


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for resume in RESUMES:
        path = OUTPUT_DIR / resume["file"]
        (write_pdf if path.suffix == ".pdf" else write_docx)(resume, path)
        print(f"  wrote {path.relative_to(OUTPUT_DIR.parent)}")
    print(f"{len(RESUMES)} sample resumes generated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
