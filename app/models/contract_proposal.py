from app.models.base import BaseModel, db


class ContractProposal(BaseModel):
    __tablename__ = "contract_proposals"

    contract_id = db.Column(db.Integer, db.ForeignKey("contracts.id"), nullable=False, index=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    manager_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)

    proposal_type = db.Column(db.String(50), nullable=False)  # renewal, termination, probation_conversion
    status = db.Column(db.String(30), nullable=False, default="pending_hr", server_default="pending_hr")
    proposed_date = db.Column(db.Date, nullable=True)
    proposed_duration_months = db.Column(db.Integer, nullable=True)
    reason = db.Column(db.Text, nullable=False)
    professional_note = db.Column(db.Text, nullable=True)
    hr_feedback = db.Column(db.Text, nullable=True)
    admin_feedback = db.Column(db.Text, nullable=True)