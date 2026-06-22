from decimal import Decimal, ROUND_HALF_UP


class TaxRules:
    
    @staticmethod
    def tax_by_bracket(taxable_income: Decimal, brackets: list[dict]) -> Decimal:
        """Tính thuế TNCN theo phương pháp lũy tiến từng phần."""
        if taxable_income <= 0:
            return Decimal("0")
        selected = None
        for bracket in brackets:
            from_value = Decimal(str(bracket["from"]))
            to_value = Decimal(str(bracket["to"]))
            if from_value < taxable_income <= to_value:
                selected = bracket
                break
        if not selected:
            selected = brackets[-1]
        rate = Decimal(str(selected["rate_percent"])) / Decimal("100")
        quick_deduction = Decimal(str(selected["quick_deduction"]))
        tax = taxable_income * rate - quick_deduction
        return max(Decimal("0"), tax).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
