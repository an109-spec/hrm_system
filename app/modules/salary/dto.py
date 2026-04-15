from dataclasses import dataclass
from datetime import date


@dataclass
class SalaryQueryDTO:
    employee_id: int
    year: int


@dataclass
class SalaryComplaintDTO:
    employee_id: int
    salary_id: int
    type: str
    description: str
    evidence_url: str | None = None