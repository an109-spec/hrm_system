class UpdateProfileDTO:
    def __init__(self, data):
        self.full_name = data.get("full_name")
        self.phone = data.get("phone")
        self.address = data.get("address")


class ChangePasswordDTO:
    def __init__(self, data):
        self.current_password = data.get("current_password")
        self.new_password = data.get("new_password")
        self.confirm_password = data.get("confirm_password")