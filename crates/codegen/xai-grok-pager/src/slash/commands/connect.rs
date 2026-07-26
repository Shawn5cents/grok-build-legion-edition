//! `/connect` — Open the interactive Cloud SaaS Provider & Gateway modal.

use crate::app::actions::Action;
use crate::slash::command::{CommandExecCtx, CommandResult, SlashCommand};

/// Open the interactive `/connect` modal dialog.
pub struct ConnectCommand;

impl SlashCommand for ConnectCommand {
    fn name(&self) -> &str {
        "connect"
    }

    fn aliases(&self) -> &[&str] {
        &["cloud"]
    }

    fn description(&self) -> &str {
        "Configure Cloud SaaS Providers & Gateways"
    }

    fn session_scoped(&self) -> bool {
        false
    }

    fn offered_when_session_less(&self) -> bool {
        true
    }

    fn usage(&self) -> &str {
        "/connect"
    }

    fn run(&self, _ctx: &mut CommandExecCtx, _args: &str) -> CommandResult {
        CommandResult::Action(Action::OpenConnectModal)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_connect_command_name() {
        let cmd = ConnectCommand;
        assert_eq!(cmd.name(), "connect");
        assert_eq!(cmd.aliases(), &["cloud"]);
    }
}
