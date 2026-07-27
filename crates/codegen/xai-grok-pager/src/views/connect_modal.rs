//! Interactive `/connect` modal for Cloud SaaS Providers & Gateways.
//!
//! Provides provider selection for cloud SaaS providers and gateways,
//! masked API key prompt, validation against `/v1/models` endpoints, private
//! credential storage, and hot-reloaded `[model.*]` runtime configuration.

use crossterm::event::{KeyCode, KeyEvent, KeyModifiers};
use ratatui::buffer::Buffer;
use ratatui::layout::Rect;
use ratatui::style::{Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Paragraph, Widget};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::fs;
use std::path::PathBuf;
use std::sync::mpsc;

use crate::theme::Theme;
use crate::views::modal_window::{
    ModalSizing, ModalWindowConfig, ModalWindowOutcome, ModalWindowState, Shortcut,
    handle_modal_key, handle_modal_mouse, render_modal_window,
};

/// Provider definition.
#[derive(Debug, Clone)]
pub struct ProviderSpec {
    pub id: &'static str,
    pub name: &'static str,
    pub endpoint: &'static str,
    pub description: &'static str,
    pub context_window: u64,
}

pub static CLOUD_PROVIDERS: &[ProviderSpec] = &[
    ProviderSpec {
        id: "kimi",
        name: "Kimi Code",
        endpoint: "https://api.kimi.com/coding/v1",
        description: "Moonshot Kimi Code API endpoint",
        context_window: 1_000_000,
    },
    ProviderSpec {
        id: "moonshot",
        name: "Moonshot AI",
        endpoint: "https://api.moonshot.ai/v1",
        description: "Moonshot AI platform endpoint",
        context_window: 1_000_000,
    },
    ProviderSpec {
        id: "opencode",
        name: "OpenCode Go",
        endpoint: "https://api.opencode.ai/v1",
        description: "OpenCode Go stealth gateway endpoint",
        context_window: 200_000,
    },
    ProviderSpec {
        id: "venice",
        name: "Venice AI",
        endpoint: "https://api.venice.ai/api/v1",
        description: "Venice AI privacy-first model endpoint",
        context_window: 128_000,
    },
    ProviderSpec {
        id: "zenmux",
        name: "ZenMux",
        endpoint: "https://zenmux.ai/api/v1",
        description: "ZenMux Cloud SaaS Gateway endpoint",
        context_window: 200_000,
    },
    ProviderSpec {
        id: "openrouter",
        name: "OpenRouter",
        endpoint: "https://openrouter.ai/api/v1",
        description: "OpenRouter Unified API gateway",
        context_window: 200_000,
    },
    ProviderSpec {
        id: "cline",
        name: "Cline Pass",
        endpoint: "https://api.cline.bot/v1",
        description: "Cline Pass gateway endpoint",
        context_window: 200_000,
    },
    ProviderSpec {
        id: "kilo",
        name: "Kilo Code",
        endpoint: "https://api.kilocode.com/v1",
        description: "Kilo Code SaaS API endpoint",
        context_window: 200_000,
    },
    ProviderSpec {
        id: "xai",
        name: "xAI / Grok",
        endpoint: "https://api.x.ai/v1",
        description: "xAI Grok native frontier model endpoint",
        context_window: 500_000,
    },
    ProviderSpec {
        id: "deepseek",
        name: "DeepSeek Native",
        endpoint: "https://api.deepseek.com/v1",
        description: "DeepSeek AI direct provider endpoint",
        context_window: 200_000,
    },
    ProviderSpec {
        id: "gemini",
        name: "Google Gemini",
        endpoint: "https://generativelanguage.googleapis.com/v1beta/openai",
        description: "Google Gemini OpenAI-compatible endpoint",
        context_window: 1_000_000,
    },
    ProviderSpec {
        id: "anthropic",
        name: "Anthropic / Claude",
        endpoint: "https://api.anthropic.com/v1",
        description: "Anthropic Messages API endpoint",
        context_window: 200_000,
    },
    ProviderSpec {
        id: "nvidia",
        name: "NVIDIA NIM",
        endpoint: "https://integrate.api.nvidia.com/v1",
        description: "NVIDIA NIM OpenAI-compatible endpoint",
        context_window: 128_000,
    },
    ProviderSpec {
        id: "openai",
        name: "OpenAI / Codex",
        endpoint: "https://api.openai.com/v1",
        description: "OpenAI / Codex API endpoint",
        context_window: 200_000,
    },
    ProviderSpec {
        id: "minimax",
        name: "MiniMax",
        endpoint: "https://api.minimax.io/v1",
        description: "MiniMax M3 frontier model endpoint",
        context_window: 1_000_000,
    },
];

