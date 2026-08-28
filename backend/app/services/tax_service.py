from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional
import re

# Standard 2-digit Indian GST State / Union Territory Codes
GST_STATE_CODES: Dict[str, str] = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
}

# Major cities/keywords mapped to their respective states
STATE_KEYWORDS: Dict[str, str] = {
    "tamil nadu": "Tamil Nadu",
    "tamilnadu": "Tamil Nadu",
    "chennai": "Tamil Nadu",
    "coimbatore": "Tamil Nadu",
    "madurai": "Tamil Nadu",
    "tiruchirappalli": "Tamil Nadu",
    "trichy": "Tamil Nadu",
    "salem": "Tamil Nadu",
    "karnataka": "Karnataka",
    "bangalore": "Karnataka",
    "bengaluru": "Karnataka",
    "mysore": "Karnataka",
    "mysuru": "Karnataka",
    "hubli": "Karnataka",
    "maharashtra": "Maharashtra",
    "mumbai": "Maharashtra",
    "pune": "Maharashtra",
    "nagpur": "Maharashtra",
    "thane": "Maharashtra",
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "uttar pradesh": "Uttar Pradesh",
    "noida": "Uttar Pradesh",
    "greater noida": "Uttar Pradesh",
    "lucknow": "Uttar Pradesh",
    "kanpur": "Uttar Pradesh",
    "ghaziabad": "Uttar Pradesh",
    "varanasi": "Uttar Pradesh",
    "agra": "Uttar Pradesh",
    "telangana": "Telangana",
    "hyderabad": "Telangana",
    "secunderabad": "Telangana",
    "andhra pradesh": "Andhra Pradesh",
    "visakhapatnam": "Andhra Pradesh",
    "vizag": "Andhra Pradesh",
    "vijayawada": "Andhra Pradesh",
    "kerala": "Kerala",
    "kochi": "Kerala",
    "cochin": "Kerala",
    "thiruvananthapuram": "Kerala",
    "trivandrum": "Kerala",
    "calicut": "Kerala",
    "kozhikode": "Kerala",
    "gujarat": "Gujarat",
    "ahmedabad": "Gujarat",
    "surat": "Gujarat",
    "vadodara": "Gujarat",
    "haryana": "Haryana",
    "gurgaon": "Haryana",
    "gurugram": "Haryana",
    "faridabad": "Haryana",
    "west bengal": "West Bengal",
    "kolkata": "West Bengal",
    "calcutta": "West Bengal",
    "rajasthan": "Rajasthan",
    "jaipur": "Rajasthan",
    "punjab": "Punjab",
    "chandigarh": "Chandigarh",
    "bihar": "Bihar",
    "patna": "Bihar",
    "odisha": "Odisha",
    "bhubaneswar": "Odisha",
    "madhya pradesh": "Madhya Pradesh",
    "indore": "Madhya Pradesh",
    "bhopal": "Madhya Pradesh",
}


def resolve_state(gstin: Optional[str] = None, address: Optional[str] = None, default_state: str = "Tamil Nadu") -> str:
    """
    Resolves the canonical Indian State for GST calculation:
    1. First checks GSTIN prefix (first 2 digits correspond to state code in GSTIN).
    2. If GSTIN is absent/unregistered, extracts state name or city keyword from address text.
    3. Falls back to default_state (e.g. "Tamil Nadu").
    """
    if gstin:
        clean_gstin = re.sub(r"[^0-9A-Za-z]", "", str(gstin).strip())
        if len(clean_gstin) >= 2 and clean_gstin[:2] in GST_STATE_CODES:
            return GST_STATE_CODES[clean_gstin[:2]]

    if address:
        addr_lower = str(address).lower()
        for kw, state_name in STATE_KEYWORDS.items():
            if re.search(r"\b" + re.escape(kw) + r"\b", addr_lower):
                return state_name

        for code, state_name in GST_STATE_CODES.items():
            if state_name.lower() in addr_lower:
                return state_name

    return default_state


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
    
    seller_canonical = resolve_state(address=seller_state, default_state="Tamil Nadu") if seller_state else "Tamil Nadu"
    buyer_canonical = resolve_state(address=buyer_state, default_state="Tamil Nadu") if buyer_state else "Tamil Nadu"

    is_intra_state = seller_canonical.lower() == buyer_canonical.lower()
    
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

