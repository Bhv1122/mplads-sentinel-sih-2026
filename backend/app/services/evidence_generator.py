"""
backend/app/services/evidence_generator.py
=============================================================================
Phase 8: Evidence Generator for the Explainability Service.
=============================================================================

Converts raw detector metrics into concise, factual, and auditable evidence
statements.

Strict Governance Constraints:
1. NEVER INVENT NUMBERS OR EXPLANATIONS: Every statement is deterministically
   derived from raw detector metrics, reference baselines, and database records.
2. PRESERVE NUMERICAL ACCURACY & APPROPRIATE ROUNDING: Numbers are formatted
   according to domain standards (Indian numbering, percentage points, multipliers),
   and raw unrounded values are retained for audit and frontend inspection.
3. REUSABLE FORMATTING FUNCTIONS:
   - format_currency
   - format_percentage
   - format_percentage_points
   - format_ratio
   - format_multiplier
   - format_dates / format_date
   - format_duration
   - format_score
"""

import re
import math
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Any, Optional, List, Tuple, Union

try:
    from app.schemas.explainability import EvidenceStatement
except ImportError:
    from backend.app.schemas.explainability import EvidenceStatement

logger = logging.getLogger(__name__)


# =============================================================================
# Numerical & String Parsing Helpers
# =============================================================================

def _clean_number_string(val_str: str) -> str:
    """Removes commas, currency signs, and surrounding whitespace."""
    s = val_str.strip().replace(",", "")
    s = re.sub(r"^[₹$€£\s]+", "", s)
    return s.strip()


def parse_numerical_value(val: Any) -> Tuple[Optional[float], Optional[str]]:
    """
    Parses numerical values and detects magnitude/currency units (e.g. crore, lakh).
    Returns (float_value, detected_unit).
    """
    if val is None:
        return None, None

    if isinstance(val, (int, float)):
        return float(val), None

    if isinstance(val, Decimal):
        return float(val), None

    if isinstance(val, str):
        cleaned = _clean_number_string(val)
        lower = cleaned.lower()

        # Check for crore / cr
        match_crore = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:crores?|cr)", lower)
        if match_crore:
            return float(match_crore.group(1)), "crore"

        # Check for lakh / lac / l
        match_lakh = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:lakhs?|lac|l)\b", lower)
        if match_lakh:
            return float(match_lakh.group(1)), "lakh"

        # Check for percentage
        match_pct = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", lower)
        if match_pct:
            return float(match_pct.group(1)), "%"

        # Plain number
        match_num = re.search(r"[-+]?[0-9]+(?:\.[0-9]+)?", lower)
        if match_num:
            return float(match_num.group(0)), None

    return None, None


# =============================================================================
# Reusable Formatting Functions
# =============================================================================

def format_currency(
    amount: Optional[Union[float, int, Decimal, str]],
    compact: bool = False,
    in_crores: bool = False,
    currency_symbol: str = "₹",
    decimals: int = 2,
) -> str:
    """
    Format an amount into standard Indian Rupee notation (Lakhs / Crores).

    Examples:
    - format_currency(25600000) -> "₹2,56,00,000.00"
    - format_currency(25600000, compact=True) -> "₹2.56 Cr"
    - format_currency(25600000, in_crores=True) -> "2.56 crore"
    """
    if amount is None:
        return "N/A"

    num, unit = parse_numerical_value(amount)
    if num is None:
        return "N/A"

    # If already parsed as crore or requested in_crores
    if unit == "crore" or in_crores:
        val_crore = num if unit == "crore" else num / 10_000_000.0
        # Format clean decimals
        if val_crore == int(val_crore):
            return f"{int(val_crore)} crore"
        val_str = f"{val_crore:.{decimals}f}".rstrip("0").rstrip(".")
        return f"{val_str} crore"

    if unit == "lakh":
        val_lakh = num
        if val_lakh == int(val_lakh):
            return f"{int(val_lakh)} lakh"
        val_str = f"{val_lakh:.{decimals}f}".rstrip("0").rstrip(".")
        return f"{val_str} lakh"

    abs_num = abs(num)
    sign = "-" if num < 0 else ""

    if compact:
        if abs_num >= 10_000_000:
            cr = abs_num / 10_000_000.0
            cr_str = f"{cr:.{decimals}f}".rstrip("0").rstrip(".")
            return f"{sign}{currency_symbol}{cr_str} Cr"
        elif abs_num >= 100_000:
            lakh = abs_num / 100_000.0
            lakh_str = f"{lakh:.{decimals}f}".rstrip("0").rstrip(".")
            return f"{sign}{currency_symbol}{lakh_str} L"
        elif abs_num >= 1_000:
            k = abs_num / 1_000.0
            k_str = f"{k:.{decimals}f}".rstrip("0").rstrip(".")
            return f"{sign}{currency_symbol}{k_str} K"

    # Indian Comma Notation (e.g. 2,56,00,000.00)
    integer_part = int(abs_num)
    decimal_part = f"{abs_num - integer_part:.{decimals}f}"[1:] if decimals > 0 else ""

    s = str(integer_part)
    if len(s) > 3:
        last3 = s[-3:]
        other = s[:-3]
        groups = []
        while len(other) > 2:
            groups.insert(0, other[-2:])
            other = other[:-2]
        if other:
            groups.insert(0, other)
        groups.append(last3)
        formatted_int = ",".join(groups)
    else:
        formatted_int = s

    return f"{sign}{currency_symbol}{formatted_int}{decimal_part}"


