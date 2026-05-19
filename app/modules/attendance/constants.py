class AttendanceAction:
    ACTION_CHECK_IN = "check_in"                          # Điểm danh vào ca chính
    ACTION_CHECK_OUT = "check_out"                        # Điểm danh ra ca chính
    ACTION_CHECK_IN_OT = "check_in_overtime"              # Điểm danh vào ca tăng ca (OT)
    ACTION_CHECK_OUT_OT = "check_out_overtime"            # Điểm danh ra ca tăng ca (OT)

    ACTION_HOLIDAY_WORK_PROMPT = "holiday_work_prompt"    # Gợi ý/Hỏi xác nhận đi làm vào ngày lễ
    ACTION_WEEKEND_WORK_PROMPT = "weekend_work_prompt"    # Gợi ý/Hỏi xác nhận đi làm vào ngày cuối tuần
    ACTION_EARLY_CHECKOUT_PROMPT = "early_checkout_prompt" # Gợi ý/Cảnh báo khi nhân viên check-out sớm hơn giờ quy định
    ACTION_OFFER_OVERTIME = "offer_overtime"              # Gợi ý/Hỏi nhân viên có muốn đăng ký tăng ca không (khi hết ca chính)

    ACTION_ALREADY_RECORDED = "already_recorded"          # Dữ liệu điểm danh ngày hôm nay đã được ghi nhận trước đó (trùng lặp)
    ACTION_OVERTIME_REQUEST_CREATED = "overtime_request_created" # Đã tạo yêu cầu/đơn đăng ký tăng ca thành công
    ACTION_COMPLETE_WITHOUT_OT = "complete_without_overtime"     # Hoàn thành ngày làm việc bình thường, không đăng ký tăng ca
    ACTION_HOLIDAY_OFF = "holiday_off"                    # Ghi nhận nghỉ ngày lễ (hưởng nguyên lương, không cần điểm danh)
    ACTION_WEEKEND_OFF = "weekend_off"                    # Ghi nhận nghỉ cuối tuần (không tính công, không cần điểm danh)
    ACTION_OVERTIME_DECISION_RECORDED = "overtime_decision_recorded" # Đã ghi nhận quyết định xử lý tăng ca (Đồng ý/Từ chối từ Quản lý)