/// Persisted credentials in `~/.grok/credentials.toml`
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct CredentialsToml {
    #[serde(default)]
    pub providers: BTreeMap<String, ProviderEntry>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderEntry {
    pub api_key: String,
    pub endpoint: String,
    #[serde(default)]
    pub models: Vec<String>,
}

pub fn get_credentials_path() -> PathBuf {
    xai_grok_config::user_grok_home()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("credentials.toml")
}

fn load_credentials_from(path: &std::path::Path) -> std::io::Result<CredentialsToml> {
    match fs::read_to_string(path) {
        Ok(content) => toml::from_str(&content)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e)),
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => Ok(CredentialsToml::default()),
        Err(err) => Err(err),
    }
}

pub fn load_credentials() -> CredentialsToml {
    load_credentials_from(&get_credentials_path()).unwrap_or_default()
}

pub fn save_provider_credential(
    provider_id: &str,
    api_key: &str,
    endpoint: &str,
    models: &[String],
) -> std::io::Result<()> {
    let path = get_credentials_path();
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let mut creds = load_credentials_from(&path)?;
    creds.providers.insert(
        provider_id.to_string(),
        ProviderEntry {
            api_key: api_key.to_string(),
            endpoint: endpoint.to_string(),
            models: models.to_vec(),
        },
    );
    let toml_str = toml::to_string_pretty(&creds).map_err(std::io::Error::other)?;
    xai_grok_config::fs_atomic::write_atomically(&path, &toml_str, Some(0o600))
}

fn save_models_to_runtime_config(
    path: &std::path::Path,
    provider: &ProviderSpec,
    api_key: &str,
    models: &[String],
) -> Result<Vec<String>, String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .map_err(|e| format!("Could not create config directory: {e}"))?;
    }
    if path.exists() {
        fs::read_to_string(path)
            .map_err(|e| format!("Could not read the existing config.toml: {e}"))?;
    }
    let Some(mut doc) = crate::config_toml_edit::read_config_document_for_edit(path) else {
        return Err("config.toml is not valid TOML; it was left unchanged".to_string());
    };
    if !doc.contains_key("model") {
        doc["model"] = toml_edit::Item::Table(toml_edit::Table::new());
    }
    let model_root = doc["model"]
        .as_table_mut()
        .ok_or("[model] is not a TOML table")?;
    let mut catalog_ids = Vec::with_capacity(models.len());
    for model in models {
        let catalog_id = format!("{}/{}", provider.id, model);
        if !model_root.contains_key(&catalog_id) {
            model_root[&catalog_id] = toml_edit::Item::Table(toml_edit::Table::new());
        }
        let table = model_root[&catalog_id]
            .as_table_mut()
            .ok_or_else(|| format!("[model.{catalog_id:?}] is not a TOML table"))?;
        table["model"] = toml_edit::value(model);
        table["base_url"] = toml_edit::value(provider.endpoint);
        table["name"] = toml_edit::value(format!("{} ({})", model, provider.name));
        table["api_key"] = toml_edit::value(api_key);
        table["context_window"] = toml_edit::value(provider.context_window as i64);
        if provider.id == "anthropic" {
            table["api_backend"] = toml_edit::value("messages");
            table["auth_scheme"] = toml_edit::value("x_api_key");
        }
        catalog_ids.push(catalog_id);
    }
    xai_grok_config::fs_atomic::write_atomically(path, &doc.to_string(), Some(0o600))
        .map_err(|e| format!("Could not update config.toml: {e}"))?;
    Ok(catalog_ids)
}

