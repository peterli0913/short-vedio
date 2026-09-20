from auto_resume_bot.currency import parse_salary_to_rmb_min


def test_parse_hkd_monthly():
    assert parse_salary_to_rmb_min("HKD 60,000 - 80,000", 0.92) == 55200


def test_parse_cny():
    assert parse_salary_to_rmb_min("人民币 5万-8万/月", 0.92) == 50000


def test_unparseable():
    assert parse_salary_to_rmb_min("面议", 0.92) is None