def format_percentage(
    value: Optional[Union[float, int, Decimal, str]],
    decimals: int = 0,
    include_symbol: bool = True,
    is_ratio: Optional[bool] = None,
) -> str:
    """
    Format a ratio or percentage into a clean percentage string.

    Examples:
    - format_percentage(0.94) -> "94%"
    - format_percentage(0.85) -> "85%"
    - format_percentage(82) -> "82%"
    - format_percentage(47.5, decimals=1) -> "47.5%"
    """
    if value is None:
        return "N/A"

    num, unit = parse_numerical_value(value)
    if num is None:
        return "N/A"

    # Determine if value is a 0.0-1.0 ratio
    if unit == "%":
        pct = num
    elif is_ratio is True:
        pct = num * 100.0
    elif is_ratio is False:
        pct = num
    elif 0.0 < abs(num) <= 1.0:
        pct = num * 100.0
    else:
        pct = num

    # Rounding
    rounded = round(pct, decimals) if decimals > 0 else round(pct)

    if decimals == 0:
        res = f"{int(rounded)}"
    else:
        res = f"{rounded:.{decimals}f}"

    if include_symbol:
        return f"{res}%"
    return res


def format_percentage_points(
    difference: Optional[Union[float, int, Decimal, str]],
    decimals: int = 0,
    signed: bool = False,
) -> str:
    """
    Format an absolute difference between percentages as 'percentage points'.

    Examples:
    - format_percentage_points(47) -> "47 percentage points"
    - format_percentage_points(1) -> "1 percentage point"
    - format_percentage_points(12.5, decimals=1) -> "12.5 percentage points"
    """
    if difference is None:
        return "N/A"

    num, _ = parse_numerical_value(difference)
    if num is None:
        return "N/A"

    val = abs(num)
    sign = ("+" if num > 0 else "-") if signed and num != 0 else ""

    rounded = round(val, decimals) if decimals > 0 else round(val)
    if decimals == 0 or rounded == int(rounded):
        val_str = f"{int(rounded)}"
    else:
        val_str = f"{rounded:.{decimals}f}".rstrip("0").rstrip(".")

    unit_name = "percentage point" if rounded == 1 else "percentage points"
    return f"{sign}{val_str} {unit_name}".strip()


def format_multiplier(
    multiplier: Optional[Union[float, int, Decimal, str]],
    decimals: int = 2,
) -> str:
    """
    Format a relative multiplier with the mathematical multiplication symbol '×'.

    Preserves exact user example: 2.56 -> "2.56×".

    Examples:
    - format_multiplier(2.56) -> "2.56×"
    - format_multiplier(2.0) -> "2×"
    - format_multiplier(1.35) -> "1.35×"
    """
    if multiplier is None:
        return "N/A"

    num, _ = parse_numerical_value(multiplier)
    if num is None:
        return "N/A"

    rounded = round(num, decimals)
    if rounded == int(rounded):
        return f"{int(rounded)}×"

    val_str = f"{rounded:.{decimals}f}".rstrip("0").rstrip(".")
    return f"{val_str}×"