fn persist_validated_provider(
    provider: &ProviderSpec,
    api_key: &str,
    models: &[String],
) -> Result<Vec<String>, String> {
    load_credentials_from(&get_credentials_path())
        .map_err(|e| format!("Could not read the existing credentials: {e}"))?;
    let config_path = xai_grok_config::grok_home().join("config.toml");
    let catalog_ids = save_models_to_runtime_config(&config_path, provider, api_key, models)?;
    save_provider_credential(provider.id, api_key, provider.endpoint, models)
        .map_err(|e| format!("Could not save credentials: {e}"))?;
    Ok(catalog_ids)
}

/// Mode of the connect modal.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ConnectStep {
    ProviderSelect,
    KeyPrompt,
    Validating,
    Result,
}

/// Outcome of user interaction in the Connect modal.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ConnectModalOutcome {
    Cancelled,
    Changed,
    Unchanged,
}

pub struct ConnectModalState {
    pub focus: usize,
    pub step: ConnectStep,
    pub input_buffer: String,
    pub status_message: Option<String>,
    pub discovered_models: Vec<String>,
    pub window: ModalWindowState,
    pub content_area: Option<Rect>,
    pub creds: CredentialsToml,
    visible_start: usize,
    validation_rx: Option<mpsc::Receiver<Result<Vec<String>, String>>>,
    validation_key: Option<String>,
    pending_catalog_models: Vec<(String, String)>,
}

impl Default for ConnectModalState {
    fn default() -> Self {
        Self::new()
    }
}

impl ConnectModalState {
    pub fn new() -> Self {
        let creds = load_credentials();
        Self {
            focus: 0,
            step: ConnectStep::ProviderSelect,
            input_buffer: String::new(),
            status_message: None,
            discovered_models: Vec::new(),
            window: ModalWindowState::new(),
            content_area: None,
            creds,
            visible_start: 0,
            validation_rx: None,
            validation_key: None,
            pending_catalog_models: Vec::new(),
        }
    }

    pub fn selected_provider(&self) -> &ProviderSpec {
        &CLOUD_PROVIDERS[self.focus.min(CLOUD_PROVIDERS.len() - 1)]
    }

    fn open_selected_provider(&mut self) {
        self.step = ConnectStep::KeyPrompt;
        let provider_id = self.selected_provider().id;
        if let Some(entry) = self.creds.providers.get(provider_id) {
            self.input_buffer.clone_from(&entry.api_key);
        } else {
            self.input_buffer.clear();
        }
        self.status_message = None;
    }

