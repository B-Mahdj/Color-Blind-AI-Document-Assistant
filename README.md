# Color-Blind Document Assistant

A document assistant for readers with **protanopia**, built for the OpenAI DevDay Community Hackathon in Paris.

The repository has two areas:

| Folder | Contents | Status |
| --- | --- | --- |
| [cli/](cli/README.md) | Python application, tests, fixtures, stress-document generator, configuration template, architecture and QA records. | Implemented and tested. |
| [skill/](skill/README.md) | Migration plan and workspace for the upcoming instructions-and-references skill. | Planned; no runnable skill yet. |

See [CLI setup and usage](cli/README.md), the [architecture](cli/ARCHITECTURE.md), or the [skill migration plan](skill/PROJECT_PLAN.md).

The local `.env` and generated outputs now live under `cli/` and remain ignored by Git. The development virtual environment stays in the repository's `.venv/` directory. The shared Git settings and MIT [license](LICENSE) remain at the root.
