import { Store } from "../core/store.js";

class EmployeeStore extends Store {
  constructor() {
    super({
      profile: null,
      department: null,
      position: null,
      manager: null,
      loading: false,
    });
  }

  setProfile(data) {
    this.setState({
      profile: data,
    });
  }

  setOrganization(data) {
    this.setState({
      department: data.department,
      position: data.position,
      manager: data.manager,
    });
  }

  updateField(key, value) {
    this.setState({
      profile: {
        ...this.state.profile,
        [key]: value,
      },
    });
  }

  setLoading(status) {
    this.setState({
      loading: status,
    });
  }

  getProfile() {
    return this.state.profile;
  }
}

export const employeeStore = new EmployeeStore();