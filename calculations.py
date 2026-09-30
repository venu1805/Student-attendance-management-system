"""
SmartAttend - Mathematical Calculation Engine for Attendance & Forecasting
"""
import math


def calculate_percentage(attended: int, conducted: int) -> float:
    """Calculate attendance percentage rounded to 1 decimal place."""
    if conducted <= 0:
        return 0.0
    pct = (attended / conducted) * 100.0
    return round(pct, 1)


def calculate_required_classes(attended: int, conducted: int, min_percentage: float = 75.0) -> int:
    """
    Calculate the smallest integer x >= 0 such that:
    (attended + x) / (conducted + x) >= min_percentage / 100
    
    Formula:
    x >= (min_fraction * conducted - attended) / (1 - min_fraction)
    """
    if conducted <= 0:
        return 0
    
    if min_percentage <= 0:
        return 0
    
    if min_percentage >= 100.0:
        if attended >= conducted:
            return 0
        return max(0, conducted - attended)
        
    min_fraction = min_percentage / 100.0
    current_fraction = attended / conducted
    
    if current_fraction >= min_fraction:
        return 0
    
    numerator = (min_fraction * conducted) - attended
    denominator = 1.0 - min_fraction
    
    required = math.ceil(numerator / denominator)
    return max(0, int(required))


def calculate_missable_classes(attended: int, conducted: int, min_percentage: float = 75.0) -> int:
    """
    Calculate the maximum integer y >= 0 such that:
    attended / (conducted + y) >= min_percentage / 100
    
    Formula:
    y <= (attended - min_fraction * conducted) / min_fraction
    """
    if conducted <= 0:
        return 0
    
    if min_percentage <= 0:
        return 0
        
    min_fraction = min_percentage / 100.0
    current_fraction = attended / conducted
    
    if current_fraction < min_fraction:
        return 0
    
    numerator = attended - (min_fraction * conducted)
    missable = math.floor(numerator / min_fraction)
    return max(0, int(missable))


def get_attendance_status(percentage: float, conducted: int, min_percentage: float = 75.0) -> dict:
    """
    Evaluate status, alert level, theme color, and human-friendly badge label.
    """
    if conducted == 0:
        return {
            "status": "NO_DATA",
            "level": "info",
            "color": "slate",
            "badge_color": "bg-slate-100 text-slate-800",
            "label": "No Classes Conducted Yet",
            "message": "Classes have not commenced yet.",
            "is_safe": True
        }
    
    if percentage >= min_percentage + 5.0:
        return {
            "status": "SAFE",
            "level": "good",
            "color": "emerald",
            "badge_color": "bg-emerald-100 text-emerald-800",
            "label": "Attendance is Sufficient",
            "message": f"Your attendance is healthy and well above the {min_percentage}% minimum.",
            "is_safe": True
        }
    elif percentage >= min_percentage:
        return {
            "status": "BORDERLINE",
            "level": "warning",
            "color": "amber",
            "badge_color": "bg-amber-100 text-amber-800",
            "label": "Attendance Meets Minimum",
            "message": f"You are currently at or slightly above the {min_percentage}% minimum. Be cautious about missing classes.",
            "is_safe": True
        }
    elif percentage >= min_percentage - 5.0:
        return {
            "status": "NEAR_CRITICAL",
            "level": "danger",
            "color": "orange",
            "badge_color": "bg-orange-100 text-orange-800",
            "label": "Close to Minimum Requirement",
            "message": f"Attendance is below {min_percentage}%. Attend upcoming classes to prevent debarment.",
            "is_safe": False
        }
    else:
        return {
            "status": "CRITICAL",
            "level": "critical",
            "color": "rose",
            "badge_color": "bg-rose-100 text-rose-800",
            "label": "Low Attendance — Action Required",
            "message": f"Critical attendance shortage! You risk exam debarment without immediate intervention.",
            "is_safe": False
        }


def simulate_future_attendance(attended: int, conducted: int, future_attended: int, future_missed: int) -> dict:
    """
    Simulate what the attendance percentage would be after attending or missing a specific number of upcoming classes.
    """
    total_conducted = conducted + future_attended + future_missed
    total_attended = attended + future_attended
    new_pct = calculate_percentage(total_attended, total_conducted)
    return {
        "future_attended": future_attended,
        "future_missed": future_missed,
        "new_conducted": total_conducted,
        "new_attended": total_attended,
        "new_percentage": new_pct
    }