    pub fn handle_key(&mut self, key: &KeyEvent) -> ConnectModalOutcome {
        let _ = self.poll_validation();
        let config = ModalWindowConfig {
            title: "Connect Cloud SaaS Provider",
            tabs: None,
            shortcuts: &[],
            sizing: Default::default(),
            fold_info: None,
        };
        match handle_modal_key(&mut self.window, key, &config) {
            ModalWindowOutcome::CloseRequested => return ConnectModalOutcome::Cancelled,
            ModalWindowOutcome::Handled => return ConnectModalOutcome::Changed,
            _ => {}
        }

        match self.step {
            ConnectStep::ProviderSelect => match key.code {
                KeyCode::Esc => ConnectModalOutcome::Cancelled,
                KeyCode::Up | KeyCode::Char('k') => {
                    if self.focus > 0 {
                        self.focus -= 1;
                        ConnectModalOutcome::Changed
                    } else {
                        ConnectModalOutcome::Unchanged
                    }
                }
                KeyCode::Down | KeyCode::Char('j') => {
                    if self.focus + 1 < CLOUD_PROVIDERS.len() {
                        self.focus += 1;
                        ConnectModalOutcome::Changed
                    } else {
                        ConnectModalOutcome::Unchanged
                    }
                }
                KeyCode::Enter => {
                    self.open_selected_provider();
                    ConnectModalOutcome::Changed
                }
                _ => ConnectModalOutcome::Unchanged,
            },
            ConnectStep::KeyPrompt => match key.code {
                KeyCode::Esc => {
                    self.step = ConnectStep::ProviderSelect;
                    self.status_message = None;
                    ConnectModalOutcome::Changed
                }
                KeyCode::Backspace => {
                    self.input_buffer.pop();
                    ConnectModalOutcome::Changed
                }
                KeyCode::Char(c) if !key.modifiers.contains(KeyModifiers::CONTROL) => {
                    self.input_buffer.push(c);
                    ConnectModalOutcome::Changed
                }
                KeyCode::Enter => {
                    let key_text = self.input_buffer.trim().to_string();
                    if key_text.is_empty() {
                        self.status_message = Some("API Key cannot be empty".into());
                        return ConnectModalOutcome::Changed;
                    }
                    let endpoint = self.selected_provider().endpoint.to_string();
                    let (tx, rx) = mpsc::channel();
                    let validation_key = key_text.clone();
                    std::thread::spawn(move || {
                        let _ = tx.send(validate_key_against_endpoint(&endpoint, &validation_key));
                    });
                    self.validation_rx = Some(rx);
                    self.validation_key = Some(key_text);
                    self.step = ConnectStep::Validating;
                    self.status_message = None;
                    ConnectModalOutcome::Changed
                }
                _ => ConnectModalOutcome::Unchanged,
            },
            ConnectStep::Result => match key.code {
                KeyCode::Esc | KeyCode::Enter => {
                    self.step = ConnectStep::ProviderSelect;
                    self.status_message = None;
                    ConnectModalOutcome::Changed
                }
                _ => ConnectModalOutcome::Unchanged,
            },
            ConnectStep::Validating => match key.code {
                KeyCode::Esc => {
                    self.validation_rx = None;
                    self.validation_key = None;
                    self.step = ConnectStep::KeyPrompt;
                    self.status_message = Some("Validation cancelled".to_string());
                    ConnectModalOutcome::Changed
                }
                _ => ConnectModalOutcome::Unchanged,
            },
        }
    }

    fn poll_validation(&mut self) -> bool {
        let Some(rx) = self.validation_rx.as_ref() else {
            return false;
        };
        let result = match rx.try_recv() {
            Ok(result) => result,
            Err(mpsc::TryRecvError::Empty) => return false,
            Err(mpsc::TryRecvError::Disconnected) => {
                Err("Credential validation stopped unexpectedly".to_string())
            }
        };
        self.validation_rx = None;
        let api_key = self.validation_key.take().unwrap_or_default();
        match result {
            Ok(models) => {
                let provider = self.selected_provider();
                let provider_name = provider.name;
                match persist_validated_provider(provider, &api_key, &models) {
                    Ok(catalog_ids) => {
                        self.pending_catalog_models = catalog_ids
                            .iter()
                            .zip(&models)
                            .map(|(id, model)| (id.clone(), format!("{model} ({provider_name})")))
                            .collect();
                        self.creds = load_credentials();
                        self.discovered_models = catalog_ids;
                        self.input_buffer.clear();
                        self.step = ConnectStep::Result;
                        self.status_message = Some(format!(
                            "Connected to {provider_name}. Configured {} models.",
                            models.len()
                        ));
                    }
                    Err(err) => {
                        self.step = ConnectStep::KeyPrompt;
                        self.status_message = Some(format!("Save error: {err}"));
                    }
                }
            }
            Err(err) => {
                self.step = ConnectStep::KeyPrompt;
                self.status_message = Some(format!("Validation error: {err}"));
            }
        }
        true
    }

