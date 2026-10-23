"""Host-rendered application tools (e.g. ANSYS Journal Studio).

Such plugins ship data/templates and ``ui_contributions`` menu actions that the
host app renders itself; they have no template entrypoint. The app gates these
actions on the ``application-tools`` capability (hpc_gui
``services/plugin_menu_actions.py``), so the capability is satisfied by at
least one of these actions instead of a ``template_index``/``job_templates``
entrypoint.
"""

from __future__ import annotations

# Keep in sync with the app's action -> capability map for "application-tools".
APPLICATION_TOOL_ACTIONS = frozenset(
    {
        "journal_studio.open",
        "journal_studio.new",
        "journal_studio.open_journal",
        "journal_studio.settings",
    }
)


def provides_host_rendered_tool(manifest: dict) -> bool:
    """True when the manifest's plugins menu offers an application-tool action."""
    menu = (manifest.get("ui_contributions") or {}).get("plugins_menu") or {}
    items = menu.get("items") or []
    return any(
        isinstance(item, dict) and item.get("action") in APPLICATION_TOOL_ACTIONS
        for item in items
    )
