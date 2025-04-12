from typing import Dict, Any, List
from seo_agent_hub.core.architecture import AnalysisAgent

class KeywordAnalysisAgent(AnalysisAgent):
    """Agent for analyzing keywords across multiple data sources"""
    
    def get_analysis_type(self) -> str:
        return "keyword_analysis"
    
    def get_required_sources(self) -> List[str]:
        # Define which data sources this agent needs to function
        # Adjust based on the actual implementation and available data agents
        return ["google_analytics", "search_console", "semrush_tool", "google_trends_tool"] 
        # Using tool names here as placeholders, might need adjustment based on how data is stored in memory

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze keywords across all available sources"""
        print(f"KeywordAnalysisAgent processing data from sources: {list(data.keys())}")
        product_data = data.get("product_data", {})
        
        # Extract keyword data from each source provided in the input 'data' dictionary
        # The keys in 'data' should match the source names defined in get_required_sources()
        # or the names used by the orchestrator when passing data.
        ga_data = data.get("google_analytics", {})
        sc_data = data.get("search_console", {})
        semrush_data = data.get("semrush_tool", {}) # Assuming tool name is used as key
        trends_data = data.get("google_trends_tool", {}) # Assuming tool name is used as key
        
        # --- Placeholder Logic ---
        # In a real implementation, this section would contain sophisticated logic
        # to combine, deduplicate, analyze intent, score, and rank keywords.
        
        # 1. Combine Keywords
        all_keywords = self._combine_keywords(ga_data, sc_data, semrush_data, trends_data)
        
        # 2. Group by Intent (Placeholder)
        keyword_groups = self._group_by_intent(all_keywords)
        
        # 3. Rank Keywords (Placeholder)
        ranked_keywords = self._rank_keywords(all_keywords)
        
        # 4. Generate Recommendations (Placeholder)
        recommendations = self._generate_recommendations(ranked_keywords, product_data)
        # --- End Placeholder Logic ---

        return {
            "combined_keyword_count": len(all_keywords),
            "keyword_groups": keyword_groups,
            "top_ranked_keywords": ranked_keywords[:15], # Return top 15 ranked keywords
            "recommendations": recommendations
        }

    def _combine_keywords(self, ga_data, sc_data, semrush_data, trends_data):
        """Placeholder: Combine keywords from all sources with source attribution"""
        combined = []
        
        # GA Keywords
        for kw in ga_data.get("brand_keywords", {}).get("keywords", []):
            combined.append({"term": kw.get("term"), "source": "ga", "metrics": kw})
            
        # Search Console Queries
        for query in sc_data.get("search_data", {}).get("queries", []):
             combined.append({"term": query.get("query"), "source": "sc", "metrics": query})

        # SEMrush Keywords (Needs parsing of 'related_keywords_raw')
        # Example: assuming related_keywords_raw is a dict with keyword data
        related_raw = semrush_data.get("related_keywords_raw", {})
        # This part needs refinement based on the actual structure of related_keywords_raw
        if isinstance(related_raw, dict) and "Keyword" in related_raw: # Basic check
             combined.append({"term": related_raw.get("Keyword"), "source": "semrush_related", "metrics": related_raw})

        # Google Trends Related Queries
        trends_related = trends_data.get("related_queries", {})
        for item in trends_related.get("top", []):
             combined.append({"term": item.get("query"), "source": "trends_top", "metrics": item})
        for item in trends_related.get("rising", []):
             combined.append({"term": item.get("query"), "source": "trends_rising", "metrics": item})

        # Deduplicate (simple version based on term)
        seen_terms = set()
        unique_keywords = []
        for kw in combined:
            term = kw.get("term", "").lower()
            if term and term not in seen_terms:
                seen_terms.add(term)
                unique_keywords.append(kw)
                
        print(f"Combined {len(unique_keywords)} unique keywords.")
        return unique_keywords

    def _group_by_intent(self, keywords):
        """Placeholder: Group keywords by search intent (informational, navigational, transactional)"""
        # Simple rule-based intent classification (needs improvement)
        groups = {"informational": [], "navigational": [], "transactional": [], "unknown": []}
        for kw in keywords:
            term = kw.get("term", "").lower()
            if any(w in term for w in ["buy", "price", "discount", "sale", "shop"]):
                groups["transactional"].append(term)
            elif any(w in term for w in ["how", "what", "why", "guide", "tutorial"]):
                 groups["informational"].append(term)
            elif kw.get("source") == "ga" and kw.get("metrics", {}).get("sessions", 0) > 5: # High sessions might indicate navigation
                 groups["navigational"].append(term)
            else:
                 groups["unknown"].append(term)
        print(f"Grouped keywords by intent (simple): { {k: len(v) for k, v in groups.items()} }")
        return {k: v[:10] for k, v in groups.items()} # Return top 10 per group

    def _rank_keywords(self, keywords):
        """Placeholder: Rank keywords by potential value"""
        # Simple scoring: prioritize SC clicks, GA conversions, SEMrush volume
        def calculate_score(kw):
            score = 0
            metrics = kw.get("metrics", {})
            source = kw.get("source")
            
            if source == "sc":
                score += metrics.get("clicks", 0) * 5 # High weight for SC clicks
                score += metrics.get("impressions", 0) * 0.1
            elif source == "ga":
                score += metrics.get("conversions", 0) * 10 # Highest weight for GA conversions
                score += metrics.get("sessions", 0) * 1
            elif source == "semrush_related": # Needs parsing
                 # Add scoring based on SEMrush volume/competition if available
                 pass 
            elif source.startswith("trends"):
                 # Lower score for trends, maybe higher for rising
                 score += metrics.get("value", 0) * 0.5 if source == "trends_rising" else 0.1
                 
            return score

        ranked = sorted(keywords, key=calculate_score, reverse=True)
        print(f"Ranked {len(ranked)} keywords.")
        return ranked

    def _generate_recommendations(self, ranked_keywords, product_data):
        """Placeholder: Generate keyword optimization recommendations"""
        recommendations = []
        top_keywords = [kw['term'] for kw in ranked_keywords[:5] if kw.get('term')]
        
        if top_keywords:
             recommendations.append(f"Prioritize these top keywords in title and description: {', '.join(top_keywords)}")
        
        # Add more specific recommendations based on analysis
        if any(kw['source'] == 'sc' and kw['metrics'].get('ctr', 100) < 1.0 for kw in ranked_keywords[:20]):
             recommendations.append("Improve meta descriptions and titles for low CTR queries found in Search Console.")
             
        if any(kw['source'] == 'ga' and kw['metrics'].get('conversion_rate', 0) > 5.0 for kw in ranked_keywords[:10]):
             high_conv_kw = [kw['term'] for kw in ranked_keywords[:10] if kw['source'] == 'ga' and kw['metrics'].get('conversion_rate', 0) > 5.0]
             recommendations.append(f"Focus on high-converting keywords from GA: {', '.join(high_conv_kw)}")

        print(f"Generated {len(recommendations)} keyword recommendations.")
        return recommendations
