import pytest
from h15hub.engine.tarjan import tarjan_scc, find_cycles, build_automation_graph


def test_no_cycles():
    graph = {"A": ["B"], "B": ["C"], "C": []}
    cycles = find_cycles(graph)
    assert cycles == []


def test_simple_cycle():
    graph = {"A": ["B"], "B": ["A"]}
    cycles = find_cycles(graph)
    assert len(cycles) == 1
    assert set(cycles[0]) == {"A", "B"}


def test_self_loop():
    graph = {"A": ["A"]}
    cycles = find_cycles(graph)
    assert len(cycles) == 1


def test_complex_graph():
    # A→B→C→A (Zyklus), D→E (kein Zyklus)
    graph = {"A": ["B"], "B": ["C"], "C": ["A"], "D": ["E"], "E": []}
    cycles = find_cycles(graph)
    assert len(cycles) == 1
    assert set(cycles[0]) == {"A", "B", "C"}


def test_empty_graph():
    assert find_cycles({}) == []


def test_build_automation_graph():
    automations = [
        {"trigger": "device:lasercutter:status = free", "action": "device:labelprinter:print"},
        {"trigger": "device:bambu-p1s-1:progress = 100", "action": "device:labelprinter:print"},
    ]
    graph = build_automation_graph(automations)
    assert "lasercutter" in graph
    assert "labelprinter" in graph["lasercutter"]
    assert "bambu-p1s-1" in graph


def test_automation_cycle_detected():
    """Zirkuläre Automation: Lasercutter triggert Bambu, Bambu triggert Lasercutter."""
    automations = [
        {"trigger": "device:lasercutter:status = free", "action": "device:bambu-p1s-1:start"},
        {"trigger": "device:bambu-p1s-1:status = free", "action": "device:lasercutter:start"},
    ]
    graph = build_automation_graph(automations)
    cycles = find_cycles(graph)
    assert len(cycles) == 1


def test_automation_engine_rejects_cycles():
    from h15hub.engine.automation import AutomationEngine
    automations = [
        {"name": "A→B", "trigger": "device:foo:status = free", "action": "device:bar:start"},
        {"name": "B→A", "trigger": "device:bar:status = free", "action": "device:foo:start"},
    ]
    with pytest.raises(ValueError, match="Zirkuläre"):
        AutomationEngine(automations)


def test_automation_engine_accepts_valid():
    from h15hub.engine.automation import AutomationEngine
    automations = [
        {"name": "Drucker fertig", "trigger": "device:bambu-p1s-1:progress = 100",
         "action": "notify:member:all"},
    ]
    engine = AutomationEngine(automations)
    assert len(engine.automations) == 1
