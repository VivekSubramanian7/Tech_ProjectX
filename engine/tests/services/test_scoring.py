from app.services.scoring import final_scores, risk_score_for_code


def test_passport_risk_above_ip():
    passport_risk, _ = final_scores("PASSPORT_NUMBER", 0.9)
    ip_risk, _ = final_scores("IP_ADDRESS", 0.9)
    assert passport_risk > ip_risk


def test_confidence_independent_of_risk_weight():
    risk, conf = final_scores("EMAIL", 0.42)
    assert conf == 0.42
    assert risk == risk_score_for_code("EMAIL")
