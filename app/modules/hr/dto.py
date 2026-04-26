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


@dataclass
class PayrollFilterDTO:
    search: Optional[str] = None
    department_id: Optional[int] = None
    status: Optional[str] = None
    month: Optional[int] = None
    year: Optional[int] = None


@dataclass
class PayrollCalculationDTO:
    month: int
    year: int
    department_id: Optional[int] = None


@dataclass
class PayrollAdjustmentDTO:
    fuel_allowance: float = 0
    meal_allowance: float = 0
    responsibility_allowance: float = 0
    other_allowance: float = 0
    late_penalty: float = 0
    early_penalty: float = 0
    unpaid_leave_penalty: float = 0
    other_penalty: float = 0
    note: Optional[str] = None


@dataclass
class PayrollApprovalDTO:
    action: str
    note: Optional[str] = None


@dataclass
class PayrollExportDTO:
    month: int
    year: int
    export_scope: str = "company"
    department_id: Optional[int] = None
    export_format: str = "excel"


@dataclass
class PayrollComplaintHandleDTO:
    complaint_id: int
    action: str
    message: Optional[str] = None
    payroll_status: Optional[str] = None


@dataclass
class AttendanceFilterDTO:
    search: Optional[str] = None
    department_id: Optional[int] = None
    status: Optional[str] = "all"
    month: Optional[int] = None
    year: Optional[int] = None
    shift_type: Optional[str] = "all"


@dataclass
class AttendanceAdjustmentDTO:
    attendance_id: int
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    status: Optional[str] = None
    note: Optional[str] = None


@dataclass
class OvertimeApprovalDTO:
    attendance_id: int
    action: str
    note: Optional[str] = None


@dataclass
class AttendanceExportDTO:
    month: int
    year: int
    export_scope: str = "company"
    department_id: Optional[int] = None
    export_format: str = "excel"


@dataclass
class AbnormalAttendanceResolveDTO:
    attendance_id: int
    action: str
    note: Optional[str] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    status: Optional[str] = None