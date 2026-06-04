class UpdateProfileDTO:
    def __init__(self, data):
        self.full_name = data.get("full_name")
        self.phone = data.get("phone")
        self.gender = data.get("gender")
        self.dob = data.get("dob")
        
        self.address = data.get("address")
        self.province_id = data.get("province_id")
        self.district_id = data.get("district_id")
        self.ward_id = data.get("ward_id")
        self.address_detail = data.get("address_detail")

class ChangePasswordDTO:
    def __init__(self, data):
        self.current_password = data.get("current_password")
        self.new_password = data.get("new_password")
        self.confirm_password = data.get("confirm_password")