class Hr_Contract_service:
    @staticmethod
    def _latest_contract(employee_id: int) -> Contract | None:
        return (
            Contract.query.filter_by(employee_id=employee_id)
            .order_by(Contract.start_date.desc(), Contract.created_at.desc())
            .first()
        )

    @staticmethod
    def _contract_type_from_employee(employee: Employee | None) -> str:
        if not employee:
            return "official"
        mapping = {
            "probation": "trial",
            "permanent": "official",
            "intern": "internship",
            "contract": "seasonal",
        }
        return mapping.get((employee.employment_type or "").lower(), "official")
    
    @staticmethod
    def _status_and_days_left(contract: Contract, today: date | None = None) -> tuple[str, int | None]:
        current = today or date.today()

        if (contract.status or "").lower() == "terminated":
            days_left = (contract.end_date - current).days if contract.end_date else None
            return "terminated", days_left

        if not contract.end_date:
            return "active", None

        days_left = (contract.end_date - current).days
        if days_left < 0:
            return "expired", days_left
        if days_left < 30:
            return "expiring", days_left
        return "active", days_left

    @staticmethod
    def _status_label(status: str) -> str:
        labels = {
            "expiring": "Sắp hết hạn",
            "active": "Đang hiệu lực",
            "expired": "Đã hết hạn",
            "terminated": "Đã kết thúc",
        }
        return labels.get(status, status)

    @staticmethod
    def _contract_type_label(contract_type: str) -> str:
        labels = {
            "trial": "Thử việc",
            "official": "Chính thức",
            "internship": "Thực tập",
            "seasonal": "Thời vụ",
        }
        return labels.get(contract_type, contract_type)
    
    @staticmethod
    def _serialize_contract(contract: Contract, *, today: date | None = None) -> dict:
        employee = contract.employee
        contract_type = getattr(contract, "contract_type", None) or HRService._contract_type_from_employee(employee)
        status, days_left = HRService._status_and_days_left(contract, today=today)
        allowance = HRService._sum_allowance(employee.id) if employee else Decimal("0")

        return {
            "id": contract.id,
            "contract_code": contract.contract_code,
            "employee_id": employee.id if employee else None,
            "employee_code": f"EMP{employee.id:05d}" if employee else "--",
            "employee_name": employee.full_name if employee else "--",
            "department": employee.department.name if employee and employee.department else "--",
            "position": employee.position.job_title if employee and employee.position else "--",
            "contract_type": contract_type,
            "contract_type_label": HRService._contract_type_label(contract_type),
            "start_date": contract.start_date.isoformat() if contract.start_date else None,
            "end_date": contract.end_date.isoformat() if contract.end_date else None,
            "contract_status": status,
            "contract_status_label": HRService._status_label(status),
            "days_left": days_left,
            "basic_salary": float(contract.basic_salary or 0),
            "allowance": float(allowance),
            "note": getattr(contract, "note", None),
        }
    @staticmethod
    def get_filter_meta() -> dict:
        departments = Department.query.filter_by(is_deleted=False).order_by(Department.name.asc()).all()
        positions = Position.query.filter_by(is_deleted=False).order_by(Position.job_title.asc()).all()
        managers = (
            Employee.query.filter_by(is_deleted=False)
            .join(Position, Employee.position_id == Position.id, isouter=True)
            .order_by(Employee.full_name.asc())
            .all()
        )
        return {
            "departments": [{"id": d.id, "name": d.name} for d in departments],
            "positions": [{"id": p.id, "name": p.job_title} for p in positions],
            "managers": [{"id": m.id, "name": m.full_name} for m in managers],
            "contract_statuses": [
                {"value": "all", "label": "Tất cả"},
                {"value": "expiring", "label": "Sắp hết hạn"},
                {"value": "active", "label": "Đang hiệu lực"},
                {"value": "expired", "label": "Đã hết hạn"},
            ],
            "contract_types": [
                {"value": "all", "label": "Tất cả"},
                {"value": "trial", "label": "Thử việc"},
                {"value": "official", "label": "Chính thức"},
                {"value": "internship", "label": "Thực tập"},
                {"value": "seasonal", "label": "Thời vụ"},
            ],
        }
    @staticmethod
    def get_contracts(filters: ContractFilterDTO) -> dict:
        contracts = (
            Contract.query.join(Employee, Contract.employee_id == Employee.id)
            .filter(Employee.is_deleted.is_(False), Contract.is_deleted.is_(False))
            .order_by(Contract.start_date.desc(), Contract.id.desc())
            .all()
        )

        today = date.today()
        serialized = [HR_Manager_Service._serialize_contract(contract, today=today) for contract in contracts]

        if filters.search:
            keyword = filters.search.strip().lower()
            serialized = [
                row
                for row in serialized
                if keyword in (row.get("contract_code") or "").lower()
                or keyword in (row.get("employee_name") or "").lower()
                or keyword in (row.get("employee_code") or "").lower()
            ]

        contract_type = (filters.contract_type or "all").lower()
        if contract_type != "all":
            serialized = [row for row in serialized if (row.get("contract_type") or "").lower() == contract_type]

        contract_status = (filters.contract_status or "all").lower()
        if contract_status != "all":
            serialized = [row for row in serialized if (row.get("contract_status") or "").lower() == contract_status]

        summary = {
            "total": len(serialized),
            "expiring": sum(1 for row in serialized if row["contract_status"] == "expiring"),
            "active": sum(1 for row in serialized if row["contract_status"] == "active"),
            "expired": sum(1 for row in serialized if row["contract_status"] == "expired"),
        }
        return {"items": serialized, "summary": summary}

    @staticmethod
    def get_contract_detail(contract_id: int) -> dict:
        contract = Contract.query.filter_by(id=contract_id, is_deleted=False).first()
        if not contract:
            raise ValueError("Không tìm thấy hợp đồng")
        return HR_Manager_Service._serialize_contract(contract)

    @staticmethod
    def _generate_contract_code() -> str:
        year = datetime.utcnow().year
        prefix = f"HD{year}"
        latest_code = (
            Contract.query.filter(Contract.contract_code.like(f"{prefix}-%"))
            .order_by(Contract.id.desc())
            .with_entities(Contract.contract_code)
            .first()
        )
        seq = 1
        if latest_code and latest_code[0]:
            try:
                seq = int(str(latest_code[0]).split("-")[-1]) + 1
            except ValueError:
                seq = 1
        return f"{prefix}-{seq:03d}"
    
    @staticmethod
    def _validate_contract_type(contract_type: str | None) -> str:
        resolved = (contract_type or "official").lower()
        if resolved not in HRService.VALID_CONTRACT_TYPES:
            raise ValueError("Loại hợp đồng không hợp lệ")
        return resolved

    @staticmethod
    def create_contract(data: CreateContractDTO) -> Contract:
        employee = Employee.query.filter_by(id=data.employee_id, is_deleted=False).first()
        if not employee:
            raise ValueError("Không tìm thấy nhân viên để tạo hợp đồng")

        start_date = HRService._parse_date(data.start_date, "Ngày bắt đầu")
        end_date = HRService._parse_date(data.end_date, "Ngày kết thúc")
        if not start_date:
            raise ValueError("Ngày bắt đầu là bắt buộc")
        if end_date and end_date < start_date:
            raise ValueError("Ngày kết thúc phải sau ngày bắt đầu")

        active_contract = (
            Contract.query.filter_by(employee_id=data.employee_id, is_deleted=False)
            .filter(Contract.status == "active")
            .order_by(Contract.start_date.desc())
            .first()
        )
        if active_contract and (not active_contract.end_date or active_contract.end_date >= date.today()):
            raise ValueError("Nhân viên đang có hợp đồng hiệu lực. Vui lòng gia hạn/chỉnh sửa thay vì tạo mới")


        contract = Contract(
            employee_id=data.employee_id,
            contract_code=HRService._generate_contract_code(),
            basic_salary=Decimal(str(data.basic_salary or 0)),
            start_date=start_date,
            end_date=end_date,
            status="active",
        )

        contract_type = HRService._validate_contract_type(data.contract_type)
        if hasattr(contract, "contract_type"):
            setattr(contract, "contract_type", contract_type)

        if hasattr(contract, "note"):
            setattr(contract, "note", data.note)

        db.session.add(contract)
        db.session.commit()
        return contract

    @staticmethod
    def update_contract(contract_id: int, data: UpdateContractDTO) -> Contract:
        contract = Contract.query.filter_by(id=contract_id, is_deleted=False).first()
        if not contract:
            raise ValueError("Không tìm thấy hợp đồng")

        if data.basic_salary is not None:
            contract.basic_salary = Decimal(str(data.basic_salary))

        if data.start_date is not None:
            parsed_start = HRService._parse_date(data.start_date, "Ngày bắt đầu")
            if parsed_start is None:
                raise ValueError("Ngày bắt đầu là bắt buộc")
            contract.start_date = parsed_start

        if data.end_date is not None:
            contract.end_date = HRService._parse_date(data.end_date, "Ngày kết thúc")

        if contract.end_date and contract.start_date and contract.end_date < contract.start_date:
            raise ValueError("Ngày kết thúc phải sau ngày bắt đầu")

        if data.contract_type is not None and hasattr(contract, "contract_type"):
            setattr(contract, "contract_type", HRService._validate_contract_type(data.contract_type))

        if data.note is not None and hasattr(contract, "note"):
            setattr(contract, "note", data.note)

        if contract.end_date and contract.end_date < date.today() and contract.status == "active":
            contract.status = "expired"
        elif contract.status != "terminated":
            contract.status = "active"

        db.session.commit()
        return contract

    @staticmethod
    def extend_contract(contract_id: int, data: ExtendContractDTO) -> Contract:
        contract = Contract.query.filter_by(id=contract_id, is_deleted=False).first()
        if not contract:
            raise ValueError("Không tìm thấy hợp đồng")

        new_end_date = HRService._parse_date(data.end_date, "Ngày gia hạn")
        if not new_end_date:
            raise ValueError("Ngày gia hạn là bắt buộc")
        if new_end_date <= contract.start_date:
            raise ValueError("Ngày gia hạn phải sau ngày bắt đầu hợp đồng")

        contract.end_date = new_end_date
        contract.status = "active"
        if data.note is not None and hasattr(contract, "note"):
            setattr(contract, "note", data.note)

        db.session.commit()
        return contract
    @staticmethod
    def terminate_contract(contract_id: int, data: TerminateContractDTO) -> Contract:
        contract = Contract.query.filter_by(id=contract_id, is_deleted=False).first()
        if not contract:
            raise ValueError("Không tìm thấy hợp đồng")

        terminate_date = HRService._parse_date(data.end_date, "Ngày kết thúc") or date.today()
        if terminate_date < contract.start_date:
            raise ValueError("Ngày kết thúc không thể trước ngày bắt đầu")

        contract.end_date = terminate_date
        contract.status = "terminated"
        if data.note is not None and hasattr(contract, "note"):
            setattr(contract, "note", data.note)

        db.session.commit()
        return contract
    
    @staticmethod
    def get_contract_reminders() -> dict:
        today = date.today()
        week_later = today + timedelta(days=7)
        month_later = today + timedelta(days=30)

        reminders: list[dict] = []

        latest_by_employee: dict[int, Contract] = {}
        all_contracts = (
            Contract.query.join(Employee, Contract.employee_id == Employee.id)
            .filter(Employee.is_deleted.is_(False), Contract.is_deleted.is_(False))
            .order_by(Contract.employee_id.asc(), Contract.start_date.desc(), Contract.id.desc())
            .all()
        )
        for contract in all_contracts:
            latest_by_employee.setdefault(contract.employee_id, contract)

        employees = Employee.query.filter_by(is_deleted=False).order_by(Employee.full_name.asc()).all()
        for employee in employees:
            contract = latest_by_employee.get(employee.id)
            if not contract:
                reminders.append(
                    {
                        "level": "critical",
                        "type": "missing_contract",
                        "employee_id": employee.id,
                        "employee_code": f"EMP{employee.id:05d}",
                        "employee_name": employee.full_name,
                        "message": "Nhân viên chưa có hợp đồng",
                    }
                )
                continue

            status, days_left = HRService._status_and_days_left(contract, today=today)
            if status == "expired":
                reminders.append(
                    {
                        "level": "critical",
                        "type": "expired",
                        "contract_id": contract.id,
                        "employee_id": employee.id,
                        "employee_code": f"EMP{employee.id:05d}",
                        "employee_name": employee.full_name,
                        "message": "Hợp đồng đã quá hạn, cần xử lý ngay",
                        "days_left": days_left,
                    }
                )
                continue

            if contract.end_date and contract.end_date <= week_later:
                reminders.append(
                    {
                        "level": "warning",
                        "type": "expiring_7_days",
                        "contract_id": contract.id,
                        "employee_id": employee.id,
                        "employee_code": f"EMP{employee.id:05d}",
                        "employee_name": employee.full_name,
                        "message": f"Hợp đồng còn {max(days_left or 0, 0)} ngày sẽ hết hạn",
                        "days_left": days_left,
                    }
                )
            elif contract.end_date and contract.end_date <= month_later:
                reminders.append(
                    {
                        "level": "warning",
                        "type": "expiring_30_days",
                        "contract_id": contract.id,
                        "employee_id": employee.id,
                        "employee_code": f"EMP{employee.id:05d}",
                        "employee_name": employee.full_name,
                        "message": "Hợp đồng còn dưới 30 ngày sẽ hết hạn",
                        "days_left": days_left,
                    }
                )
            elif contract.end_date:
                reminders.append(
                    {
                        "level": "info",
                        "type": "normal",
                        "contract_id": contract.id,
                        "employee_id": employee.id,
                        "employee_code": f"EMP{employee.id:05d}",
                        "employee_name": employee.full_name,
                        "message": "Hợp đồng đang hiệu lực bình thường",
                        "days_left": days_left,
                    }
                )

        reminders.sort(
            key=lambda item: (
                {"critical": 0, "warning": 1, "info": 2}.get(item["level"], 3),
                item.get("days_left") if item.get("days_left") is not None else 10_000,
            )
        )

        return {
            "items": reminders,
            "summary": {
                "critical": sum(1 for item in reminders if item["level"] == "critical"),
                "warning": sum(1 for item in reminders if item["level"] == "warning"),
                "info": sum(1 for item in reminders if item["level"] == "info"),
            },
        }


    @staticmethod
    def update_account_status(data: AccountStatusDTO) -> User:
        employee = Employee.query.filter_by(id=data.employee_id, is_deleted=False).first()
        if not employee or not employee.user:
            raise ValueError("Nhân viên chưa có tài khoản đăng nhập")

        employee.user.is_active = data.is_active
        db.session.commit()
        return employee.user

    PAYROLL_STATUSES = {"draft", "pending_approval", "approved", "finalized", "locked", "complaint"}
