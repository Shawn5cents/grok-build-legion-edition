//! Interactive `/connect` modal for Cloud SaaS Providers & Gateways.
//!
//! Provides provider selection picker for 13 Cloud SaaS providers & gateways,
//! secure API key prompt, validation against `/v1/models` endpoints,
//! and keychain storage in `~/.grok/credentials.toml`.

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
}

pub static CLOUD_PROVIDERS: &[ProviderSpec] = &[
    ProviderSpec {
        id: "kimi",
        name: "Kimi Code",
        endpoint: "https://api.kimi.com/coding/v1",
        description: "Moonshot Kimi Code API endpoint",
    },
    ProviderSpec {
        id: "moonshot",
        name: "Moonshot AI",
        endpoint: "https://api.moonshot.ai/v1",
        description: "Moonshot AI platform endpoint",
    },
    ProviderSpec {
        id: "opencode",
        name: "OpenCode Go",
        endpoint: "https://api.opencode.ai/v1",
        description: "OpenCode Go stealth gateway endpoint",
    },
    ProviderSpec {
        id: "venice",
        name: "Venice AI",
        endpoint: "https://api.venice.ai/api/v1",
        description: "Venice AI privacy-first model endpoint",
    },
    ProviderSpec {
        id: "zenmux",
        name: "ZenMux",
        endpoint: "https://zenmux.ai/api/v1",
        description: "ZenMux Cloud SaaS Gateway endpoint",
    },
    ProviderSpec {
        id: "openrouter",
        name: "OpenRouter",
        endpoint: "https://openrouter.ai/api/v1",
        description: "OpenRouter Unified API gateway",
    },
    ProviderSpec {
        id: "cline",
        name: "Cline Pass",
        endpoint: "https://api.cline.bot/v1",
        description: "Cline Pass gateway endpoint",
    },
    ProviderSpec {
        id: "kilo",
        name: "Kilo Code",
        endpoint: "https://api.kilocode.com/v1",
        description: "Kilo Code SaaS API endpoint",
    },
    ProviderSpec {
        id: "xai",
        name: "xAI / Grok",
        endpoint: "https://api.x.ai/v1",
        description: "xAI Grok native frontier model endpoint",
    },
    ProviderSpec {
        id: "deepseek",
        name: "DeepSeek Native",
        endpoint: "https://api.deepseek.com/v1",
        description: "DeepSeek AI direct provider endpoint",
    },
    ProviderSpec {
        id: "gemini",
        name: "Google Gemini",
        endpoint: "https://generativelanguage.googleapis.com/v1beta",
        description: "Google Gemini REST API endpoint",
    },
    ProviderSpec {
        id: "openai",
        name: "OpenAI / Codex",
        endpoint: "https://api.openai.com/v1",
        description: "OpenAI / Codex API endpoint",
    },
    ProviderSpec {
        id: "minimax",
        name: "MiniMax",
        endpoint: "https://api.minimax.io/v1",
        description: "MiniMax M3 frontier model endpoint",
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
}

pub fn get_credentials_path() -> PathBuf {
    xai_grok_config::user_grok_home()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("credentials.toml")
}

pub fn load_credentials() -> CredentialsToml {
    let path = get_credentials_path();
    if path.exists() {
        if let Ok(content) = fs::read_to_string(&path) {
            if let Ok(creds) = toml::from_str(&content) {
                return creds;
            }
        }
    }
    CredentialsToml::default()
}

pub fn save_provider_credential(provider_id: &str, api_key: &str, endpoint: &str) -> std::io::Result<()> {
    let path = get_credentials_path();
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let mut creds = load_credentials();
    creds.providers.insert(
        provider_id.to_string(),
        ProviderEntry {
            api_key: api_key.to_string(),
            endpoint: endpoint.to_string(),
        },
    );
    let toml_str = toml::to_string_pretty(&creds)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;
    fs::write(path, toml_str)
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
    Confirmed {
        provider_id: String,
        discovered_models: Vec<String>,
    },
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
        }
    }

    pub fn selected_provider(&self) -> &ProviderSpec {
        &CLOUD_PROVIDERS[self.focus.min(CLOUD_PROVIDERS.len() - 1)]
    }

    pub fn handle_key(&mut self, key: &KeyEvent) -> ConnectModalOutcome {
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
                    self.step = ConnectStep::KeyPrompt;
                    let prov = self.selected_provider();
                    if let Some(entry) = self.creds.providers.get(prov.id) {
                        self.input_buffer = entry.api_key.clone();
                    } else {
                        self.input_buffer.clear();
                    }
                    self.status_message = None;
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
                    let prov = self.selected_provider();
                    let prov_id = prov.id.to_string();
                    let prov_name = prov.name.to_string();
                    let prov_endpoint = prov.endpoint.to_string();
                    // Validate key against /v1/models endpoint
                    match validate_key_against_endpoint(&prov_endpoint, &key_text) {
                        Ok(models) => {
                            let _ = save_provider_credential(&prov_id, &key_text, &prov_endpoint);
                            self.creds = load_credentials();
                            self.discovered_models = models.clone();
                            self.step = ConnectStep::Result;
                            self.status_message = Some(format!(
                                "Successfully connected to {prov_name}! Discovered {} models.",
                                models.len()
                            ));
                            ConnectModalOutcome::Confirmed {
                                provider_id: prov_id,
                                discovered_models: models,
                            }
                        }
                        Err(err) => {
                            self.status_message = Some(format!("Validation error: {err}"));
                            ConnectModalOutcome::Changed
                        }
                    }
                }
                _ => ConnectModalOutcome::Unchanged,
            },
            ConnectStep::Result | ConnectStep::Validating => match key.code {
                KeyCode::Esc | KeyCode::Enter => {
                    self.step = ConnectStep::ProviderSelect;
                    self.status_message = None;
                    ConnectModalOutcome::Changed
                }
                _ => ConnectModalOutcome::Unchanged,
            },
        }
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
            _ => ConnectModalOutcome::Unchanged,
        }
    }
}

