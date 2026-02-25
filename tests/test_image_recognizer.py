"""Tests for image recognizer LLM response parser."""
import json

import pytest

from autocoin.services.image_recognizer import _parse_llm_response


class TestParseLlmResponse:
    def test_basic_json_array(self):
        data = [
            {
                "transaction_time": "2025-01-15 12:30:00",
                "direction": "expense",
                "amount": 25.80,
                "category": "餐饮",
                "counterparty": "美团",
                "product": "外卖",
                "payment_method": "花呗",
                "remark": "",
            }
        ]
        result = _parse_llm_response(json.dumps(data))
        assert len(result) == 1
        assert result[0]["amount"] == 25.80
        assert result[0]["direction"] == "expense"
        assert result[0]["category"] == "餐饮"

    def test_markdown_code_fence(self):
        data = [{"transaction_time": "2025-01-15 12:30:00", "direction": "income", "amount": 100}]
        text = f"```json\n{json.dumps(data)}\n```"
        result = _parse_llm_response(text)
        assert len(result) == 1
        assert result[0]["direction"] == "income"

    def test_wrapped_in_dict(self):
        data = {
            "transactions": [
                {"transaction_time": "2025-01-15 12:30:00", "direction": "expense", "amount": 50}
            ]
        }
        result = _parse_llm_response(json.dumps(data))
        assert len(result) == 1
        assert result[0]["amount"] == 50

    def test_skip_zero_amount(self):
        data = [
            {"transaction_time": "2025-01-15 12:30:00", "direction": "expense", "amount": 0},
            {"transaction_time": "2025-01-15 13:00:00", "direction": "expense", "amount": 10},
        ]
        result = _parse_llm_response(json.dumps(data))
        assert len(result) == 1
        assert result[0]["amount"] == 10

    def test_invalid_direction_defaults_to_expense(self):
        data = [{"transaction_time": "2025-01-15 12:30:00", "direction": "unknown", "amount": 20}]
        result = _parse_llm_response(json.dumps(data))
        assert result[0]["direction"] == "expense"

    def test_json_embedded_in_text(self):
        text = 'Here are the transactions:\n[{"transaction_time": "2025-01-15 12:30:00", "direction": "expense", "amount": 15}]\nDone.'
        result = _parse_llm_response(text)
        assert len(result) == 1

    def test_garbage_input_returns_empty(self):
        result = _parse_llm_response("This is not JSON at all.")
        assert result == []

    def test_single_dict_result(self):
        data = {"transaction_time": "2025-01-15 12:30:00", "direction": "expense", "amount": 30}
        result = _parse_llm_response(json.dumps(data))
        assert len(result) == 1

    def test_multiple_transactions(self):
        data = [
            {"transaction_time": "2025-01-15 12:30:00", "direction": "expense", "amount": 10, "category": "A"},
            {"transaction_time": "2025-01-15 13:00:00", "direction": "income", "amount": 20, "category": "B"},
            {"transaction_time": "2025-01-15 14:00:00", "direction": "neutral", "amount": 5, "category": "C"},
        ]
        result = _parse_llm_response(json.dumps(data))
        assert len(result) == 3
        assert result[2]["direction"] == "neutral"

    def test_negative_amount_skipped(self):
        data = [{"transaction_time": "2025-01-15 12:30:00", "direction": "expense", "amount": -10}]
        result = _parse_llm_response(json.dumps(data))
        assert len(result) == 0
