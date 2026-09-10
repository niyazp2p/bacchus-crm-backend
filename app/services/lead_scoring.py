import re
from app.models.lead import CommercialModel, LeadTier

def calculate_lead_score(
    commercial_model: CommercialModel,
    volume_estimate: str | None,
    country: str,
    phone: str | None,
    email: str,
) -> tuple[int, LeadTier]:
    """
    Computes qualification score (0-100) and assigns lead tier.
    HOT: >= 70 | WARM: 40-69 | COLD: < 40
    """
    score = 0

    # 1. Commercial Model Base Weight
    if commercial_model == CommercialModel.STATE_OWNERSHIP:
        score += 35
    elif commercial_model == CommercialModel.DISTRIBUTION:
        score += 30
    elif commercial_model == CommercialModel.PRIVATE_LABEL:
        score += 25

    # 2. Volume Estimate Evaluation
    if volume_estimate:
        vol_lower = volume_estimate.lower()
        if any(term in vol_lower for term in ["container", "fcl", "40ft", "20ft"]):
            score += 35
            # High-velocity container volume bonus
            match = re.search(r"(\d+)", vol_lower)
            if match and int(match.group(1)) >= 5:
                score += 10
        elif any(term in vol_lower for term in ["case", "pallet", "truckload"]):
            score += 20
        else:
            score += 10

    # 3. Contact & Corporate Credibility
    free_domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]
    domain = email.split("@")[-1].lower() if "@" in email else ""
    if domain and domain not in free_domains:
        score += 15  # Verified corporate email domain

    if phone and len(phone.strip()) >= 7:
        score += 10  # Valid direct phone line

    # 4. Strategic Footprint
    strategic_corridors = [
        "tanzania", "kenya", "nigeria", "united states", "usa", 
        "united arab emirates", "uae", "canada", "united kingdom", "uk", "india"
    ]
    if country.strip().lower() in strategic_corridors:
        score += 10

    # Normalization & Tier Categorization
    final_score = min(score, 100)
    if final_score >= 70:
        tier = LeadTier.HOT
    elif final_score >= 40:
        tier = LeadTier.WARM
    else:
        tier = LeadTier.COLD

    return final_score, tier