    pub fn needs_tick(&self) -> bool {
        self.step == ConnectStep::Validating
    }

    pub fn tick(&mut self) -> bool {
        self.poll_validation()
    }

    /// Drain models that were just persisted by a completed validation.
    ///
    /// The shell's config watcher remains the authoritative reload path, but
    /// the pager consumes this one-shot projection immediately so `/model`
    /// reflects a successful `/connect` without waiting for filesystem
    /// debounce and an ACP notification round-trip.
    pub fn take_pending_catalog_models(&mut self) -> Vec<(String, String)> {
        std::mem::take(&mut self.pending_catalog_models)
    }

    pub fn handle_mouse(
        &mut self,
        kind: crossterm::event::MouseEventKind,
        column: u16,
        row: u16,
    ) -> ConnectModalOutcome {
        let chrome_outcome = handle_modal_mouse(&mut self.window, kind, column, row);
        match chrome_outcome {
            ModalWindowOutcome::CloseRequested => ConnectModalOutcome::Cancelled,
            ModalWindowOutcome::Handled => ConnectModalOutcome::Changed,
            ModalWindowOutcome::ShortcutActivated(1) => {
                if self.step == ConnectStep::ProviderSelect {
                    self.open_selected_provider();
                }
                ConnectModalOutcome::Changed
            }
            ModalWindowOutcome::ShortcutActivated(2) => ConnectModalOutcome::Cancelled,
            ModalWindowOutcome::Unhandled => {
                if self.step == ConnectStep::ProviderSelect
                    && matches!(
                        kind,
                        crossterm::event::MouseEventKind::Down(crossterm::event::MouseButton::Left)
                    )
                    && let Some(area) = self.content_area
                    && area.contains((column, row).into())
                    && row >= area.y.saturating_add(2)
                {
                    let provider_row =
                        self.visible_start + row.saturating_sub(area.y).saturating_sub(2) as usize;
                    if provider_row < CLOUD_PROVIDERS.len() {
                        self.focus = provider_row;
                        self.open_selected_provider();
                        return ConnectModalOutcome::Changed;
                    }
                }
                ConnectModalOutcome::Unchanged
            }
            _ => ConnectModalOutcome::Changed,
        }
    }

    pub fn handle_paste(&mut self, text: &str) -> ConnectModalOutcome {
        if self.step != ConnectStep::KeyPrompt {
            return ConnectModalOutcome::Unchanged;
        }
        let pasted = text.trim();
        if pasted.is_empty() {
            return ConnectModalOutcome::Unchanged;
        }
        self.input_buffer = pasted.chars().take(8_192).collect();
        self.status_message = None;
        ConnectModalOutcome::Changed
    }
}

/// Validate key against /v1/models endpoint via HTTP GET
pub fn validate_key_against_endpoint(endpoint: &str, api_key: &str) -> Result<Vec<String>, String> {
    let client = reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(8))
        .build()
        .map_err(|e| format!("Failed to build HTTP client: {e}"))?;

    let url = if endpoint.ends_with("/models") {
        endpoint.to_string()
    } else {
        format!("{}/models", endpoint.trim_end_matches('/'))
    };

    let req = if endpoint.contains("api.anthropic.com") {
        client
            .get(&url)
            .header("x-api-key", api_key)
            .header("anthropic-version", "2023-06-01")
    } else {
        client
            .get(&url)
            .header("Authorization", format!("Bearer {api_key}"))
    };

    let resp = req
        .send()
        .map_err(|e| format!("HTTP connection error: {e}"))?;
    let status = resp.status();
    if !status.is_success() {
        return Err(format!("Server returned HTTP status {}", status));
    }

    let body_text = resp.text().map_err(|e| format!("Read body error: {e}"))?;
    let parsed: serde_json::Value = serde_json::from_str(&body_text)
        .map_err(|e| format!("Invalid JSON from /v1/models: {e}"))?;

    let mut model_ids = Vec::new();
    if let Some(data) = parsed.get("data").and_then(|v| v.as_array()) {
        for item in data {
            if let Some(id) = item.get("id").and_then(|v| v.as_str()) {
                model_ids.push(id.to_string());
            }
        }
    } else if let Some(models) = parsed.get("models").and_then(|v| v.as_array()) {
        for item in models {
            if let Some(name) = item.get("name").and_then(|v| v.as_str()) {
                let clean_id = name.strip_prefix("models/").unwrap_or(name);
                model_ids.push(clean_id.to_string());
            }
        }
    }

    if model_ids.is_empty() {
        return Err("The models response did not contain any model IDs".to_string());
    }

    Ok(model_ids)
}

