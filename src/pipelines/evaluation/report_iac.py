from enum import Enum
from dataclasses import dataclass, field
from typing import Dict

class CreditType(str, Enum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    NONE = "NONE"
    CONTRADICTED = "CONTRADICTED"

@dataclass
class ComponentScore:
    credit_type: CreditType # full / partial / none / contradicted
    max_cost: float
    partial_credit: float
    evaluated_fact: str | None = None  # Human-readable description of the candidate fact that was scored
    ground_truth_fact: str | None = None  # Human-readable description of the expected ground truth fact

    cost_saved: float = field(init=False)
    omission_cost: float = field(init=False)
    misinformation_cost: float = field(init=False)

    def __post_init__(self):
        if self.credit_type == CreditType.FULL:
            self.cost_saved = self.max_cost
            self.omission_cost = 0
            self.misinformation_cost = 0
        elif self.credit_type == CreditType.PARTIAL:
            self.cost_saved = self.max_cost * self.partial_credit
            self.omission_cost = self.max_cost * (1 - self.partial_credit)
            self.misinformation_cost = 0
        elif self.credit_type == CreditType.NONE:
            self.cost_saved = 0
            self.omission_cost = self.max_cost
            self.misinformation_cost = 0
        elif self.credit_type == CreditType.CONTRADICTED:
            self.cost_saved = 0
            self.omission_cost = self.max_cost
            self.misinformation_cost = 0
            
@dataclass
class EntityScore:
    location_score: ComponentScore
    need_score: ComponentScore
    resource_score: ComponentScore

    def __post_init__(self):
        components = [self.location_score, self.need_score, self.resource_score]
        self.omission_cost = sum([score.omission_cost for score in components])
        self.misinformation_cost = sum([score.misinformation_cost for score in components])
        self.total_cost_saved = sum([score.cost_saved for score in components])

@dataclass
class IACResult:
    entity_scores: Dict[str, EntityScore]
    misinformation_multiplier: float # misinformation penalty weight, passed from CostConfig
    distraction_cost: float = 0.0
    misinformation_cost: float = 0.0
    misinformation_count: int = 0

    # Derived aggregates
    total_cost_saved: float = field(init=False)
    omission_cost: float = field(init=False)
    combined_cost: float = field(init=False)
    soft_recall: float = field(init=False)
    soft_precision: float = field(init=False)
    soft_f1: float = field(init=False)


    def __post_init__(self):
        self.omission_cost = sum([score.omission_cost for score in self.entity_scores.values()])
        self.total_cost_saved = sum([score.total_cost_saved for score in self.entity_scores.values()])
        self.combined_cost = self.omission_cost + self.misinformation_multiplier * self.misinformation_cost + self.distraction_cost
        
        # Calculate soft metrics (slot-based unweighted precision & recall)
        total_credit = sum(
            comp.partial_credit 
            for score in self.entity_scores.values() 
            for comp in [score.location_score, score.need_score, score.resource_score]
        )
        total_slots = len(self.entity_scores) * 3
        self.soft_recall = total_credit / total_slots if total_slots > 0 else 0.0
        self.soft_precision = total_credit / (total_credit + self.misinformation_count) if (total_credit + self.misinformation_count) > 0 else 0.0
        
        if self.soft_precision + self.soft_recall > 0:
            self.soft_f1 = 2 * (self.soft_precision * self.soft_recall) / (self.soft_precision + self.soft_recall)
        else:
            self.soft_f1 = 0.0