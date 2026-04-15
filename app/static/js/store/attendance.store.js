import { Store } from "../core/store.js";

class AttendanceStore extends Store {
  constructor() {
    super({
      today: {
        check_in: null,
        check_out: null,
        working_hours: 0,
        status: null,
      },
      history: [],
      loading: false,
    });
  }

  setToday(data) {
    this.setState({
      today: {
        ...this.state.today,
        ...data,
      },
    });
  }

  setHistory(list) {
    this.setState({
      history: list,
    });
  }

  setLoading(status) {
    this.setState({
      loading: status,
    });
  }

  getToday() {
    return this.state.today;
  }
}

export const attendanceStore = new AttendanceStore();