def format_ratio(
    numerator: Optional[Union[float, int, Decimal, str]],
    denominator: Optional[Union[float, int, Decimal, str]],
    decimals: int = 2,
    style: str = "multiplier",
) -> str:
    """
    Calculate and format the ratio of numerator to denominator.

    Styles:
    - "multiplier": "2.56×"
    - "ratio": "2.56:1"
    """
    if numerator is None or denominator is None:
        return "N/A"

    num_val, _ = parse_numerical_value(numerator)
    den_val, _ = parse_numerical_value(denominator)

    if num_val is None or den_val is None or den_val == 0:
        return "N/A"

    ratio_val = num_val / den_val
    if style == "multiplier":
        return format_multiplier(ratio_val, decimals=decimals)

    rounded = round(ratio_val, decimals)
    val_str = f"{int(rounded)}" if rounded == int(rounded) else f"{rounded:.{decimals}f}".rstrip("0").rstrip(".")
    return f"{val_str}:1"


def format_duration(
    days: Optional[Union[float, int, str]],
    style: str = "days",
) -> str:
    """
    Format duration into days (or months/years if requested).

    Examples:
    - format_duration(210) -> "210 days"
    - format_duration(1) -> "1 day"
    """
    if days is None:
        return "N/A"

    num, _ = parse_numerical_value(days)
    if num is None:
        return "N/A"

    int_days = int(round(num))
    if style == "days":
        unit = "day" if abs(int_days) == 1 else "days"
        return f"{int_days} {unit}"

    # Auto style: convert to months/years if large
    if abs(int_days) >= 365:
        years = int_days // 365
        remaining_days = int_days % 365
        months = remaining_days // 30
        y_unit = "year" if years == 1 else "years"
        if months > 0:
            m_unit = "month" if months == 1 else "months"
            return f"{years} {y_unit}, {months} {m_unit}"
        return f"{years} {y_unit}"
    elif abs(int_days) >= 30:
        months = int_days // 30
        m_unit = "month" if months == 1 else "months"
        return f"{months} {m_unit}"

    unit = "day" if abs(int_days) == 1 else "days"
    return f"{int_days} {unit}"


def format_date(
    date_val: Optional[Union[str, datetime, date, Any]],
    format_str: str = "%Y-%m-%d",
) -> str:
    """
    Format date/datetime safely into standard string representation.
    """
    if date_val is None:
        return "N/A"

    if isinstance(date_val, (datetime, date)):
        return date_val.strftime(format_str)

    if isinstance(date_val, str):
        # Try parsing ISO format
        try:
            dt = datetime.fromisoformat(date_val.replace("Z", "+00:00"))
            return dt.strftime(format_str)
        except Exception:
            return date_val.strip()

    return str(date_val)


def format_score(
    score: Optional[Union[float, int, Decimal, str]],
    max_score: float = 100.0,
    decimals: int = 1,
    include_max: bool = False,
) -> str:
    """
    Format a detector or composite score.

    Examples:
    - format_score(78.4) -> "78.4"
    - format_score(78.4, include_max=True) -> "78.4/100"
    """
    if score is None:
        return "N/A"

    num, _ = parse_numerical_value(score)
    if num is None:
        return "N/A"

    rounded = round(num, decimals)
    if decimals == 0 or rounded == int(rounded):
        val_str = f"{int(rounded)}"
    else:
        val_str = f"{rounded:.{decimals}f}"

    if include_max:
        return f"{val_str}/{int(max_score)}"
    return val_str


# =============================================================================
# Evidence Generator
# =============================================================================

