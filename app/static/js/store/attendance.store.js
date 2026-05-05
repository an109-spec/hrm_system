import { Store } from "../core/store.js";
const initialState = {
  today: {
    id: null,
    date: null,
    check_in: null,
    check_out: null,
    overtime_check_in: null,
    overtime_check_out: null,
    regular_hours: 0,
    overtime_hours: 0,
    working_hours: 0,
    shift_status: "not_started",
    shift_status_label: "Chưa chấm công",
    attendance_type: "normal",
    attendance_type_label: "Ngày thường",
    late_minutes: 0,
    is_half_day: false,
    is_weekend: false,
    is_holiday: false,
  },
  history: [],
  ui: {
    loading: false,
    submitting: false,
    scannerOpen: false,
    lastError: null,
  },
  flow: {
    lastAction: null,
    lastMessage: null,
    responseType: "success",
    requiresConfirmation: false,
    requiresOvertimeDecision: false,
    nextEvent: null,
  },
};

function toNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function normalizeTodayPayload(payload = {}) {
  return {
    ...initialState.today,
    ...payload,
    regular_hours: toNumber(payload.regular_hours, 0),
    overtime_hours: toNumber(payload.overtime_hours, 0),
    working_hours: toNumber(payload.working_hours, 0),
    late_minutes: toNumber(payload.late_minutes, 0),
    is_half_day: Boolean(payload.is_half_day),
    is_weekend: Boolean(payload.is_weekend),
    is_holiday: Boolean(payload.is_holiday),
    shift_status: payload.shift_status || payload.attendance_state || "not_started",
    shift_status_label: payload.shift_status_label || "Chưa chấm công",
    attendance_type: payload.attendance_type || "normal",
    attendance_type_label: payload.attendance_type_label || "Ngày thường",
  };
}

class AttendanceStore extends Store {
  constructor() {
    super(initialState);
  }

  reset() {
    this.setState({ ...initialState });
  }

  setToday(data = {}) {
    this.setState({
      today: normalizeTodayPayload({
        ...this.state.today,
        ...data,
      }),
    });
  }

  setHistory(list = []) {
    this.setState({
      history: list.map((item) => normalizeTodayPayload(item)),
    });
  }

  setLoading(status) {
    this.setState({
      ui: {
        ...this.state.ui,
        loading: Boolean(status),
      },
    });
  }

  setSubmitting(status) {
    this.setState({
      ui: {
        ...this.state.ui,
        submitting: Boolean(status),
      },
    });
  }

  setScannerOpen(status) {
    this.setState({
      ui: {
        ...this.state.ui,
        scannerOpen: Boolean(status),
      },
    });
  }

  setError(message = null) {
    this.setState({
      ui: {
        ...this.state.ui,
        lastError: message,
      },
    });
  }

  setFlow(meta = {}) {
    this.setState({
      flow: {
        ...this.state.flow,
        ...meta,
      },
    });
  }
  applyActionResult(result = {}) {
    const action = result.action || null;
    const payload = result.data || result;

    this.setFlow({
      lastAction: action,
      lastMessage: result.message || payload.message || null,
      responseType: result.type || "success",
      requiresConfirmation: Boolean(payload.requires_confirmation),
      requiresOvertimeDecision: Boolean(payload.requires_overtime_decision),
      nextEvent: payload.next_event || null,
    });

    if (payload && (payload.shift_status || payload.attendance_state || payload.check_in || payload.check_out)) {
      this.setToday(payload);
    }
  }
  getToday() {
    return this.state.today;
  }
}

export const attendanceStore = new AttendanceStore();