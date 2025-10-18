# CS-499 Computer Science Capstone — Mubeen Ahmed Khan

### Bachelor of Science in Computer Science  
**Southern New Hampshire University (SNHU)**  
**Instructor:** Dr. Pravin Bhandari  
**Final Submission:** 2025  

---

## Overview

This repository contains my **Computer Science Capstone ePortfolio**, completed as part of the Bachelor of Science in Computer Science program at Southern New Hampshire University.  
The project integrates and demonstrates my mastery of the five program outcomes in software engineering, algorithmic design, database management, communication, and security.

The central artifact for this capstone is the **Animal Shelter CRUD Module**, developed and enhanced through iterative milestones to demonstrate advanced design, performance, and security principles.  
It connects to a MongoDB database and powers a Dash/Jupyter-based analytics dashboard for managing and visualizing animal shelter data.

---

## Repository Contents

| Folder | Description |
|--------|--------------|
| `/artifacts` | Contains enhanced artifacts and narratives for software design, algorithms, and databases. |
| `/code_review` | Code review materials, including a professional walkthrough video. |
| `/dashboard` | The Dash and Jupyter Notebook dashboard that visualizes MongoDB data. |
| `/originals` | Original unenhanced artifacts for comparison. |
| `dashboard/tests` | Unit and integration tests for CRUD functions, caching, and database operations. |

---

## Project Highlights

### Software Design and Engineering
Enhanced `animal_shelter.py` with:
- Structured logging and environment-based configuration.
- Type hints and modular documentation.
- Fast-fail connection validation and safe input handling.

### Algorithms and Data Structures
Optimized code performance by:
- Implementing in-memory caching and validation algorithms.
- Adding helper functions for data cleaning and efficient querying.
- Maintaining backward compatibility and clean code interfaces.

### Databases
Strengthened database reliability with:
- MongoDB `$jsonSchema` validation for structural integrity.
- Compound and geospatial indexing for query performance.
- Aggregation pipelines for server-side analytics.

---

## Technology Stack

- **Programming Language:** Python 3.10  
- **Database:** MongoDB  
- **Visualization:** Dash & Plotly  
- **Environment:** Jupyter Notebook  
- **Testing Framework:** PyTest  
- **Version Control:** Git & GitHub  
- **Recording Tools:** OBS Studio  

---

## Code Review

A comprehensive walkthrough of the artifact’s original design, issues identified, and enhancement plan can be viewed here:

**[Watch Code Review Video](https://youtu.be/ziDEvxnYvEU)**

---

## ePortfolio Website

The complete ePortfolio website, hosted via **GitHub Pages**, includes the professional self-assessment, narratives, and artifact links.

🔗 **View the Portfolio:** [https://mubeenkh4u.github.io/](https://mubeenkh4u.github.io/)

---

## Program Outcomes Demonstrated

1. **Collaboration and Decision-Making** – Applied documentation and testing in collaborative environments.  
2. **Professional Communication** – Delivered technical content clearly for varied audiences.  
3. **Algorithmic Design and Evaluation** – Implemented caching and efficient query solutions.  
4. **Innovative Computing Practices** – Used modern tools and frameworks to build maintainable systems.  
5. **Security Mindset** – Enforced validation, safe queries, and schema enforcement to protect data integrity.

---

## Pre-requisites

`pip install -r requirements.txt`

## How to Run the Dashboard

1. Clone this repository:
    `git clone https://github.com/mubeenkh4u/mubeenkh4u.github.io.git`
3. Ensure that you have MongoDB installed and setup.
4. Create a Database `aac` with collections `animals`.
5. Load your .env file (placed inside the dashboard folder).
    Sample .env (replace username with `aacuser` or your username and input your password - remove the tags):
    ```
        # Connection details (sample URL: mongodb://USER:PASSWORD@127.0.0.1:27017/aac?authSource=aac)
        MONGO_URI=mongodb://<username>:<password>@127.0.0.1:27017/aac?authSource=aac
        MONGO_DB=aac
        MONGO_COLL=animals
        # Optional features
        MONGO_APPLY_VALIDATOR=1
        LOG_LEVEL=INFO
6. Load the dataset from `aac_shelter_outcomes.csv` (provided in the `dashboard` folder).
7. Run Jupter Notebook.
8. Run `ProjectTwoDashboard.ipynb`.
9. Test everything runs without issues using `pytest -q` inside the dashboard folder to check if environment is funcitoning correctly.
10. For creating test entry, use the Cell in the Jupyter Notebook to run CRUD tests. 
11. Change optional features to your liking to enable/disable schema validation and log-level.