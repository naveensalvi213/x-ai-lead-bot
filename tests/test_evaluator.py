import pytest
from unittest.mock import MagicMock, patch
from src.evaluator import evaluate_tweet_lead

@pytest.mark.asyncio
async def test_evaluate_tweet_lead_success():
    mock_json_response = """
    {
        "is_lead": true,
        "confidence_score": 9,
        "service_match_reason": "User is looking to automate client intake forms using AI.",
        "suggested_comment": "You can easily automate intake forms using custom webhooks with Claude or n8n. Happy to share a working template if you need one!"
    }
    """
    mock_response = MagicMock()
    mock_response.text = mock_json_response

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("src.evaluator.genai.Client", return_value=mock_client):
        result = await evaluate_tweet_lead("Looking for someone to automate client intake forms using AI", api_key="fake_key")
        assert result["is_lead"] is True
        assert result["confidence_score"] == 9
        assert "automate client intake forms" in result["service_match_reason"]
        assert "custom webhooks with Claude" in result["suggested_comment"]
        
        # Verify client call parameters
        mock_client.models.generate_content.assert_called_once()
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        assert call_kwargs["model"] == "gemini-2.5-flash-lite"

@pytest.mark.asyncio
async def test_evaluate_tweet_lead_not_a_lead():
    mock_json_response = """
    {
        "is_lead": false,
        "confidence_score": 2,
        "service_match_reason": "Tweet is about general tech news, not hiring or needing automation.",
        "suggested_comment": ""
    }
    """
    mock_response = MagicMock()
    mock_response.text = mock_json_response

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("src.evaluator.genai.Client", return_value=mock_client):
        result = await evaluate_tweet_lead("AI is advancing so fast this year!", api_key="fake_key")
        assert result["is_lead"] is False
        assert result["confidence_score"] == 2

@pytest.mark.asyncio
async def test_evaluate_tweet_lead_invalid_json():
    mock_response = MagicMock()
    mock_response.text = "This is not valid json text"

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("src.evaluator.genai.Client", return_value=mock_client):
        result = await evaluate_tweet_lead("Need AI workflow help", api_key="fake_key")
        assert result["is_lead"] is False
        assert result["confidence_score"] == 0
        assert "Error:" in result["service_match_reason"]
        assert result["suggested_comment"] == ""

@pytest.mark.asyncio
async def test_evaluate_tweet_lead_api_exception():
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("API connection error")

    with patch("src.evaluator.genai.Client", return_value=mock_client):
        result = await evaluate_tweet_lead("Need AI workflow help", api_key="fake_key")
        assert result["is_lead"] is False
        assert result["confidence_score"] == 0
        assert "API connection error" in result["service_match_reason"]
        assert result["suggested_comment"] == ""
