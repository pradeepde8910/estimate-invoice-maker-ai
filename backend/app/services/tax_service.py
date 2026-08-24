from decimal import Decimal, ROUND_HALF_UP

class TaxResult:
    def __init__(self, cgst: Decimal = Decimal('0.00'), sgst: Decimal = Decimal('0.00'), igst: Decimal = Decimal('0.00'), total_gst: Decimal = Decimal('0.00')):
        self.cgst = cgst
        self.sgst = sgst
        self.igst = igst
        self.total_gst = total_gst

def calculate_gst(seller_state: str, buyer_state: str, taxable_amount: Decimal, gst_rate: Decimal) -> TaxResult:
    """
    Calculates GST cleanly splitting CGST/SGST if intra-state, or IGST if inter-state.
    """
    taxable_amount = Decimal(str(taxable_amount))
    gst_rate = Decimal(str(gst_rate))
    
    is_intra_state = seller_state.strip().lower() == buyer_state.strip().lower()
    
    total_gst = (taxable_amount * (gst_rate / Decimal('100.0'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    if is_intra_state:
        half_rate = gst_rate / Decimal('2.0')
        cgst = (taxable_amount * (half_rate / Decimal('100.0'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        sgst = (taxable_amount * (half_rate / Decimal('100.0'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        # Ensure CGST + SGST matches total_gst mathematically despite rounding
        sgst = total_gst - cgst 
        return TaxResult(cgst=cgst, sgst=sgst, total_gst=total_gst)
    else:
        return TaxResult(igst=total_gst, total_gst=total_gst)

def calculate_tds(taxable_base_amount: Decimal, tds_rate: Decimal) -> Decimal:
    """
    Calculates TDS.
    Per company accounting rule: TDS is deducted from the taxable base (Subtotal), not the gross invoice value.
    """
    taxable_base_amount = Decimal(str(taxable_base_amount))
    tds_rate = Decimal(str(tds_rate))
    
    tds_amount = (taxable_base_amount * (tds_rate / Decimal('100.0'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return tds_amount

from typing import List, Dict

class TaxBucket:
    def __init__(self, gst_rate: Decimal, taxable_amount: Decimal):
        self.gst_rate = gst_rate
        self.taxable_amount = taxable_amount
        self.cgst = Decimal('0.00')
        self.sgst = Decimal('0.00')
        self.igst = Decimal('0.00')
        self.total_gst = Decimal('0.00')

def calculate_taxes_by_bucket(seller_state: str, buyer_state: str, items: List[Dict]) -> List[TaxBucket]:
    """
    Groups items by their gst_rate and calculates tax per bucket.
    `items` is expected to be a list of dicts like:
    [{"amount": Decimal, "gst_rate": Decimal}, ...]
    """
    buckets: Dict[Decimal, Decimal] = {}
    
    for item in items:
        rate = item["gst_rate"]
        amt = item["amount"]
        if rate not in buckets:
            buckets[rate] = Decimal('0.00')
        buckets[rate] += amt
        
    result_buckets = []
    for rate, amount in buckets.items():
        tax_res = calculate_gst(seller_state, buyer_state, amount, rate)
        bucket = TaxBucket(rate, amount)
        bucket.cgst = tax_res.cgst
        bucket.sgst = tax_res.sgst
        bucket.igst = tax_res.igst
        bucket.total_gst = tax_res.total_gst
        result_buckets.append(bucket)
        
    return result_buckets
