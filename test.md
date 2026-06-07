def _get_holiday_lookup() -> dict[str, str]:
    now = get_current_time()
    current_year = now.year
    lookup = {}
    db_holidays = Holiday.query.filter(
        db.or_(
            Holiday.is_recurring.is_(True),
            db.extract('year', Holiday.date) == current_year
        )
    ).all()
    for holiday in db_holidays:
        key = holiday.date.strftime("%m-%d")
        lookup[key] = holiday.name
    for holiday_key, holiday_name in VN_FIXED_PUBLIC_HOLIDAYS.items():
        lookup.setdefault(holiday_key, holiday_name)
    lunar_holidays = OvertimeConfig.get_lunar_holidays(current_year)
    for holiday_key, holiday_name in lunar_holidays.items():
        lookup.setdefault(holiday_key, holiday_name)
    return lookup

    '''
    GỬI YÊU CẦU ĐIỀU CHỈNH HỢP ĐỒNG
    '''
    '''
    @staticmethod
    def request_contract_adjustment(
        manager_id: int,
        contract_id: int,
        reason: str,
        proposed_duration_months: int = None,
        proposed_end_date: date = None,
        professional_note: str = None
    ) -> dict:
        # 1. Kiểm tra tồn tại
        contract = Contract.query.filter_by(id=contract_id, is_deleted=False).first()
        if not contract:
            raise ValueError("Không tìm thấy hợp đồng")
        
        # 2. TẬN DỤNG hàm kiểm tra quyền dùng chung
        # Lưu ý: Hàm này sẽ raise PermissionError nếu manager không có quyền
        Manager_Contract_Service._validate_manager_access(manager_id, contract.employee_id)

        # 3. Validate dữ liệu
        if not reason or not reason.strip():
            raise ValueError("Lý do điều chỉnh là bắt buộc")

        # Lấy nhãn hiển thị từ hằng số
        proposal_label = ProposalType.get_label(ProposalType.ADJUSTMENT)

        # 4. Tạo đề xuất điều chỉnh
        proposal = ContractProposal(
            contract_id=contract.id,
            employee_id=contract.employee_id,
            manager_id=manager_id,
            proposal_type=ProposalType.ADJUSTMENT, # SỬ DỤNG HẰNG SỐ
            reason=reason.strip(),
            proposed_duration_months=proposed_duration_months,
            proposed_end_date=proposed_end_date,
            professional_note=professional_note.strip() if professional_note else None,
            status="pending_hr",
        )
        db.session.add(proposal)
        db.session.flush()

        # 5. Ghi log lịch sử
        HistoryService.log_event(
            action="MANAGER_ADJUSTMENT_REQUEST",
            employee_id=contract.employee_id,
            entity_type="contract_proposal",
            entity_id=proposal.id,
            description=f"Manager yêu cầu {proposal_label.lower()} hợp đồng #{contract.contract_code}",
            performed_by=manager_id
        )

        # 6. Gửi thông báo cho TẤT CẢ HR
        hr_users = User.query.join(Role).filter(Role.name == RoleName.HR).all()
        for hr_user in hr_users:
            NotificationService.create(NotificationDTO(
                user_id=hr_user.id,
                title=f"Yêu cầu {proposal_label} mới",
                content=f"Nhân viên {contract.employee.full_name} có yêu cầu {proposal_label.lower()}.",
                type=ProposalType.ADJUSTMENT,
                link=f"/hr/contracts/proposals/{proposal.id}",
                is_read=False
            ))

        db.session.commit()
        return {"id": proposal.id, "status": "success", "message": f"Đã gửi yêu cầu {proposal_label.lower()} đến HR"}
    '''