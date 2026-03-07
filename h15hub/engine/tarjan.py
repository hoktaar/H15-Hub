"""
Tarjan's Strongly Connected Components Algorithmus.
Wird verwendet um zirkuläre Abhängigkeiten in Automations-Regeln zu erkennen.
"""
from __future__ import annotations


def tarjan_scc(graph: dict[str, list[str]]) -> list[list[str]]:
    """
    Findet alle Strongly Connected Components (SCCs) im gerichteten Graphen.

    Args:
        graph: Adjazenzliste  { node: [nachbarn] }

    Returns:
        Liste von SCCs. Jede SCC ist eine Liste von Knoten.
        Eine SCC mit mehr als einem Knoten ist ein Zyklus.
    """
    index_counter = [0]
    stack: list[str] = []
    on_stack: set[str] = set()
    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    sccs: list[list[str]] = []

    def strongconnect(node: str) -> None:
        index[node] = index_counter[0]
        lowlink[node] = index_counter[0]
        index_counter[0] += 1
        stack.append(node)
        on_stack.add(node)

        for neighbour in graph.get(node, []):
            if neighbour not in index:
                strongconnect(neighbour)
                lowlink[node] = min(lowlink[node], lowlink[neighbour])
            elif neighbour in on_stack:
                lowlink[node] = min(lowlink[node], index[neighbour])

        if lowlink[node] == index[node]:
            scc: list[str] = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                scc.append(w)
                if w == node:
                    break
            sccs.append(scc)

    for node in list(graph.keys()):
        if node not in index:
            strongconnect(node)

    return sccs


def find_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """Gibt nur die SCCs zurück die echte Zyklen sind (mehr als 1 Knoten oder Self-Loop)."""
    return [
        scc for scc in tarjan_scc(graph)
        if len(scc) > 1 or (len(scc) == 1 and scc[0] in graph.get(scc[0], []))
    ]


def build_automation_graph(automations: list[dict]) -> dict[str, list[str]]:
    """
    Baut einen Abhängigkeitsgraphen aus Automations-Regeln.

    Eine Automation  trigger: device:X  →  action: device:Y
    erzeugt eine Kante  X → Y.
    """
    graph: dict[str, list[str]] = {}
    for automation in automations:
        trigger = automation.get("trigger", "")
        action = automation.get("action", "")

        trigger_device = _extract_device(trigger)
        action_device = _extract_device(action)

        if trigger_device and action_device:
            graph.setdefault(trigger_device, [])
            graph.setdefault(action_device, [])
            graph[trigger_device].append(action_device)

    return graph


def _extract_device(rule_str: str) -> str | None:
    """Extrahiert den Geräte-ID aus einem Regel-String wie 'device:bambu-p1s-1:status'."""
    parts = rule_str.split(":")
    if len(parts) >= 2 and parts[0] == "device":
        return parts[1]
    return None
