---
name: viz-and-reporting
description: Visualization & Reporting
When to use:
  - Creating or modifying plots, dashboards, or tearsheets.
  - Preparing analysis artifacts for humans (notebooks, reports, dashboards).
---

Instructions for the skill go here. Provide relative paths to other resources in the skill directory as needed.

Goals:
- Keep analytical logic in Python, visuals reusable.
- Make it easy to switch or augment visualization technologies (Python now, Julia later).

Workflow:
1. Implement core analytics (metrics, aggregations) as pure Python functions that operate on dataframes/arrays.
2. For Python visualization:
   - Use the project’s standard libraries (e.g., Plotly, Matplotlib).
   - Keep plotting code separate from business logic.
3. When preparing data for Julia or other tools:
   - Export clean, documented Parquet/Arrow tables from the analysis layer.
   - Avoid tight coupling between visualization and the trading engine.
4. Prefer reusable components:
   - A generic performance tearsheet that can be reused for multiple strategies.
   - Parameterized dashboards that can be driven by different datasets.
5. Add tests for analytics functions that validate metric correctness on small, known datasets.