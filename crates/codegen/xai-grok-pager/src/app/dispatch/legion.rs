//! Legion DAG model synchronization.
//!
//! In Legion mode the root session is the orchestrator, so its base model must
//! be the model assigned to `[subagents.models].orchestrator`. Other DAG roles
//! remain heterogeneous and resolve independently when their subagents spawn.

use crate::app::actions::Effect;
use crate::app::agent::AgentId;
use crate::app::agent_view::AgentView;
use crate::app::app_view::AppView;
use agent_client_protocol as acp;

pub(super) const ORCHESTRATOR_ROLE: &str = "orchestrator";

pub(crate) fn is_active(app: &AppView) -> bool {
    app.current_ui.permission_mode.as_deref() == Some("legion")
}

pub(crate) fn orchestrator_model(agent: &AgentView) -> Option<acp::ModelId> {
    let configured = agent.legion_assignments.get(ORCHESTRATOR_ROLE)?;
    agent.session.models.resolve_by_name_or_id(configured)
}

fn configured_orchestrator_id(app: &AppView, agent_id: AgentId) -> Option<acp::ModelId> {
    orchestrator_model(app.agents.get(&agent_id)?)
}

/// In Legion mode, replace an ordinary creation-time model with the assigned
/// orchestrator model and mirror that choice immediately in the placeholder UI.
pub(super) fn creation_model(
    app: &mut AppView,
    agent_id: AgentId,
    requested: Option<acp::ModelId>,
) -> Option<acp::ModelId> {
    if !is_active(app) {
        return requested;
    }
    let Some(orchestrator) = configured_orchestrator_id(app, agent_id) else {
        return requested;
    };
    if let Some(agent) = app.agents.get_mut(&agent_id) {
        agent.session.models.set_current(orchestrator.clone(), None);
    }
    Some(orchestrator)
}

/// Switch an existing Legion root session to its assigned orchestrator model.
/// A not-yet-created session stores the same choice as its deferred switch.
pub(super) fn synchronize_orchestrator(app: &mut AppView, agent_id: AgentId) -> Vec<Effect> {
    if !is_active(app) {
        return vec![];
    }
    let Some(orchestrator) = configured_orchestrator_id(app, agent_id) else {
        return vec![];
    };
    let Some(agent) = app.agents.get_mut(&agent_id) else {
        return vec![];
    };
    if agent.session.models.current.as_ref() == Some(&orchestrator) {
        return vec![];
    }
    let Some(session_id) = agent.session.session_id.clone() else {
        agent.session.models.set_current(orchestrator.clone(), None);
        agent.session.deferred_model_switch = Some((orchestrator, None));
        return vec![];
    };
    let prev_model_id = agent.session.models.current.clone();
    agent.session.models.set_current(orchestrator.clone(), None);
    agent.session.model_switch_pending = true;
    vec![Effect::SwitchModel {
        agent_id,
        session_id,
        model_id: orchestrator,
        effort: None,
        prev_model_id,
    }]
}

/// Apply the Legion root-model invariant to every open top-level session.
/// Legion is app-wide, so switching between already-open sessions must never
/// reveal a stale base model or stale role labels.
pub(super) fn synchronize_all_orchestrators(app: &mut AppView) -> Vec<Effect> {
    let agent_ids: Vec<AgentId> = app.agents.keys().copied().collect();
    agent_ids
        .into_iter()
        .flat_map(|agent_id| synchronize_orchestrator(app, agent_id))
        .collect()
}

/// Apply the modal's persisted role assignment to the live view. Selecting the
/// orchestrator additionally updates the root/base model while Legion is active.
pub(super) fn role_model_assigned(
    app: &mut AppView,
    _agent_id: AgentId,
    role: String,
    model_id: acp::ModelId,
) -> Vec<Effect> {
    for agent in app.agents.values_mut() {
        let model_id_string = model_id.0.to_string();
        agent
            .legion_assignments
            .insert(role.clone(), model_id_string.clone());
        if let Some(modal) = agent.agents_modal.as_mut() {
            modal
                .legion_assignments
                .insert(role.clone(), model_id_string);
        }
    }
    let mut effects = vec![Effect::ReloadLegionAssignments];
    if role == ORCHESTRATOR_ROLE {
        effects.extend(synchronize_all_orchestrators(app));
    }
    effects
}

/// General model pickers cannot move the root away from the configured
/// orchestrator while Legion mode is active.
pub(super) fn base_model_change_allowed(
    app: &AppView,
    agent_id: AgentId,
    requested: &acp::ModelId,
) -> bool {
    !is_active(app) || configured_orchestrator_id(app, agent_id).as_ref() == Some(requested)
}

pub(super) fn set_orchestrator_in_memory(agent: &mut AgentView, model_id: &acp::ModelId) {
    let model_id = model_id.0.to_string();
    agent
        .legion_assignments
        .insert(ORCHESTRATOR_ROLE.to_string(), model_id.clone());
    if let Some(modal) = agent.agents_modal.as_mut() {
        modal
            .legion_assignments
            .insert(ORCHESTRATOR_ROLE.to_string(), model_id);
    }
}

/// Roll a failed orchestrator switch back to the root session's actual model,
/// then reconcile every other open root. This keeps all banners, pickers,
/// configs, and root footers on one value even if only one session rejects a
/// selected model.
pub(super) fn restore_orchestrator_to_base(app: &mut AppView, agent_id: AgentId) -> Vec<Effect> {
    let Some(base_model) = app
        .agents
        .get(&agent_id)
        .and_then(|agent| agent.session.models.current.clone())
    else {
        return vec![];
    };
    for agent in app.agents.values_mut() {
        set_orchestrator_in_memory(agent, &base_model);
    }
    let mut effects = vec![Effect::PersistLegionRoleModel {
        role: ORCHESTRATOR_ROLE.to_string(),
        model_id: base_model.0.to_string(),
    }];
    effects.extend(synchronize_all_orchestrators(app));
    effects
}
