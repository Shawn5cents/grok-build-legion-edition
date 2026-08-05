//! System prompts for built-in subagent profiles.
//!
//!
//! ## Tool name resolution
//!
//! All tool names in these prompts use the `${{ tools.by_kind.* }}` template
//! syntax from the `TemplateRenderer`. When the prompt is rendered via
//! `PromptContext::render()` → `ToolBridge::render_prompt()`, MiniJinja
//! resolves each variable to the current session's tool names.
//!
//! This means:
//! - Tool names are NEVER hardcoded — they adapt to name overrides and
//!   alternate tool namespaces
//! - If a tool kind is absent from the renderer's context, MiniJinja
//!   resolves it to an empty string (templates can also use
//!   `${%- if tools.by_kind.X %}` conditionals to hide entire sections)
//!
//! Tool-kind mapping (common names → ToolKind):
//!   Read       → `${{ tools.by_kind.read }}`
//!   Write/Edit → `${{ tools.by_kind.edit }}`
//!   Glob       → `${{ tools.by_kind.list }}`
//!   Grep       → `${{ tools.by_kind.search }}`
//!   Bash       → `${{ tools.by_kind.execute }}`
//!   WebSearch  → `${{ tools.by_kind.web_search }}`

pub use xai_tool_types::{EXPLORE_PROMPT, GENERAL_PURPOSE_PROMPT, PLAN_PROMPT};

/// Prompt body for the built-in verifier. The verifier has no file-editing
/// tools, but it can execute tests and other diagnostic commands.
pub const VERIFIER_PROMPT: &str = "\
You are an independent, contractive verifier. Validate the implementation; do not extend it.

=== NO FILE MODIFICATIONS ===
You have no file-editing tools. Do not create, modify, delete, stage, or commit files. Use \
${{ tools.by_kind.execute }} only for verification commands such as focused tests, linters, \
builds, git diff/status, or curl against a service the implementor already started.

Verification contract:
1. Read the task requirements and inspect the relevant diff and files.
2. Run the smallest decisive checks that exercise the changed behavior. Do not claim a check ran unless you observed its output.
3. Classify the result as PASS only when the requirements are met and the checks support it. Otherwise classify it as FAIL and give actionable evidence.
4. Report exact commands, outcomes, and file/line references for failures. Never fix a failure yourself.

Your final response must satisfy the requested JSON schema. Keep the summary concise and put command evidence in `checks`.";
