<p align="right">
  <a href="./README.md"><strong>English</strong></a> · <a href="./HETEROGENEOUS_AGENTS.md"><strong>Architecture Specs</strong></a>
</p>

<p align="center">
  <img src="docs/assets/banner.svg" width="100%" alt="Grok Build Legion Edition Header Banner">
</p>

<div align="center">

[![Fork Creator](https://img.shields.io/badge/Creator-shawn5cents%20%2F%20Nichols%20AI-7B2CBF?style=for-the-badge&logo=github&logoColor=white)](https://github.com/shawn5cents)
[![Gateway Agnostic](https://img.shields.io/badge/Gateway-Universal%20%2F%20Agnostic-00B4D8?style=for-the-badge&logo=go&logoColor=white)](https://github.com/router-for-me/Cli-Proxy-API)
[![DAG Architecture](https://img.shields.io/badge/DAG-Multi--Agent%20Specialist%20Graph-FF007F?style=for-the-badge&logo=diagramsdotnet&logoColor=white)](HETEROGENEOUS_AGENTS.md)
[![Rust](https://img.shields.io/badge/Rust-1.85%2B-CE412B?style=for-the-badge&logo=rust&logoColor=white)](https://www.rust-lang.org)
[![License](https://img.shields.io/badge/License-Apache_2.0-00F5D4?style=for-the-badge&logo=apache&logoColor=black)](LICENSE)

<br>

**Created & Maintained by [shawn5cents](https://github.com/shawn5cents) (Nichols AI)**  
*Upstream Fork of xAI Grok Build with Universal Heterogeneous Subagent Routing.*

[🚀 Quick Start](#-quick-start) •
[🌐 Universal & Agnostic Architecture](#-universal--provider-agnostic) •
[🕸️ Multi-Agent DAG](#-heterogeneous-multi-agent-dag) •
[🎛️ Interactive Hub & Switcher](#-interactive-hub--configuration-tools) •
[🤝 Credits](#-credits--acknowledgements) •
[📄 License](LICENSE)

</div>

---

## 💡 Overview

**Grok Build Legion Edition** is a **100% Model-, CLI-, Provider-, and Gateway-Agnostic** terminal coding agent system. Built on xAI's high-performance Rust engine, Legion unlocks the ability to use **ANY model**, **ANY local or cloud provider**, **ANY gateway proxy**, and **ANY CLI tool** for each specialized subagent role (`orchestrator`, `explore`, `plan`, `general-purpose` coder, `verifier` critic).

> [!IMPORTANT]
> **Universal Freedom**: You are NEVER locked into specific models or providers. Whether you use local models (Ollama, LM Studio, vLLM), cloud SaaS providers (OpenAI, DeepSeek, Anthropic, Gemini, Grok, MiniMax, Qwen, Moonshot), universal gateways (CLIProxyAPI, LiteLLM, OpenRouter, ZenMux, Kilo Code, Cline Pass), or direct API endpoints — Legion automatically discovers and works with whatever you have configured!

---

## 🌐 Universal & Provider-Agnostic

Legion decouples agent roles from specific vendor lock-in:

- **Bring Any Model**: DeepSeek, OpenAI / Codex, Anthropic / Claude, Google Gemini, xAI Grok, MiniMax, Qwen, Mistral, Moonshot Kimi, Llama 3, CodeLlama, or local Ollama models.
- **Bring Any Gateway or Proxy**: `CLIProxyAPI`, LiteLLM, OpenRouter, ZenMux, Kilo Code, Cline Pass, vLLM, local HTTP proxies, or direct SaaS API endpoints.
- **Bring Any CLI Tool**: Automatically detects and leverages `ollama`, `opencode`, `codex`, `cline`, `agy`, `python3`, `go`, and local binaries installed on your system.
- **100% Upstream Git Hygiene**: Zero core engine modifications required — preserves 100% clean `git pull upstream main` compatibility.

---

## 🕸️ Heterogeneous Multi-Agent DAG

Legion allows assigning **ANY model** to **ANY specialized role** in a Directed Acyclic Graph (DAG):

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'lineColor': '#8A2BE2', 'primaryColor': '#1E1E2E', 'primaryTextColor': '#FFFFFF', 'primaryBorderColor': '#74C7EC', 'nodeBorder': '#74C7EC'}}}%%
graph TD
    User["👤 User Request"] --> Router["🧠 Router / Lead<br/><code>Any Model (e.g. DeepSeek V4 Pro)</code>"]

    subgraph DAG ["🕸️ Heterogeneous Specialist Graph"]
        Router -->|Complex Task| Explorer["🔍 Explorer<br/><code>Any Model (e.g. Flash / Local Ollama)</code>"]
        Router -->|Complex Task| Plan["📐 Architecture Planner<br/><code>Any Model (e.g. DeepSeek V4 Pro / Grok 4.5)</code>"]
        
        Explorer --> Implementer["💻 Implementer / Coder<br/><code>Any Model (e.g. MiniMax-M3 / Codex)</code>"]
        Plan --> Implementer
        
        Implementer --> Verifier["🛡️ Verifier Critic<br/><code>Any Model (e.g. Grok 4.5 / Gemini)</code>"]
        
        Verifier -->|PASS| Final["✅ Final Task Completion"]
        Verifier -->|FAIL| Repair["↺ 1 Bounded Repair Loop"]
        Repair --> Implementer
    end

    Router -->|Trivial Task| Implementer

    style User fill:#10002B,stroke:#7B2CBF,stroke-width:2px,color:#fff
    style Router fill:#3C096C,stroke:#C77DFF,stroke-width:3px,color:#fff
    style Explorer fill:#240046,stroke:#9D4EDD,stroke-width:2px,color:#fff
    style Plan fill:#240046,stroke:#9D4EDD,stroke-width:2px,color:#fff
    style Implementer fill:#3C096C,stroke:#E0AAFF,stroke-width:3px,color:#fff
    style Verifier fill:#5A189A,stroke:#FF85A1,stroke-width:3px,color:#fff
    style Final fill:#003566,stroke:#00B4D8,stroke-width:2px,color:#fff
    style Repair fill:#5c001e,stroke:#ff4d4f,stroke-width:2px,color:#fff
```

---

## 🎛️ Interactive Hub & Configuration Tools

Legion ships with intuitive interactive tools so you can configure models and presets with zero TOML editing required:

| Command | Description |
|---|---|
| **`legion-hub`** *(or `legion hub`)* | **Ultimate Visual Control Panel**: Browse model catalog by context window, assign models to roles, select presets, view live DAG topology, and launch sessions. |
| **`legion-mode`** *(or `legion --mode`)* | **Preset Profile Switcher**: Instantly switch between profiles (`Original Grok 4.5`, `Legion DAG`, `Cline/Codex`, `Auto-Discovered`) or run `legion-mode create` to build a custom preset. |
| **`legion-config`** | **Model & Role Editor**: Interactively change models for individual subagent roles or apply **one single LLM to ALL roles at once** (`legion-config --all <model>`). |
| **`./tools/auto-discover.py`** | **Zero-Touch Capability Scan**: Automatically scans system API keys, local binaries (`ollama`, `opencode`, `codex`, `cline`, `agy`), and running proxies to generate a tailored profile. |

---

## 🚀 Quick Start

### 1. Install Legion

```bash
git clone https://github.com/shawn5cents/grok-build-legion-edition.git
cd grok-build-legion-edition
./install.sh
```

### 2. Launch an Interactive Session

```bash
legion
```

### 3. Open the Interactive Control Hub

```bash
legion-hub
```

---

## 🤝 Credits & Acknowledgements

- **Creator & Maintainer**: **[shawn5cents](https://github.com/shawn5cents)** (Nichols AI) — Designed the Universal Heterogeneous Multi-Agent DAG Architecture, Zero-Touch Auto-Discovery Engine, interactive Hub & switcher tools, and overall Legion system.
- **Provider Gateway Engine**: **[CLIProxyAPI](https://github.com/router-for-me/Cli-Proxy-API)** (by router-for-me) — High-performance Go proxy server enabling multi-account and multi-provider protocol routing.
- **Core Engine & Agent Runtime**: **SpaceXAI / xAI Team** — Creators of the original `Grok Build` (`grok`) terminal-based AI coding agent codebase.
- **README Visual Design**: Inspired by **[oil-oil/beautify-github-readme](https://github.com/oil-oil/beautify-github-readme)**.

---

<p align="center">
  <img src="docs/assets/footer.svg" width="100%" alt="Grok Build Legion Edition Footer Banner">
</p>

## 📄 License

First-party code is licensed under the **Apache License, Version 2.0** — see [`LICENSE`](LICENSE).