pub fn render_connect_modal(
    buf: &mut Buffer,
    area: Rect,
    state: &mut ConnectModalState,
    theme: &Theme,
    compact: bool,
) {
    let _ = state.poll_validation();
    let shortcuts = [
        Shortcut {
            label: "↑↓ navigate",
            clickable: false,
            id: 0,
        },
        Shortcut {
            label: "Enter select",
            clickable: true,
            id: 1,
        },
        Shortcut {
            label: "Esc cancel",
            clickable: true,
            id: 2,
        },
    ];

    let config = ModalWindowConfig {
        title: "Connect Cloud SaaS Provider",
        tabs: None,
        shortcuts: &shortcuts,
        sizing: ModalSizing::default().with_compact(compact),
        fold_info: None,
    };

    let Some(areas) = render_modal_window(buf, area, &mut state.window, &config, theme) else {
        return;
    };

    let content_area = areas.content;
    state.content_area = Some(content_area);

    let mut lines: Vec<Line> = Vec::new();

    match state.step {
        ConnectStep::ProviderSelect => {
            lines.push(Line::from(vec![Span::styled(
                "Select a Cloud SaaS Provider or Gateway to configure API credentials:",
                Style::default()
                    .fg(theme.text_primary)
                    .add_modifier(Modifier::BOLD),
            )]));
            let visible_rows = usize::from(content_area.height.saturating_sub(2)).max(1);
            let visible_start = if state.focus >= visible_rows {
                state.focus + 1 - visible_rows
            } else {
                0
            };
            state.visible_start = visible_start;
            if CLOUD_PROVIDERS.len() > visible_rows {
                let visible_end = (visible_start + visible_rows).min(CLOUD_PROVIDERS.len());
                lines.push(Line::from(Span::styled(
                    format!(
                        "Showing {}–{} of {}",
                        visible_start + 1,
                        visible_end,
                        CLOUD_PROVIDERS.len()
                    ),
                    Style::default().fg(theme.gray_dim),
                )));
            } else {
                lines.push(Line::from(""));
            }

            for (idx, prov) in CLOUD_PROVIDERS
                .iter()
                .enumerate()
                .skip(visible_start)
                .take(visible_rows)
            {
                let is_focused = idx == state.focus;
                let is_connected = state.creds.providers.contains_key(prov.id);

                let status_span = if is_connected {
                    Span::styled("[Connected]", Style::default().fg(theme.accent_success))
                } else {
                    Span::styled("[Not Connected]", Style::default().fg(theme.gray_dim))
                };

                let prefix = if is_focused { " ▶ " } else { "   " };
                let style = if is_focused {
                    Style::default()
                        .fg(theme.accent_user)
                        .add_modifier(Modifier::BOLD)
                } else {
                    Style::default().fg(theme.text_primary)
                };

                lines.push(Line::from(vec![
                    Span::styled(prefix, style),
                    Span::styled(format!("{:<18}", prov.name), style),
                    Span::raw(" "),
                    status_span,
                    Span::styled(
                        format!(" - {}", prov.description),
                        Style::default().fg(theme.gray_dim),
                    ),
                ]));
            }
        }
        ConnectStep::KeyPrompt => {
            let prov = state.selected_provider();
            lines.push(Line::from(vec![
                Span::raw("Provider: "),
                Span::styled(
                    prov.name,
                    Style::default()
                        .fg(theme.accent_user)
                        .add_modifier(Modifier::BOLD),
                ),
            ]));
            lines.push(Line::from(vec![
                Span::raw("Endpoint: "),
                Span::styled(prov.endpoint, Style::default().fg(theme.gray_dim)),
            ]));
            lines.push(Line::from(Span::styled(
                prov.description,
                Style::default().fg(theme.gray_dim),
            )));
            lines.push(Line::from(""));

            lines.push(Line::from(Span::styled(
                "Enter API Key (will be validated against /v1/models):",
                Style::default()
                    .fg(theme.text_primary)
                    .add_modifier(Modifier::BOLD),
            )));

            let masked_buffer: String = if state.input_buffer.is_empty() {
                "Paste/Type API Key here...".to_string()
            } else {
                "*".repeat(state.input_buffer.len().min(40))
            };

            let input_style = if state.input_buffer.is_empty() {
                Style::default().fg(theme.gray_dim).bg(theme.bg_dark)
            } else {
                Style::default()
                    .fg(theme.accent_success)
                    .bg(theme.bg_dark)
                    .add_modifier(Modifier::BOLD)
            };

            lines.push(Line::from(vec![Span::styled(
                format!("  🔑 {masked_buffer} "),
                input_style,
            )]));

            if let Some(ref msg) = state.status_message {
                lines.push(Line::from(""));
                lines.push(Line::from(Span::styled(
                    msg.as_str(),
                    Style::default().fg(theme.accent_error),
                )));
            }
        }
        ConnectStep::Validating => {
            lines.push(Line::from(Span::styled(
                "Validating credentials against /v1/models endpoint...",
                Style::default()
                    .fg(theme.running)
                    .add_modifier(Modifier::BOLD),
            )));
        }
        ConnectStep::Result => {
            if let Some(ref msg) = state.status_message {
                lines.push(Line::from(Span::styled(
                    msg.as_str(),
                    Style::default()
                        .fg(theme.accent_success)
                        .add_modifier(Modifier::BOLD),
                )));
            }
            if !state.discovered_models.is_empty() {
                lines.push(Line::from(""));
                lines.push(Line::from(Span::styled(
                    "Discovered Models:",
                    Style::default()
                        .fg(theme.text_primary)
                        .add_modifier(Modifier::BOLD),
                )));
                for m in state.discovered_models.iter().take(6) {
                    lines.push(Line::from(vec![
                        Span::styled("   • ", Style::default().fg(theme.accent_user)),
                        Span::styled(m.as_str(), Style::default().fg(theme.text_primary)),
                    ]));
                }
                if state.discovered_models.len() > 6 {
                    lines.push(Line::from(Span::styled(
                        format!(
                            "   ... and {} more models",
                            state.discovered_models.len() - 6
                        ),
                        Style::default().fg(theme.gray_dim),
                    )));
                }
            }
            lines.push(Line::from(""));
            lines.push(Line::from(Span::styled(
                "Saved to private credentials and config.toml. Models reload automatically.",
                Style::default().fg(theme.gray_dim),
            )));
        }
    }

    Paragraph::new(lines).render(content_area, buf);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cloud_providers_list() {
        assert_eq!(CLOUD_PROVIDERS.len(), 15);
        assert_eq!(CLOUD_PROVIDERS[0].id, "kimi");
        assert_eq!(CLOUD_PROVIDERS[3].id, "venice");
    }

    #[test]
    fn test_connect_modal_state_init() {
        let state = ConnectModalState::new();
        assert_eq!(state.step, ConnectStep::ProviderSelect);
        assert_eq!(state.selected_provider().id, "kimi");
    }

    #[test]
    fn paste_populates_only_the_key_prompt() {
        let mut state = ConnectModalState::new();
        assert_eq!(
            state.handle_paste("ignored"),
            ConnectModalOutcome::Unchanged
        );
        state.step = ConnectStep::KeyPrompt;
        assert_eq!(
            state.handle_paste("  secret-key\n"),
            ConnectModalOutcome::Changed
        );
        assert_eq!(state.input_buffer, "secret-key");
    }

    #[test]
    fn validation_result_is_applied_by_the_ui_tick() {
        let mut state = ConnectModalState::new();
        let (tx, rx) = mpsc::channel();
        state.step = ConnectStep::Validating;
        state.validation_rx = Some(rx);
        state.validation_key = Some("secret-key".to_string());
        tx.send(Err("provider rejected the key".to_string()))
            .unwrap();

        assert!(state.needs_tick());
        assert!(state.tick());
        assert_eq!(state.step, ConnectStep::KeyPrompt);
        assert_eq!(
            state.status_message.as_deref(),
            Some("Validation error: provider rejected the key")
        );
    }

    #[test]
    fn configured_models_are_published_once_to_the_live_catalog() {
        let mut state = ConnectModalState::new();
        state.pending_catalog_models = vec![(
            "provider/model-id".to_string(),
            "model-id (Provider)".to_string(),
        )];

        assert_eq!(
            state.take_pending_catalog_models(),
            vec![(
                "provider/model-id".to_string(),
                "model-id (Provider)".to_string()
            )]
        );
        assert!(state.take_pending_catalog_models().is_empty());
    }

    #[test]
    fn runtime_model_config_preserves_siblings_and_routes_catalog_id() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("config.toml");
        fs::write(&path, "[ui]\ntheme = \"dark\"\n").unwrap();
        let provider = ProviderSpec {
            id: "test-provider",
            name: "Test Provider",
            endpoint: "https://example.test/v1",
            description: "test",
            context_window: 123_456,
        };
        let ids = save_models_to_runtime_config(
            &path,
            &provider,
            "top-secret",
            &["model/one".to_string()],
        )
        .unwrap();
        assert_eq!(ids, vec!["test-provider/model/one"]);

        let body = fs::read_to_string(&path).unwrap();
        let parsed: toml::Value = toml::from_str(&body).unwrap();
        assert_eq!(parsed["ui"]["theme"].as_str(), Some("dark"));
        let model = &parsed["model"]["test-provider/model/one"];
        assert_eq!(model["model"].as_str(), Some("model/one"));
        assert_eq!(model["base_url"].as_str(), Some("https://example.test/v1"));
        assert_eq!(model["api_key"].as_str(), Some("top-secret"));
        assert_eq!(model["context_window"].as_integer(), Some(123_456));
    }

    #[test]
    fn malformed_runtime_config_is_not_overwritten() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("config.toml");
        let malformed = "this is [not toml\n";
        fs::write(&path, malformed).unwrap();
        let provider = ProviderSpec {
            id: "test",
            name: "Test",
            endpoint: "https://example.test/v1",
            description: "test",
            context_window: 200_000,
        };
        let result =
            save_models_to_runtime_config(&path, &provider, "secret", &["model".to_string()]);
        assert!(result.is_err());
        assert_eq!(fs::read_to_string(path).unwrap(), malformed);
    }

    #[test]
    fn malformed_credentials_are_reported_without_overwrite() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("credentials.toml");
        let malformed = "[providers.broken\n";
        fs::write(&path, malformed).unwrap();
        assert_eq!(
            load_credentials_from(&path).unwrap_err().kind(),
            std::io::ErrorKind::InvalidData
        );
        assert_eq!(fs::read_to_string(path).unwrap(), malformed);
    }
}