class EvidenceGenerator:
    """
    Translates raw detector metrics into concise, factual evidence statements.

    Strict Rule:
    NEVER invent numbers or explanations.
    All statements are directly computed from the passed metrics.
    """

    def __init__(self):
        pass

    # -------------------------------------------------------------------------
    # 1. Cost Anomaly Statement
    # -------------------------------------------------------------------------
    def generate_cost_statement(
        self,
        project_cost: Union[float, int, str],
        peer_median: Union[float, int, str],
        cost_unit: Optional[str] = None,
    ) -> EvidenceStatement:
        """
        Input:
            project_cost = 25.6 crore (or 256000000 or 25.6)
            peer_median = 10 crore (or 100000000 or 10)

        Output:
            "Cost is 2.56× peer median."
        """
        c_num, c_unit = parse_numerical_value(project_cost)
        m_num, m_unit = parse_numerical_value(peer_median)

        raw_values = {
            "project_cost": project_cost,
            "peer_median": peer_median,
            "parsed_cost": c_num,
            "parsed_peer_median": m_num,
            "cost_unit": cost_unit or c_unit or m_unit,
        }

        if c_num is None or m_num is None or m_num == 0:
            statement = f"Cost is {format_currency(c_num)}, peer median unavailable."
            return EvidenceStatement(
                statement=statement,
                raw_values=raw_values,
                metric_key="cost_multiplier",
                detector_name="cost_anomaly",
                formatted_evidence=statement,
            )

        # Normalize units if one was in crores and the other in raw INR
        eff_cost = c_num
        eff_median = m_num
        if c_unit == "crore" and (m_unit is None and eff_median > 10_000):
            eff_cost = eff_cost * 10_000_000.0
        elif m_unit == "crore" and (c_unit is None and eff_cost > 10_000):
            eff_median = eff_median * 10_000_000.0

        ratio = eff_cost / eff_median
        mult_str = format_multiplier(ratio, decimals=2)
        statement = f"Cost is {mult_str} peer median."

        raw_values["multiplier"] = round(ratio, 4)
        raw_values["effective_cost"] = eff_cost
        raw_values["effective_peer_median"] = eff_median

        return EvidenceStatement(
            statement=statement,
            raw_values=raw_values,
            metric_key="cost_multiplier",
            detector_name="cost_anomaly",
            formatted_evidence=statement,
        )

    def generate_cost_overrun_statement(
        self,
        expenditure: Union[float, int, str],
        sanctioned: Union[float, int, str],
        overrun_pct: Optional[Union[float, int, str]] = None,
    ) -> EvidenceStatement:
        """
        Generates statement regarding budget overrun vs legal sanction.
        """
        e_num, _ = parse_numerical_value(expenditure)
        s_num, _ = parse_numerical_value(sanctioned)

        if overrun_pct is not None:
            pct_num, _ = parse_numerical_value(overrun_pct)
        elif e_num is not None and s_num is not None and s_num > 0:
            pct_num = max(0.0, ((e_num - s_num) / s_num) * 100.0)
        else:
            pct_num = 0.0

        raw_values = {
            "expenditure": expenditure,
            "sanctioned_amount": sanctioned,
            "cost_overrun_pct": pct_num,
        }

        if pct_num is not None and pct_num > 0:
            pct_str = format_percentage(pct_num, decimals=1, is_ratio=False)
            statement = f"Expenditure exceeds sanctioned amount by {pct_str}."
        else:
            statement = "Expenditure is within approved sanction."

        return EvidenceStatement(
            statement=statement,
            raw_values=raw_values,
            metric_key="cost_overrun_pct",
            detector_name="cost_anomaly",
            formatted_evidence=statement,
        )

    # -------------------------------------------------------------------------
    # 2. Delay Statement
    # -------------------------------------------------------------------------
    def generate_delay_statement(
        self,
        delay_days: Union[float, int, str],
        planned_duration: Optional[Union[int, str]] = None,
        expected_completion: Optional[str] = None,
    ) -> EvidenceStatement:
        """
        Input:
            delay_days = 210

        Output:
            "Project is delayed by 210 days."
        """
        days_num, _ = parse_numerical_value(delay_days)
        raw_values = {
            "delay_days": delay_days,
            "parsed_delay_days": days_num,
            "planned_duration": planned_duration,
            "expected_completion": expected_completion,
        }

        if days_num is None:
            statement = "Project schedule delay status is unrecorded."
        elif days_num > 0:
            statement = f"Project is delayed by {format_duration(days_num)}."
        elif days_num == 0:
            statement = "Project is on schedule."
        else:
            statement = f"Project is ahead of schedule by {format_duration(abs(days_num))}."

        raw_values["is_delayed"] = bool(days_num and days_num > 0)

        return EvidenceStatement(
            statement=statement,
            raw_values=raw_values,
            metric_key="delay_days",
            detector_name="delay_detection",
            formatted_evidence=statement,
        )

    # -------------------------------------------------------------------------
    # 3. Financial / Physical Progress Statement
    # -------------------------------------------------------------------------
    def generate_progress_statement(
        self,
        financial_progress: Union[float, int, str],
        physical_progress: Union[float, int, str],
    ) -> EvidenceStatement:
        """
        Input:
            financial_progress = 82% (or 82 or 0.82)
            physical_progress = 35% (or 35 or 0.35)

        Output:
            "Financial progress exceeds physical progress by 47 percentage points."
        """
        fp_num, _ = parse_numerical_value(financial_progress)
        pp_num, _ = parse_numerical_value(physical_progress)

        # Normalize 0.0-1.0 to 0-100%
        if fp_num is not None and 0.0 < abs(fp_num) <= 1.0 and (pp_num is None or pp_num <= 1.0):
            fp_num = fp_num * 100.0
        if pp_num is not None and 0.0 < abs(pp_num) <= 1.0 and fp_num is not None and fp_num > 1.0:
            pp_num = pp_num * 100.0

        raw_values = {
            "financial_progress": financial_progress,
            "physical_progress": physical_progress,
            "parsed_financial_progress": fp_num,
            "parsed_physical_progress": pp_num,
        }

        if fp_num is None or pp_num is None:
            statement = "Progress alignment data is incomplete."
            return EvidenceStatement(
                statement=statement,
                raw_values=raw_values,
                metric_key="progress_gap",
                detector_name="progress_mismatch",
                formatted_evidence=statement,
            )

        gap = round(abs(fp_num - pp_num), 2)
        raw_values["progress_gap"] = gap
        gap_str = format_percentage_points(gap)

        if fp_num > pp_num:
            statement = f"Financial progress exceeds physical progress by {gap_str}."
            raw_values["direction"] = "financial_ahead"
        elif pp_num > fp_num:
            statement = f"Physical progress exceeds financial progress by {gap_str}."
            raw_values["direction"] = "physical_ahead"
        else:
            statement = "Financial progress matches physical progress."
            raw_values["direction"] = "aligned"

        return EvidenceStatement(
            statement=statement,
            raw_values=raw_values,
            metric_key="progress_gap",
            detector_name="progress_mismatch",
            formatted_evidence=statement,
        )

    # -------------------------------------------------------------------------
    # 4. Duplicate Detection Statement
    # -------------------------------------------------------------------------
    def generate_duplicate_statement(
        self,
        similarity_score: Union[float, int, str],
        threshold: Union[float, int, str],
        matched_project_id: str = "XYZ",
    ) -> EvidenceStatement:
        """
        Input:
            similarity_score = 0.94 (or 94%)
            threshold = 0.85 (or 85%)
            matched_project_id = "XYZ"

        Output:
            "Project description has 94% similarity with project XYZ, exceeding the 85% duplicate threshold."
        """
        sim_num, _ = parse_numerical_value(similarity_score)
        thr_num, _ = parse_numerical_value(threshold)

        # Normalize to 0-1 ratio if needed
        eff_sim = (sim_num / 100.0) if (sim_num is not None and sim_num > 1.0) else sim_num
        eff_thr = (thr_num / 100.0) if (thr_num is not None and thr_num > 1.0) else thr_num

        raw_values = {
            "similarity_score": similarity_score,
            "threshold": threshold,
            "matched_project_id": matched_project_id,
            "parsed_similarity": eff_sim,
            "parsed_threshold": eff_thr,
        }

        if eff_sim is None:
            statement = "No text similarity detected."
            return EvidenceStatement(
                statement=statement,
                raw_values=raw_values,
                metric_key="similarity_score",
                detector_name="duplicate_detection",
                formatted_evidence=statement,
            )

        sim_str = format_percentage(eff_sim, decimals=0, is_ratio=True)
        thr_str = format_percentage(eff_thr, decimals=0, is_ratio=True) if eff_thr is not None else "threshold"

        exceeds = eff_thr is not None and eff_sim >= eff_thr
        raw_values["exceeds_threshold"] = exceeds

        if exceeds:
            statement = (
                f"Project description has {sim_str} similarity with project {matched_project_id}, "
                f"exceeding the {thr_str} duplicate threshold."
            )
        elif eff_thr is not None:
            statement = (
                f"Project description has {sim_str} similarity with project {matched_project_id}, "
                f"within the {thr_str} duplicate threshold."
            )
        else:
            statement = f"Project description has {sim_str} similarity with project {matched_project_id}."

        return EvidenceStatement(
            statement=statement,
            raw_values=raw_values,
            metric_key="similarity_score",
            detector_name="duplicate_detection",
            formatted_evidence=statement,
        )

    # -------------------------------------------------------------------------
    # 5. Agency Pattern Statement
    # -------------------------------------------------------------------------
    def generate_agency_statement(
        self,
        agency_name: str,
        projects_analyzed: int,
        delay_rate: Union[float, int, str],
        benchmark: Union[float, int, str] = 0.25,
        insufficient_history: bool = False,
    ) -> EvidenceStatement:
        """
        Generates factual statement regarding historical agency track record.
        """
        dr_num, _ = parse_numerical_value(delay_rate)
        bm_num, _ = parse_numerical_value(benchmark)

        eff_dr = (dr_num / 100.0) if (dr_num is not None and dr_num > 1.0) else dr_num
        eff_bm = (bm_num / 100.0) if (bm_num is not None and bm_num > 1.0) else bm_num

        raw_values = {
            "agency_name": agency_name,
            "projects_analyzed": projects_analyzed,
            "delay_rate": delay_rate,
            "benchmark": benchmark,
            "insufficient_history": insufficient_history,
            "parsed_delay_rate": eff_dr,
            "parsed_benchmark": eff_bm,
        }

        if insufficient_history or projects_analyzed < 3:
            statement = (
                f"Implementing agency {agency_name} has only {projects_analyzed} historical "
                f"projects recorded (minimum 3 required for statistical pattern analysis)."
            )
        else:
            rate_str = format_percentage(eff_dr, decimals=0, is_ratio=True)
            bench_str = format_percentage(eff_bm, decimals=0, is_ratio=True)
            exceeds = eff_bm is not None and eff_dr > eff_bm
            raw_values["exceeds_benchmark"] = exceeds

            proj_term = "project" if projects_analyzed == 1 else "projects"
            if exceeds:
                statement = (
                    f"Implementing agency {agency_name} has a {rate_str} historical delay rate "
                    f"across {projects_analyzed} {proj_term}, exceeding the {bench_str} benchmark."
                )
            else:
                statement = (
                    f"Implementing agency {agency_name} has a {rate_str} historical delay rate "
                    f"across {projects_analyzed} {proj_term}, within the {bench_str} benchmark."
                )

        return EvidenceStatement(
            statement=statement,
            raw_values=raw_values,
            metric_key="agency_delay_rate",
            detector_name="agency_pattern",
            formatted_evidence=statement,
        )

    # -------------------------------------------------------------------------
    # Dispatcher: Generate from Detector Dictionary
    # -------------------------------------------------------------------------
    def generate_statements_from_detector(
        self,
        detector_name: str,
        det_data: Dict[str, Any],
    ) -> List[EvidenceStatement]:
        """
        Extracts raw metrics from a detector result payload and generates
        all applicable EvidenceStatement instances.
        """
        details = det_data.get("details", {}) if det_data else {}
        statements: List[EvidenceStatement] = []

        if detector_name == "cost_anomaly":
            cost = details.get("evaluated_cost", details.get("project_expenditure", 0.0))
            median = details.get("peer_median", 0.0)
            if cost and median:
                statements.append(self.generate_cost_statement(cost, median))

            sanctioned = details.get("sanctioned_amount", 0.0)
            overrun = details.get("cost_overrun_pct")
            if sanctioned and (overrun or cost > sanctioned):
                statements.append(self.generate_cost_overrun_statement(cost, sanctioned, overrun))

        elif detector_name == "delay_detection":
            days = details.get("overdue_days", details.get("delay_days", 0))
            planned = details.get("planned_duration")
            exp_date = details.get("expected_completion_date")
            statements.append(self.generate_delay_statement(days, planned, exp_date))

        elif detector_name == "progress_mismatch":
            fp = details.get("financial_progress", 0.0)
            pp = details.get("physical_progress", 0.0)
            statements.append(self.generate_progress_statement(fp, pp))

        elif detector_name == "duplicate_detection":
            sim = details.get("similarity", details.get("raw_similarity", 0.0))
            matched_id = details.get("matched_project_id", "XYZ")
            threshold = details.get("threshold", 0.85 if sim >= 0.85 else 0.60)
            statements.append(self.generate_duplicate_statement(sim, threshold, matched_id))

        elif detector_name == "agency_pattern":
            agency = details.get("agency_name", "Implementing Agency")
            count = details.get("projects_analyzed", 0)
            dr = details.get("delay_rate", 0.0)
            insufficient = details.get("insufficient_history", count < 3)
            statements.append(
                self.generate_agency_statement(
                    agency_name=agency,
                    projects_analyzed=count,
                    delay_rate=dr,
                    insufficient_history=insufficient,
                )
            )

        return statements


# Global default instance
evidence_generator = EvidenceGenerator()
