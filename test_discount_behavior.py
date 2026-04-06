#!/usr/bin/env python3
"""
Comprehensive test suite for discount behavior in Azure Pricing MCP Server.
Tests the removal of auto-discount behavior and explicit discount application.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from azure_pricing_server import AzurePricingServer, handle_call_tool


# Mock Azure API response fixture
@pytest.fixture
def mock_azure_api_response():
    """Standard mock response from Azure Pricing API."""
    return {
        "Items": [
            {
                "serviceName": "Virtual Machines",
                "productName": "Virtual Machines Dv3 Series",
                "skuName": "D2 v3",
                "armRegionName": "eastus",
                "location": "US East",
                "retailPrice": 0.096,
                "unitOfMeasure": "1 Hour",
                "type": "Consumption",
                "currencyCode": "USD",
                "meterName": "D2 v3"
            },
            {
                "serviceName": "Virtual Machines",
                "productName": "Virtual Machines Dv3 Series",
                "skuName": "D4 v3",
                "armRegionName": "eastus",
                "location": "US East",
                "retailPrice": 0.192,
                "unitOfMeasure": "1 Hour",
                "type": "Consumption",
                "currencyCode": "USD",
                "meterName": "D4 v3"
            }
        ],
        "NextPageLink": None,
        "Count": 2
    }


@pytest.fixture
def mock_azure_api_response_with_savings():
    """Mock response with savings plans."""
    return {
        "Items": [
            {
                "serviceName": "Virtual Machines",
                "productName": "Virtual Machines Dv3 Series",
                "skuName": "D2 v3",
                "armRegionName": "eastus",
                "location": "US East",
                "retailPrice": 0.096,
                "unitOfMeasure": "1 Hour",
                "type": "Consumption",
                "currencyCode": "USD",
                "meterName": "D2 v3",
                "savingsPlan": [
                    {
                        "term": "1 Year",
                        "retailPrice": 0.072
                    },
                    {
                        "term": "3 Year",
                        "retailPrice": 0.060
                    }
                ]
            }
        ],
        "NextPageLink": None,
        "Count": 1
    }


class TestGetCustomerDiscount:
    """Tests for get_customer_discount function - should return 0% by default."""
    
    @pytest.mark.asyncio
    async def test_returns_zero_percent_default(self):
        """get_customer_discount should return 0% by default, not 10%."""
        ps = AzurePricingServer()
        async with ps:
            result = await ps.get_customer_discount()
            
            assert result["discount_percentage"] == 0.0, "Default discount should be 0%, not 10%"
            assert result["discount_type"] == "none", "Default discount type should be 'none'"
    
    @pytest.mark.asyncio
    async def test_returns_zero_with_customer_id(self):
        """get_customer_discount should return 0% even with customer_id."""
        ps = AzurePricingServer()
        async with ps:
            result = await ps.get_customer_discount(customer_id="customer123")
            
            assert result["discount_percentage"] == 0.0
            assert result["customer_id"] == "customer123"
            assert result["discount_type"] == "none"
    
    @pytest.mark.asyncio
    async def test_message_indicates_explicit_request_required(self):
        """Message should indicate discounts must be explicitly requested."""
        ps = AzurePricingServer()
        async with ps:
            result = await ps.get_customer_discount()
            
            message = result.get("description", "") + result.get("note", "")
            assert "explicit" in message.lower(), "Message should indicate explicit request required"
            assert "retail" in message.lower() or "default" in message.lower(), \
                "Message should mention retail/default pricing"


class TestSearchAzurePricesDiscounts:
    """Tests for search_azure_prices function discount behavior."""
    
    @pytest.mark.asyncio
    async def test_without_discount_returns_retail_only(self, mock_azure_api_response):
        """Without discount_percentage, should return retail prices only (no originalPrice)."""
        ps = AzurePricingServer()
        
        with patch.object(ps, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_azure_api_response
            
            async with ps:
                result = await ps.search_azure_prices(
                    service_name="Virtual Machines",
                    limit=10
                )
                
                assert result["count"] == 2
                for item in result["items"]:
                    assert "retailPrice" in item
                    assert "originalPrice" not in item, "Should not have originalPrice without discount"
                    assert "discount_applied" not in result, "Should not have discount_applied key"
    
    @pytest.mark.asyncio
    async def test_with_explicit_discount_shows_both_prices(self, mock_azure_api_response):
        """With explicit discount_percentage, should show both discounted and original prices."""
        ps = AzurePricingServer()
        
        with patch.object(ps, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_azure_api_response
            
            async with ps:
                result = await ps.search_azure_prices(
                    service_name="Virtual Machines",
                    discount_percentage=10.0,
                    limit=10
                )
                
                assert result["count"] == 2
                for item in result["items"]:
                    assert "retailPrice" in item, "Should have discounted retailPrice"
                    assert "originalPrice" in item, "Should have originalPrice when discount applied"
                    
                    # Check discount calculation
                    original = item["originalPrice"]
                    discounted = item["retailPrice"]
                    expected = round(original * 0.9, 6)
                    assert discounted == expected, f"Discount calculation incorrect: {discounted} != {expected}"
    
    @pytest.mark.asyncio
    async def test_with_zero_discount_same_as_no_discount(self, mock_azure_api_response):
        """With discount_percentage=0, should behave same as no discount."""
        ps = AzurePricingServer()
        
        with patch.object(ps, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_azure_api_response
            
            async with ps:
                result = await ps.search_azure_prices(
                    service_name="Virtual Machines",
                    discount_percentage=0.0,
                    limit=10
                )
                
                # With 0%, the _apply_discount_to_items won't be called (discount > 0 check)
                assert result["count"] == 2
                for item in result["items"]:
                    assert "retailPrice" in item
                    assert "originalPrice" not in item, "0% discount should not add originalPrice"
    
    @pytest.mark.asyncio
    async def test_with_100_percent_discount(self, mock_azure_api_response):
        """With discount_percentage=100, should return validation error."""
        ps = AzurePricingServer()
        
        with patch.object(ps, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_azure_api_response
            
            async with ps:
                result = await ps.search_azure_prices(
                    service_name="Virtual Machines",
                    discount_percentage=100.0,
                    limit=10
                )
                
                assert "error" in result, "100% discount should be rejected"
                assert "must be between 0 and 99" in result["error"]
    
    @pytest.mark.asyncio
    async def test_with_50_percent_discount(self, mock_azure_api_response):
        """With discount_percentage=50, prices should be halved."""
        ps = AzurePricingServer()
        
        with patch.object(ps, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_azure_api_response
            
            async with ps:
                result = await ps.search_azure_prices(
                    service_name="Virtual Machines",
                    discount_percentage=50.0,
                    limit=10
                )
                
                assert result["count"] == 2
                for item in result["items"]:
                    original = item["originalPrice"]
                    discounted = item["retailPrice"]
                    expected = round(original * 0.5, 6)
                    assert discounted == expected, "50% discount should halve price"
    
    @pytest.mark.asyncio
    async def test_discount_applies_to_savings_plans(self, mock_azure_api_response_with_savings):
        """Discount should apply to savings plan prices too."""
        ps = AzurePricingServer()
        
        with patch.object(ps, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_azure_api_response_with_savings
            
            async with ps:
                result = await ps.search_azure_prices(
                    service_name="Virtual Machines",
                    discount_percentage=10.0,
                    limit=10
                )
                
                item = result["items"][0]
                assert "savingsPlan" in item
                
                for plan in item["savingsPlan"]:
                    assert "originalPrice" in plan, "Savings plan should have originalPrice"
                    original = plan["originalPrice"]
                    discounted = plan["retailPrice"]
                    expected = round(original * 0.9, 6)
                    assert discounted == expected, "Discount should apply to savings plans"


class TestComparePricesDiscounts:
    """Tests for compare_prices function discount behavior."""
    
    @pytest.mark.asyncio
    async def test_without_discount_returns_retail(self, mock_azure_api_response):
        """compare_prices without discount should return retail comparison."""
        ps = AzurePricingServer()
        
        with patch.object(ps, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_azure_api_response
            
            async with ps:
                result = await ps.compare_prices(
                    service_name="Virtual Machines",
                    regions=["eastus", "westus"]
                )
                
                assert "comparisons" in result
                assert "discount_applied" not in result, "Should not have discount_applied without discount"
                
                for comparison in result["comparisons"]:
                    assert "retail_price" in comparison
                    assert "original_price" not in comparison, "Should not have original_price without discount"
    
    @pytest.mark.asyncio
    async def test_with_explicit_discount_shows_both(self, mock_azure_api_response):
        """compare_prices with discount should show both prices."""
        ps = AzurePricingServer()
        
        with patch.object(ps, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_azure_api_response
            
            async with ps:
                result = await ps.compare_prices(
                    service_name="Virtual Machines",
                    regions=["eastus", "westus"],
                    discount_percentage=20.0
                )
                
                assert "discount_applied" in result
                assert result["discount_applied"]["percentage"] == 20.0
                
                for comparison in result["comparisons"]:
                    if "retail_price" in comparison and comparison["retail_price"]:
                        assert "original_price" in comparison, "Should have original_price when discount applied"
                        original = comparison["original_price"]
                        discounted = comparison["retail_price"]
                        expected = round(original * 0.8, 6)
                        assert discounted == expected


class TestEstimateCostsDiscounts:
    """Tests for estimate_costs function discount behavior."""
    
    @pytest.mark.asyncio
    async def test_without_discount_returns_retail_estimate(self, mock_azure_api_response):
        """estimate_costs without discount should return retail estimates."""
        ps = AzurePricingServer()
        
        with patch.object(ps, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_azure_api_response
            
            async with ps:
                result = await ps.estimate_costs(
                    service_name="Virtual Machines",
                    sku_name="D2 v3",
                    region="eastus",
                    hours_per_month=730
                )
                
                assert "on_demand_pricing" in result
                assert "discount_applied" not in result
                
                pricing = result["on_demand_pricing"]
                assert "hourly_rate" in pricing
                assert "original_hourly_rate" not in pricing, "Should not have original rates without discount"
    
    @pytest.mark.asyncio
    async def test_with_explicit_discount_shows_both_estimates(self, mock_azure_api_response):
        """estimate_costs with discount should show both retail and discounted estimates."""
        ps = AzurePricingServer()
        
        with patch.object(ps, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_azure_api_response
            
            async with ps:
                result = await ps.estimate_costs(
                    service_name="Virtual Machines",
                    sku_name="D2 v3",
                    region="eastus",
                    discount_percentage=15.0,
                    hours_per_month=730
                )
                
                assert "discount_applied" in result
                assert result["discount_applied"]["percentage"] == 15.0
                
                pricing = result["on_demand_pricing"]
                assert "original_hourly_rate" in pricing
                assert "original_monthly_cost" in pricing
                assert "original_yearly_cost" in pricing
                
                # Verify discount calculation
                original_hourly = pricing["original_hourly_rate"]
                discounted_hourly = pricing["hourly_rate"]
                expected_hourly = original_hourly * 0.85
                assert abs(discounted_hourly - expected_hourly) < 0.000001


class TestMCPHandlerDiscountBehavior:
    """Tests for handle_call_tool MCP handler - KEY behavioral change tests."""
    
    @pytest.mark.asyncio
    async def test_azure_price_search_without_discount_no_auto_inject(self, mock_azure_api_response):
        """MCP handler should NOT auto-inject discount when discount_percentage not provided."""
        
        # Create a real server instance and mock its _make_request method
        test_server = AzurePricingServer()
        
        with patch.object(test_server, '_make_request', new_callable=AsyncMock) as mock_request, \
             patch('azure_pricing_server.pricing_server', test_server), \
             patch.object(test_server, 'search_azure_prices', wraps=test_server.search_azure_prices) as spy_search:
            
            mock_request.return_value = mock_azure_api_response
            
            # Call handler without discount_percentage
            arguments = {
                "service_name": "Virtual Machines",
                "limit": 10
            }
            
            result = await handle_call_tool("azure_price_search", arguments)
            
            # Verify search_azure_prices was called
            spy_search.assert_called_once()
            call_kwargs = spy_search.call_args.kwargs
            
            # The key assertion: discount_percentage should NOT be in the call
            # (If old behavior, it would be injected here)
            assert "discount_percentage" not in call_kwargs, \
                "Handler should not inject discount_percentage"
    
    @pytest.mark.asyncio
    async def test_azure_price_search_with_explicit_discount_passes_through(self, mock_azure_api_response):
        """MCP handler should pass through explicit discount_percentage."""
        
        # Create a real server instance and mock its _make_request method
        test_server = AzurePricingServer()
        
        with patch.object(test_server, '_make_request', new_callable=AsyncMock) as mock_request, \
             patch('azure_pricing_server.pricing_server', test_server), \
             patch.object(test_server, 'search_azure_prices', wraps=test_server.search_azure_prices) as spy_search:
            
            mock_request.return_value = mock_azure_api_response
            
            # Call handler WITH discount_percentage
            arguments = {
                "service_name": "Virtual Machines",
                "discount_percentage": 25.0,
                "limit": 10
            }
            
            result = await handle_call_tool("azure_price_search", arguments)
            
            # Verify discount was passed through
            spy_search.assert_called_once()
            call_kwargs = spy_search.call_args.kwargs
            
            assert call_kwargs.get("discount_percentage") == 25.0, \
                "Handler should pass through explicit discount"
    
    @pytest.mark.asyncio
    async def test_get_customer_discount_tool_not_called_by_handler(self, mock_azure_api_response):
        """Verify get_customer_discount is NOT called automatically by azure_price_search handler."""
        
        # Create a real server instance and mock its methods
        test_server = AzurePricingServer()
        
        with patch.object(test_server, '_make_request', new_callable=AsyncMock) as mock_request, \
             patch('azure_pricing_server.pricing_server', test_server), \
             patch.object(test_server, 'get_customer_discount', wraps=test_server.get_customer_discount) as spy_discount:
            
            mock_request.return_value = mock_azure_api_response
            
            arguments = {
                "service_name": "Virtual Machines",
                "limit": 10
            }
            
            await handle_call_tool("azure_price_search", arguments)
            
            # Verify get_customer_discount was NEVER called
            spy_discount.assert_not_called()


class TestEdgeCases:
    """Test edge cases for discount handling."""
    
    @pytest.mark.asyncio
    async def test_negative_discount_percentage(self, mock_azure_api_response):
        """Negative discount should be rejected."""
        ps = AzurePricingServer()
        
        with patch.object(ps, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_azure_api_response
            
            async with ps:
                result = await ps.search_azure_prices(
                    service_name="Virtual Machines",
                    discount_percentage=-10.0,
                    limit=10
                )
                
                assert "error" in result, "Negative discount should be rejected"
                assert "must be between 0 and 99" in result["error"]
    
    @pytest.mark.asyncio
    async def test_discount_over_100_percent(self, mock_azure_api_response):
        """Discount > 100% should be rejected."""
        ps = AzurePricingServer()
        
        with patch.object(ps, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_azure_api_response
            
            async with ps:
                result = await ps.search_azure_prices(
                    service_name="Virtual Machines",
                    discount_percentage=150.0,
                    limit=10
                )
                
                assert "error" in result, "Discount > 100% should be rejected"
                assert "must be between 0 and 99" in result["error"]
    
    @pytest.mark.asyncio
    async def test_compare_rejects_invalid_discount(self, mock_azure_api_response):
        """compare_prices should also reject invalid discounts."""
        ps = AzurePricingServer()
        
        with patch.object(ps, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_azure_api_response
            
            async with ps:
                result = await ps.compare_prices(
                    service_name="Virtual Machines",
                    regions=["eastus"],
                    discount_percentage=100.0
                )
                assert "error" in result
    
    @pytest.mark.asyncio
    async def test_estimate_rejects_invalid_discount(self, mock_azure_api_response):
        """estimate_costs should also reject invalid discounts."""
        ps = AzurePricingServer()
        
        with patch.object(ps, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_azure_api_response
            
            async with ps:
                result = await ps.estimate_costs(
                    service_name="Virtual Machines",
                    sku_name="D2 v3",
                    region="eastus",
                    discount_percentage=-5.0
                )
                assert "error" in result
    
    @pytest.mark.asyncio
    async def test_99_percent_discount_is_allowed(self, mock_azure_api_response):
        """99% discount should be the maximum allowed."""
        ps = AzurePricingServer()
        
        with patch.object(ps, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_azure_api_response
            
            async with ps:
                result = await ps.search_azure_prices(
                    service_name="Virtual Machines",
                    discount_percentage=99.0,
                    limit=10
                )
                
                assert "error" not in result, "99% discount should be allowed"
                assert "discount_applied" in result
    
    @pytest.mark.asyncio
    async def test_empty_items_with_discount(self):
        """Applying discount to empty result set should not error."""
        ps = AzurePricingServer()
        
        with patch.object(ps, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"Items": [], "Count": 0}
            
            async with ps:
                result = await ps.search_azure_prices(
                    service_name="NonExistentService",
                    discount_percentage=10.0,
                    limit=10
                )
                
                assert result["count"] == 0
                assert result["items"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
