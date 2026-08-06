"""The :class:`AgentSuite` — one handle for the whole Phase-4 AI subsystem.

Grouping the prompt registry, tool registry, copilot graph, and the four bounded
agents into a single frozen value lets the presentation layer depend on *one*
application type (via the :class:`~complianceiq.presentation.container.Container`
protocol) instead of six. The composition root builds it
(``build_agent_suite``); this module only defines its shape, so it stays free of
any infrastructure import.
"""

from __future__ import annotations

from dataclasses import dataclass

from complianceiq.application.agents.compliance_analyst import ComplianceAnalystAgent
from complianceiq.application.agents.remediation_engineer import RemediationEngineerAgent
from complianceiq.application.agents.report_writer import ReportWriterAgent
from complianceiq.application.agents.risk_analyst import RiskAnalystAgent
from complianceiq.application.graphs.copilot import CopilotGraph
from complianceiq.application.prompts.registry import PromptRegistry
from complianceiq.application.tools.registry import ToolRegistry


@dataclass(frozen=True, slots=True)
class AgentSuite:
    """The Phase 4 AI capabilities — bounded agents over graphs and tools.

    ``prompts`` and ``tools`` are exposed for introspection (e.g. an admin
    endpoint listing available prompts/tools); ``copilot`` is the Q&A graph; the
    four agents are the capability entry points the API calls.
    """

    prompts: PromptRegistry
    tools: ToolRegistry
    copilot: CopilotGraph
    compliance_analyst: ComplianceAnalystAgent
    remediation_engineer: RemediationEngineerAgent
    report_writer: ReportWriterAgent
    risk_analyst: RiskAnalystAgent
