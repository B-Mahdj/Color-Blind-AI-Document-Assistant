"""Controlled responses for QA only. These are not an offline production agent."""

from colorblind_assistant.agent import AgentError
from colorblind_assistant.colors import hex_color
from colorblind_assistant.models import Action, CorrectionGroup, PagePlan, PageReview
from colorblind_assistant.pdf import contains

RED = "#CC1A1A"
GREEN = "#1A9926"
LIGHT_RED = "#E63326"
LIGHT_GREEN = "#26B233"
ORANGE = "#F2801A"


def _text(data, phrase):
    return next(item.id for item in data.text if phrase in item.text)


def _group(identifier, evidence, association, actions, legends=None):
    return CorrectionGroup(id=identifier, reason="Controlled regression fixture, not an AI judgment.",
                           evidence_text_ids=evidence, association=association, legend_ids=legends or [],
                           uncertain=False, actions=actions)


def sample_plan(data):
    groups = []
    if data.number == 1:
        actions, legends = [], []
        palette = {RED: "#005A9C", LIGHT_RED: "#005A9C", GREEN: "#A84400", LIGHT_GREEN: "#A84400", ORANGE: "#6B3C91"}
        for element in data.elements:
            color = hex_color(element.fill) if element.fill else None
            if color not in palette:
                continue
            actions.append(Action(kind="recolor", target_ids=[element.id], channel="fill", color=palette[color]))
            if color in {RED, LIGHT_RED, GREEN, LIGHT_GREEN}:
                actions.append(Action(kind="hatch", target_ids=[element.id], style="diagonal" if color in {RED, LIGHT_RED} else "cross"))
            if element.bbox[3] - element.bbox[1] < 20:
                legends.append(element.id)
        groups.append(_group("bar-categories", [_text(data, word) for word in ("Target exceeded", "On target", "Below target")], "legend", actions, legends))
    elif data.number == 2:
        actions = []
        labels = []
        for color, target, phrase in ((RED, "#005A9C", "Product A"), (GREEN, "#A84400", "Product B")):
            evidence = next(item.id for item in data.text if phrase in item.text and "vs" not in item.text)
            labels.append(evidence)
            paths = []
            for element in data.elements:
                for channel in ("fill", "stroke"):
                    before = getattr(element, channel)
                    if before is not None and hex_color(before) == color:
                        actions.append(Action(kind="recolor", target_ids=[element.id], channel=channel, color=target))
                        if channel == "stroke":
                            paths.append(element.id)
                            if color == GREEN:
                                actions.append(Action(kind="dash", target_ids=[element.id], style="dashed"))
            actions.append(Action(kind="label", target_ids=[paths[-1]], source_text_id=evidence))
        groups.append(_group("line-series", labels, "direct_labels", actions))
    elif data.number == 3:
        palette = {RED: "#005A9C", GREEN: "#A84400", LIGHT_RED: "#6B3C91", LIGHT_GREEN: "#303030"}
        pie, statuses, legends = [], [], []
        status_evidence = []
        for element in data.elements:
            color = hex_color(element.fill) if element.fill else None
            if color not in palette:
                continue
            contained = [item for item in data.text if contains(element.bbox, item.bbox, 1)]
            actions = statuses if contained else pie
            actions.append(Action(kind="recolor", target_ids=[element.id], channel="fill", color=palette[color]))
            if contained:
                status_evidence.extend(item.id for item in contained)
            else:
                if color in {RED, GREEN}:
                    actions.append(Action(kind="hatch", target_ids=[element.id], style="diagonal" if color == RED else "cross"))
                if element.bbox[3] - element.bbox[1] < 20:
                    legends.append(element.id)
        groups.append(_group("departments", [_text(data, word) for word in ("Marketing", "R&D", "Operations", "HR")], "legend", pie, legends))
        groups.append(_group("statuses", status_evidence, "direct_labels", statuses))
    elif data.number == 4:
        actions, evidence = [], []
        for element in data.elements:
            if not element.fill or max(element.fill) - min(element.fill) < .05:
                continue
            number = next(item for item in data.text if contains(element.bbox, item.bbox, 1) and item.text.isdigit())
            value = int(number.text)
            factor = (value - 35) / 58
            rgb = tuple((a + (b - a) * factor) / 255 for a, b in zip((234, 246, 255), (106, 174, 214)))
            actions.append(Action(kind="recolor", target_ids=[element.id], channel="fill", color=hex_color(rgb)))
            evidence.append(number.id)
        groups.append(_group("heatmap", evidence, "ordered_scale", actions))
    elif data.number == 5:
        actions, evidence = [], []
        palette = ("#005A9C", "#A84400", "#6B3C91", "#365E30", "#754B00", "#303030")
        for element in data.elements:
            if element.fill is None:
                continue
            labels = [item for item in data.text if contains(element.bbox, item.bbox, 1)]
            if labels:
                actions.append(Action(kind="recolor", target_ids=[element.id], channel="fill", color=palette[len(actions)]))
                evidence.extend(item.id for item in labels)
        groups.append(_group("regional-labels", evidence, "direct_labels", actions))
    return PagePlan(groups=groups, warnings=[])


class SampleReviewer:
    source = "controlled_test_responses"
    model = "test-double-no-network"

    def __init__(self, plan_factory=sample_plan, failure=False, revision=False):
        self.plan_factory = plan_factory
        self.failure = failure
        self.revision = revision
        self.calls = []

    def propose(self, data, original):
        self.calls.append({"page": data.number, "stage": "propose"})
        if self.failure:
            raise AgentError("Simulated API failure.", fatal=True)
        return self.plan_factory(data)

    def review(self, data, original, corrected, applied, rejected):
        self.calls.append({"page": data.number, "stage": "review"})
        return PageReview(approved=not self.revision,
                          revised_plan=self.plan_factory(data) if self.revision else None,
                          warnings=[])
