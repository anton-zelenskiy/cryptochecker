from project.paper_trading.decision import decision_from_rsi


def test_decision_from_rsi_wait():
    decision, conf = decision_from_rsi(50)
    assert decision == "WAIT"
    assert conf == 0.0


def test_decision_from_rsi_long():
    decision, conf = decision_from_rsi(10)
    assert decision == "LONG"
    assert 0.8 <= conf <= 1.0


def test_decision_from_rsi_short():
    decision, conf = decision_from_rsi(90)
    assert decision == "SHORT"
    assert 0.8 <= conf <= 1.0