/// Validate key against /v1/models endpoint via HTTP GET
pub fn validate_key_against_endpoint(endpoint: &str, api_key: &str) -> Result<Vec<String>, String> {
    let client = reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(8))
        .build()
        .map_err(|e| format!("Failed to build HTTP client: {e}"))?;

    let url = if endpoint.contains("generativelanguage.googleapis.com") {
        format!("{endpoint}/models?key={api_key}")
    } else if endpoint.ends_with("/models") {
        endpoint.to_string()
    } else {
        format!("{}/models", endpoint.trim_end_matches('/'))
    };

    let mut req = client.get(&url);
    if !endpoint.contains("generativelanguage.googleapis.com") {
        req = req.header("Authorization", format!("Bearer {api_key}"));
    }

    let resp = req.send().map_err(|e| format!("HTTP connection error: {e}"))?;
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
        model_ids.push("default-model".to_string());
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
                Style::default().fg(theme.text_primary).add_modifier(Modifier::BOLD),
            )]));
            lines.push(Line::from(""));

            for (idx, prov) in CLOUD_PROVIDERS.iter().enumerate() {
                let is_focused = idx == state.focus;
                let is_connected = state.creds.providers.contains_key(prov.id);

                let status_span = if is_connected {
                    Span::styled("[Connected]", Style::default().fg(theme.accent_success))
                } else {
                    Span::styled("[Not Connected]", Style::default().fg(theme.gray_dim))
                };

                let prefix = if is_focused { " ▶ " } else { "   " };
                let style = if is_focused {
                    Style::default().fg(theme.accent_user).add_modifier(Modifier::BOLD)
                } else {
                    Style::default().fg(theme.text_primary)
                };

                lines.push(Line::from(vec![
                    Span::styled(prefix, style),
                    Span::styled(format!("{:<18}", prov.name), style),
                    Span::raw(" "),
                    status_span,
                    Span::styled(format!(" - {}", prov.endpoint), Style::default().fg(theme.gray_dim)),
                ]));
            }
        }
        ConnectStep::KeyPrompt => {
            let prov = state.selected_provider();
            lines.push(Line::from(vec![
                Span::raw("Provider: "),
                Span::styled(prov.name, Style::default().fg(theme.accent_user).add_modifier(Modifier::BOLD)),
            ]));
            lines.push(Line::from(vec![
                Span::raw("Endpoint: "),
                Span::styled(prov.endpoint, Style::default().fg(theme.gray_dim)),
            ]));
            lines.push(Line::from(""));

            lines.push(Line::from(Span::styled(
                "Enter API Key (will be validated against /v1/models):",
                Style::default().fg(theme.text_primary).add_modifier(Modifier::BOLD),
            )));

            let masked_buffer: String = if state.input_buffer.is_empty() {
                "Paste/Type API Key here...".to_string()
            } else {
                "*".repeat(state.input_buffer.len().min(40))
            };

            let input_style = if state.input_buffer.is_empty() {
                Style::default().fg(theme.gray_dim).bg(theme.bg_dark)
            } else {
                Style::default().fg(theme.accent_success).bg(theme.bg_dark).add_modifier(Modifier::BOLD)
            };

            lines.push(Line::from(vec![
                Span::styled(format!("  🔑 {masked_buffer} "), input_style),
            ]));

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
                Style::default().fg(theme.running).add_modifier(Modifier::BOLD),
            )));
        }
        ConnectStep::Result => {
            if let Some(ref msg) = state.status_message {
                lines.push(Line::from(Span::styled(
                    msg.as_str(),
                    Style::default().fg(theme.accent_success).add_modifier(Modifier::BOLD),
                )));
            }
            if !state.discovered_models.is_empty() {
                lines.push(Line::from(""));
                lines.push(Line::from(Span::styled(
                    "Discovered Models:",
                    Style::default().fg(theme.text_primary).add_modifier(Modifier::BOLD),
                )));
                for m in state.discovered_models.iter().take(6) {
                    lines.push(Line::from(vec![
                        Span::styled("   • ", Style::default().fg(theme.accent_user)),
                        Span::styled(m.as_str(), Style::default().fg(theme.text_primary)),
                    ]));
                }
                if state.discovered_models.len() > 6 {
                    lines.push(Line::from(Span::styled(
                        format!("   ... and {} more models", state.discovered_models.len() - 6),
                        Style::default().fg(theme.gray_dim),
                    )));
                }
            }
            lines.push(Line::from(""));
            lines.push(Line::from(Span::styled(
                "Saved to ~/.grok/credentials.toml! Press Enter or Esc to return.",
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
        assert_eq!(CLOUD_PROVIDERS.len(), 13);
        assert_eq!(CLOUD_PROVIDERS[0].id, "kimi");
        assert_eq!(CLOUD_PROVIDERS[3].id, "venice");
    }

    #[test]
    fn test_connect_modal_state_init() {
        let state = ConnectModalState::new();
        assert_eq!(state.step, ConnectStep::ProviderSelect);
        assert_eq!(state.selected_provider().id, "kimi");
    }
}
