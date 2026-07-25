//! Visual Heterogeneous Multi-Agent DAG Banner Widget.
//! Displays node graph and model assignments at the top of the workspace.

use ratatui::buffer::Buffer;
use ratatui::layout::Rect;
use ratatui::style::{Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Widget};

use crate::theme::Theme;

pub struct LegionDagBanner<'a> {
    pub orchestrator_model: &'a str,
    pub explore_model: &'a str,
    pub architect_model: &'a str,
    pub implementor_model: &'a str,
    pub verifier_model: &'a str,
}

impl<'a> LegionDagBanner<'a> {
    pub fn new(
        orchestrator_model: &'a str,
        explore_model: &'a str,
        architect_model: &'a str,
        implementor_model: &'a str,
        verifier_model: &'a str,
    ) -> Self {
        Self {
            orchestrator_model,
            explore_model,
            architect_model,
            implementor_model,
            verifier_model,
        }
    }
}

impl Widget for LegionDagBanner<'_> {
    fn render(self, area: Rect, buf: &mut Buffer) {
        if area.height < 2 || area.width < 20 {
            return;
        }

        let theme = Theme::current();
        let border_style = Style::default().fg(theme.accent_plan);
        let title_style = Style::default().fg(theme.accent_user).add_modifier(Modifier::BOLD);
        let arrow_style = Style::default().fg(theme.gray);
        let label_style = Style::default().fg(theme.text_primary).add_modifier(Modifier::BOLD);
        let model_style = Style::default().fg(theme.accent_plan);

        // Draw top border line with title
        let block = Block::default()
            .borders(Borders::ALL)
            .border_style(border_style)
            .title(Span::styled(" ⚔️ LEGION HETEROGENEOUS MULTI-AGENT DAG [Ctrl+B to hide] ", title_style));
        block.render(area, buf);

        let inner_y = area.y + 1;
        let inner_x = area.x + 2;
        let max_width = area.width.saturating_sub(4);

        if area.height >= 3 {
            // Line 1: Orchestrator -> Explore -> Architect
            let line1 = Line::from(vec![
                Span::styled("🎯 Orchestrator ", label_style),
                Span::styled(format!("[{}] ", self.orchestrator_model), model_style),
                Span::styled("➔ ", arrow_style),
                Span::styled("🔍 Explore ", label_style),
                Span::styled(format!("[{}] ", self.explore_model), model_style),
                Span::styled("➔ ", arrow_style),
                Span::styled("📐 Architect ", label_style),
                Span::styled(format!("[{}]", self.architect_model), model_style),
            ]);
            buf.set_line(inner_x, inner_y, &line1, max_width);

            // Line 2: -> Implementor -> Verifier
            let line2 = Line::from(vec![
                Span::styled("   ➔ 🛠️ Implementor ", label_style),
                Span::styled(format!("[{}] ", self.implementor_model), model_style),
                Span::styled("➔ ", arrow_style),
                Span::styled("🧪 Verifier ", label_style),
                Span::styled(format!("[{}]", self.verifier_model), model_style),
            ]);
            buf.set_line(inner_x, inner_y + 1, &line2, max_width);
        } else {
            // Single line compact render for tight areas
            let compact_line = Line::from(vec![
                Span::styled("🎯 Orch ", label_style),
                Span::styled("➔ ", arrow_style),
                Span::styled("🔍 Expl ", label_style),
                Span::styled("➔ ", arrow_style),
                Span::styled("📐 Arch ", label_style),
                Span::styled("➔ ", arrow_style),
                Span::styled("🛠️ Impl ", label_style),
                Span::styled("➔ ", arrow_style),
                Span::styled("🧪 Verif", label_style),
            ]);
            buf.set_line(inner_x, inner_y, &compact_line, max_width);
        }
    }
}
