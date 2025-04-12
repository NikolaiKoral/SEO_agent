from typing import Dict, Any, List, Optional

class ContextBuilder:
    """Builder for creating unified JSON context for data-extract function"""
    
    @staticmethod
    def build_context(product_data: Dict[str, Any], memory: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build unified JSON context from A2A memory.
        
        Args:
            product_data: Original product data (passed initially).
            memory: A2A shared memory containing results from all agents.
            
        Returns:
            Unified JSON context ready for the data-extract function.
        """
        print("Building unified context from A2A memory...")
        
        # Start with base product data format expected by data-extract
        # Using the format derived from formatProductData utility
        context = {
            "EAN nummer": product_data.get("ean", product_data.get("EAN nummer")), # Allow both keys
            "Mærke": product_data.get("brand", product_data.get("Mærke")),
            "Leverandør": product_data.get("brand", product_data.get("Leverandør")),
            "Produktets titel": product_data.get("title", product_data.get("Produktets titel")),
            "Produktbeskrivelse": product_data.get("description", product_data.get("Produktbeskrivelse")),
            # Add other known base fields expected by data-extract, initializing empty
            "Serie": product_data.get("Serie"),
            "Primær farve": product_data.get("Primær farve", ""),
            "Årstal (ift. samlerartikler)": product_data.get("Årstal (ift. samlerartikler)", ""),
            "Materialetype": product_data.get("Materialetype", ""),
            "Trætype": product_data.get("Trætype", ""),
            "Designer": product_data.get("Designer", ""),
            "Effekt": product_data.get("Effekt", ""),
            "Effekt enhed": product_data.get("Effekt enhed", ""),
            "Diameter": product_data.get("Diameter", ""),
            "Diameter Enhed": product_data.get("Diameter Enhed", ""),
            "Længde": product_data.get("Længde", ""),
            "Længde enhed": product_data.get("Længde enhed", ""),
            "Bredde": product_data.get("Bredde", ""),
            "Bredde enhed": product_data.get("Bredde enhed", ""),
            "Højde": product_data.get("Højde", ""),
            "Højde enhed": product_data.get("Højde enhed", ""),
            "Dybde": product_data.get("Dybde", ""),
            "Dybde enhed": product_data.get("Dybde enhed", ""),
            "Vægt": product_data.get("Vægt", ""),
            "Vægt enhed": product_data.get("Vægt enhed", ""),
            "Produktkapacitet": product_data.get("Produktkapacitet", ""),
            "Produktkapacitet enhed": product_data.get("Produktkapacitet enhed", ""),
            "Komfurtype": product_data.get("Komfurtype", ""),
            "Produkt Varmetype": product_data.get("Produkt Varmetype", ""),
            "Produkt låg inkluderet": product_data.get("Produkt låg inkluderet", ""),
            "Produktet tåler opvaskemaskine": product_data.get("Produktet tåler opvaskemaskine", ""),
            "produktbelægning": product_data.get("produktbelægning", ""),
            "Avistekst": product_data.get("Avistekst", ""),
        }
        
        # Add original enriched data if it exists in the input product_data
        if "enrichedData" in product_data:
            print("Adding existing enrichedData to context.")
            # Ensure we don't overwrite base fields if they exist in enrichedData
            for key, value in product_data["enrichedData"].items():
                 if key not in context or not context[key]: # Add if not already set or empty
                     context[key] = value

        # Build SEO context from agent results stored in memory
        seo_context = {
            "sources_used": list(memory.keys()), # List agents that produced output
            "high_value_keywords": ContextBuilder._extract_keywords(memory),
            "search_insights": ContextBuilder._extract_search_insights(memory),
            "competitor_insights": ContextBuilder._extract_competitor_insights(memory),
            "market_positioning": ContextBuilder._extract_market_positioning(memory),
            "content_recommendations": ContextBuilder._extract_content_recommendations(memory),
            "user_segments": ContextBuilder._extract_user_segments(memory),
            "seasonal_trends": ContextBuilder._extract_seasonal_trends(memory),
            "data_quality_issues": ContextBuilder._extract_data_quality_issues(memory),
            "performance_summary": ContextBuilder._extract_performance_summary(memory),
        }
        
        # Add SEO context under the specific key expected by data-extract
        context["seo_context"] = seo_context
        
        print(f"Built context using data from sources: {seo_context['sources_used']}")
        return context

    # --- Helper methods to extract and format data from agent results ---
    # These methods will parse the dictionary structure returned by each agent's process() method

    @staticmethod
    def _extract_keywords(memory: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract and format top keywords from keyword_analysis_agent"""
        analysis_result = memory.get("keyword_analysis", {})
        ranked_keywords = analysis_result.get("top_ranked_keywords", [])
        # Format for data-extract (e.g., just the terms or include metrics)
        return [{"term": kw.get("term"), "score": idx + 1, "source": kw.get("source")} 
                for idx, kw in enumerate(ranked_keywords)]

    @staticmethod
    def _extract_search_insights(memory: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key insights from search_console_agent"""
        sc_result = memory.get("search_console", {}) # Assuming agent name is used as key
        search_data = sc_result.get("search_data", {})
        opportunities = sc_result.get("keyword_opportunities", {})
        return {
            "total_impressions": search_data.get("total_impressions"),
            "total_clicks": search_data.get("total_clicks"),
            "avg_ctr": search_data.get("avg_ctr"),
            "avg_position": search_data.get("avg_position"),
            "dominant_device": search_data.get("dominant_device"),
            "top_queries": search_data.get("queries", [])[:5], # Top 5 queries
            "low_ctr_opportunities": opportunities.get("high_impression_low_ctr", [])[:3], # Top 3 opportunities
        }

    @staticmethod
    def _extract_competitor_insights(memory: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key insights from competitor_analysis_agent"""
        comp_result = memory.get("competitor_analysis", {})
        return {
            "top_competitors": comp_result.get("identified_competitors", []),
            "common_keywords": comp_result.get("content_analysis_summary", {}).get("common_keywords", []),
            "unique_features_vs_competitors": comp_result.get("content_analysis_summary", {}).get("unique_features", []),
            "pricing_position": comp_result.get("pricing_analysis_summary", {}).get("positioning"),
        }

    @staticmethod
    def _extract_market_positioning(memory: Dict[str, Any]) -> Dict[str, Any]:
        """Extract market positioning insights (e.g., from price intelligence)"""
        price_result = memory.get("price_intelligence", {}) # Assuming agent name
        mc_price_data = memory.get("merchant_center", {}).get("price_insights", {})
        
        return {
            "price_position_mc": mc_price_data.get("price_competitiveness", {}).get("relative_position"),
            "category_price_range_mc": mc_price_data.get("category_price_range"),
            # Add data from dedicated price intelligence tool if available
            "price_position_external": price_result.get("market_positioning", {}).get("relative_position"),
        }

    @staticmethod
    def _extract_content_recommendations(memory: Dict[str, Any]) -> Dict[str, Any]:
        """Extract recommendations from content_optimization_agent"""
        content_result = memory.get("content_optimization", {})
        return {
            "title_suggestions": content_result.get("title_recommendations", []),
            "description_suggestions": content_result.get("description_recommendations", []),
            "other_seo_suggestions": content_result.get("other_seo_recommendations", []),
        }

    @staticmethod
    def _extract_user_segments(memory: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract high-value user segments from google_analytics"""
        ga_result = memory.get("google_analytics", {})
        performance = ga_result.get("performance_metrics", {})
        segments = performance.get("user_segments", {}).get("high_value_segments", [])
        return segments

    @staticmethod
    def _extract_seasonal_trends(memory: Dict[str, Any]) -> Dict[str, Any]:
        """Extract seasonal trends from google_analytics and google_trends"""
        ga_seasonal = memory.get("google_analytics", {}).get("performance_metrics", {}).get("seasonal_trends", {})
        trends_seasonal = memory.get("google_trends_tool", {}).get("seasonality", {}) # Assuming tool name key
        
        # Combine or prioritize seasonality data
        is_seasonal = ga_seasonal.get("is_seasonal", False) or trends_seasonal.get("is_seasonal", False)
        peak_month = ga_seasonal.get("peak_month") or trends_seasonal.get("peak_month")
        
        return {
            "is_seasonal": is_seasonal,
            "peak_month": peak_month,
            "trends_data": trends_seasonal # Include detailed trends data if needed
        }

    @staticmethod
    def _extract_data_quality_issues(memory: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract critical data quality issues from merchant_center"""
        mc_result = memory.get("merchant_center", {})
        issues = mc_result.get("product_issues", {}).get("issues", [])
        # Filter for critical/error issues
        critical_issues = [i for i in issues if i.get("severity") in ["critical", "error"]]
        return critical_issues[:5] # Return top 5 critical issues

    @staticmethod
    def _extract_performance_summary(memory: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key performance metrics from GA and MC"""
        ga_perf = memory.get("google_analytics", {}).get("performance_metrics", {}).get("conversion_metrics", {})
        mc_perf = memory.get("merchant_center", {}).get("performance_report", {}).get("metrics", {})
        sc_perf = memory.get("search_console", {}).get("search_data", {})

        return {
            "ga_conversion_rate": ga_perf.get("conversion_rate"),
            "mc_conversion_rate": mc_perf.get("conversion_rate"),
            "sc_avg_ctr": sc_perf.get("avg_ctr"),
            "mc_ctr": mc_perf.get("ctr"),
            "total_impressions_sc": sc_perf.get("total_impressions"),
            "total_clicks_sc": sc_perf.get("total_clicks"),
        }
