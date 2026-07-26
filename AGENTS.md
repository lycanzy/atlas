# Repository Guidelines

## Project Structure & Module Organization

This repository centers on a Django 5.2 experiment tracking app in `experiment_app/`. The Django project package is `experiment_app/experiment_app/`, and the main app is `experiment_app/experiment_flow/`. Models, forms, views, admin registration, and context processors live there. Templates are under `experiment_app/experiment_flow/templates/experiment_flow/`; CSS/JS and vendored Bootstrap, Select2, jQuery, Cytoscape, and Bootstrap Icons assets are under `experiment_app/static/`. Django tests live in `experiment_app/experiment_flow/tests/`. Helper checks are in `scripts/`. `atlas-demo-site/` is a separate Vinext/Next demo site.


## Product context
This application tracks engineernig experiments.

- Group (AAA)
    - Project (AAA000)
        - Experiment (AAA000AA)
            -Steps (AAA000AA-AA)

This application preserves experimental tracebility and geneology.

### Engineering principles
- Inspect exisiting architecture before proposing changes
- Prefer small, reviewable patches
- Do not introduce a new dependency without explaining why
- Do not change database schemas without creating a migration
- Do not silently change exisiting API contracts
- Preserve backward compatibility unless the task explicitly permits breaking changes.
- Use existing repository conventions instead of introducing parallel patterns.

## Security & Configuration Tips

Do not commit local databases, secrets, virtual environments, or generated dependency folders. Keep team-scoped access control intact: normal users should only see their research group, while staff and superusers may access all groups. Update source assets in `experiment_app/static/`; treat `staticfiles/` as collected output.
