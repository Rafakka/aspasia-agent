
# Aspásia

**A modular platform for research, knowledge organization, and content production, powered by specialized AI agents.**

Aspásia is an evolving platform designed to investigate topics, organize information into traceable knowledge, and transform research findings into different content formats.

Rather than relying on a single general-purpose agent, Aspásia follows a modular architecture in which specialized agents perform distinct responsibilities, coordinated through a central control layer and supervised by humans.

## Project Vision

Aspásia aims to establish a structured workflow between research and communication.

Its central idea is to separate two activities:

- **Research:** investigate a subject, discover sources, acquire documents, analyze evidence, identify contradictions, and produce research reports.
- **Content Production:** transform approved research into accessible and engaging content while preserving its factual foundations.

This separation allows research results to be reused across different content formats without repeating the entire investigation.

## Core Principles

- **Evidence-based research:** conclusions should be grounded in identifiable sources and supporting evidence.
- **Human-in-the-loop:** important research and editorial decisions remain subject to human review and approval.
- **Modularity:** research, acquisition, processing, and content production have independent responsibilities.
- **Traceability:** information should retain its relationship with the documents and sources from which it originated.
- **Reusability:** approved research reports can support multiple content artifacts.
- **Extensibility:** new providers, document processors, and specialized agents can be introduced without redesigning the entire platform.

## Architecture Overview

Aspásia is organized around two complementary architectural areas.

### Control Plane

Responsible for coordinating the platform's activities and managing interactions with users.

Its responsibilities include:

- Interpreting research requests.
- Managing investigation workflows.
- Coordinating specialized agents.
- Requesting user configuration and approval.
- Analyzing research results.
- Managing reports and content production.

LangGraph is used as an orchestration mechanism for agent workflows.

### Data Plane

Responsible for discovering, acquiring, processing, and organizing information.

Its responsibilities include:

- Source discovery.
- Source and resource registration.
- Document acquisition.
- File storage.
- Document processing.
- Evidence extraction and storage.

The Control Plane coordinates operations, while the Data Plane provides the information and processing capabilities required by those operations.

## Specialized Agents

### Research Agent

The Research Agent is responsible for investigating topics and producing structured research reports.

Its intended workflow includes:

1. Research planning.
2. Human approval of the research plan.
3. Source discovery.
4. Source selection.
5. Resource acquisition.
6. Document processing.
7. Evidence analysis.
8. Research report generation.
9. Human review and approval.

### Content Agent

The Content Agent is responsible for transforming approved research into communication artifacts.

Its planned capabilities include:

- Research report interpretation.
- Narrative and discourse strategy.
- Content structure design.
- Adaptation to different formats.
- Script generation.
- Editorial review.

The Content Agent is designed to use approved research as its informational foundation rather than conducting an independent investigation for every new content artifact.

## Research and Knowledge Model

Aspásia uses distinct concepts to represent the different stages of information processing.

| Concept | Responsibility |
|---|---|
| Investigation | Represents a research activity. |
| Source | Represents an informational origin. |
| Resource | Represents a digital document or object. |
| Evidence | Represents information extracted from a resource. |
| Research Report | Represents the consolidated result of an investigation. |
| Content Artifact | Represents content produced from a research report. |

This separation establishes the foundation for traceability, information reuse, and future persistence.

## Current MVP Scope

The initial MVP focuses on establishing the research workflow and its underlying data acquisition architecture.

Current capabilities include:

- Research planning with an LLM.
- Human approval and revision of research plans.
- Web search and source selection.
- HTML page acquisition and text extraction.
- Initial document detection and storage components.
- Local LLM integration through Ollama.
- LangGraph-based workflow orchestration.
- Automated tests for implemented components.

The document acquisition layer is being expanded to support different resource types. PDF acquisition and storage are part of this evolution; PDF text extraction is not currently implemented.

The complete Evidence Store, centralized orchestration of multiple agents, and Content Agent are part of the broader development roadmap.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Main development language. |
| LangGraph | Agent workflow orchestration. |
| LangChain | LLM integration. |
| Ollama | Local LLM inference. |
| Pydantic | Data validation and structured models. |
| HTTPX | HTTP requests and resource acquisition. |
| Trafilatura | HTML content extraction. |
| DDGS | Web search provider. |
| Pytest | Automated testing. |

## Project Structure

The project follows a domain-oriented organization.

```text
src/research_agent/
├── core/
│   └── models/
│       └── resource.py
│
├── discovery/
│   └── models.py
│
├── ingestion/
│   ├── acquisition.py
│   ├── detector.py
│   ├── storage.py
│   └── workers/
│       └── html.py
│
├── graph.py
├── nodes.py
├── state.py
├── tools.py
├── llm.py
└── config.py

docs/
├── architecture/
└── diagrams/

tests/
```

The structure will evolve as additional domains and specialized agents are implemented.

## Installation and Configuration

### Requirements

- Python 3.11 or later.
- Git.
- Ollama.
- A compatible local language model.

### Clone the repository

```bash
git clone https://github.com/Rafakka/aspasia-agent.git
cd aspasia-agent
```

### Create a virtual environment

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Linux:

```bash
source .venv/bin/activate
```

### Install dependencies

```bash
pip install -e ".[dev]"
```

### Configure Ollama

Start Ollama and download a model:

```bash
ollama pull qwen3:4b
```

Configure the model in your `.env` file:

```env
RESEARCH_AGENT_MODEL=qwen3:4b
```

The LLM integration is centralized in `llm.py`, allowing the model provider to be changed without embedding provider-specific logic throughout the research workflow.

## Running the Application

The current research workflow can be executed through the command-line interface:

```bash
research-agent "Your research topic"
```

To skip the interactive approval gate:

```bash
research-agent "Your research topic" --auto
```

To specify the report output directory:

```bash
research-agent "Your research topic" --out-dir reports
```

## Tests

Run the test suite with:

```bash
python -m pytest
```

Tests cover the research workflow and implemented ingestion components.

Additional tests will be introduced as the architecture evolves.

## Architecture Documentation

More detailed architectural decisions and diagrams are available in:

- `docs/architecture/` — architecture overview and design decisions.
- `docs/diagrams/` — domain, relationship, workflow, and system architecture diagrams.

## Development Roadmap

Aspásia is under active development.

The main development directions are:

1. Complete the research and resource acquisition pipeline.
2. Integrate acquisition results into the LangGraph workflow.
3. Establish source and resource registries.
4. Implement evidence extraction and persistence.
5. Consolidate research report generation and approval.
6. Develop the Content Agent.
7. Introduce centralized orchestration between specialized agents.
8. Expand resilience, observability, and automated testing.

## Attribution

Aspásia was initially developed from [Foundry AI's LangGraph Research Agent](https://github.com/foundry-ai-dev/langgraph-research-agent).

The original project provided the initial research-agent architecture, including its LangGraph workflow, human-in-the-loop approval mechanism, and research synthesis process.

Aspásia is an independent adaptation that extends this foundation with a broader architectural vision, domain-oriented organization, document acquisition capabilities, and a planned multi-agent research and content production platform.

The original project's authorship and contributions are acknowledged with appreciation.
