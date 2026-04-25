from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class EmployeeFilterDTO:
    search: Optional[str] = None
    department_id: Optional[int] = None
    position_id: Optional[int] = None
    working_status: Optional[str] = None

@dataclass
class ContractFilterDTO:
    search: Optional[str] = None
    contract_status: Optional[str] = "all"
    contract_type: Optional[str] = "all"

@dataclass
class CreateEmployeeDTO:
    full_name: str
    dob: str
    gender: str
    phone: str
    address: Optional[str] = None
    department_id: Optional[int] = None
    position_id: Optional[int] = None
    manager_id: Optional[int] = None
    hire_date: Optional[str] = None
    employment_type: str = "probation"
    working_status: str = "working"
    create_account: bool = False
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None


@dataclass
class UpdateEmployeeDTO:
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    department_id: Optional[int] = None
    position_id: Optional[int] = None
    manager_id: Optional[int] = None
    working_status: Optional[str] = None


@dataclass
class CreateContractDTO:
    employee_id: int
    basic_salary: float
    start_date: str
    end_date: Optional[str] = None
    contract_type: Optional[str] = None
    note: Optional[str] = None

@dataclass
class UpdateContractDTO:
    basic_salary: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    contract_type: Optional[str] = None
    note: Optional[str] = None


@dataclass
class ExtendContractDTO:
    end_date: str
    note: Optional[str] = None


@dataclass
class TerminateContractDTO:
    end_date: Optional[str] = None
    note: Optional[str] = None


@dataclass
class AccountStatusDTO:
    employee_id: int
    is_active: bool