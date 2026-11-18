import google.generativeai as genai
import os
import re
from dotenv import load_dotenv
import json
from dsl.validator import ALLOWED_FIELDS

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

def is_valid_gemini_key(key: str | None) -> bool:
    if not key:
        return False
    clean = key.strip().lower()
    return clean not in ("", "your_gemini_api_key_here", "none", "null")

if is_valid_gemini_key(api_key):
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        print(f"Failed to configure Gemini API: {e}")

SECTOR_MAP = {
    "tech": "Technology",
    "technology": "Technology",
    "software": "Technology",
    "semiconductor": "Technology",
    "semis": "Technology",
    "chips": "Technology",
    "ai": "Technology",
    "healthcare": "Healthcare",
    "health": "Healthcare",
    "pharma": "Healthcare",
    "pharmaceutical": "Healthcare",
    "biotech": "Healthcare",
    "finance": "Financial Services",
    "financials": "Financial Services",
    "financial services": "Financial Services",
    "bank": "Financial Services",
    "banking": "Financial Services",
    "insurance": "Financial Services",
    "consumer": "Consumer Cyclical",
    "consumer cyclical": "Consumer Cyclical",
    "retail": "Consumer Cyclical",
    "auto": "Consumer Cyclical",
    "ev": "Consumer Cyclical",
    "industrials": "Industrials",
    "energy": "Energy",
    "oil": "Energy",
    "gas": "Energy",
    "utilities": "Utilities",
    "real estate": "Real Estate",
    "communication": "Communication Services",
    "basic materials": "Basic Materials",
}

COMPANY_TICKERS = {
    "apple": "AAPL", "aapl": "AAPL",
    "microsoft": "MSFT", "msft": "MSFT",
    "google": "GOOGL", "alphabet": "GOOGL", "googl": "GOOGL", "goog": "GOOGL",
    "nvidia": "NVDA", "nvda": "NVDA",
    "amazon": "AMZN", "amzn": "AMZN",
    "tesla": "TSLA", "tsla": "TSLA",
    "meta": "META", "facebook": "META",
    "netflix": "NFLX", "nflx": "NFLX",
    "disney": "DIS", "dis": "DIS",
    "walmart": "WMT", "wmt": "WMT",
    "costco": "COST", "cost": "COST",
    "coca cola": "KO", "coke": "KO", "ko": "KO",
    "pepsi": "PEP", "pepsico": "PEP", "pep": "PEP",
    "jpmorgan": "JPM", "chase": "JPM", "jpm": "JPM",
    "visa": "V",
    "mastercard": "MA",
    "johnson & johnson": "JNJ", "johnson and johnson": "JNJ", "jnj": "JNJ",
    "pfizer": "PFE", "pfe": "PFE",
    "exxon": "XOM", "exxonmobil": "XOM", "xom": "XOM",
    "chevron": "CVX", "cvx": "CVX",
    "boeing": "BA", "ba": "BA",
    "caterpillar": "CAT", "cat": "CAT",
    "broadcom": "AVGO", "avgo": "AVGO",
    "oracle": "ORCL", "orcl": "ORCL",
    "salesforce": "CRM", "crm": "CRM",
    "amd": "AMD",
    "intel": "INTC", "intc": "INTC",
    "cisco": "CSCO", "csco": "CSCO",
    "eli lilly": "LLY", "lly": "LLY",
    "unitedhealth": "UNH", "unh": "UNH",
    "abbvie": "ABBV", "abbv": "ABBV",
    "merck": "MRK", "mrk": "MRK",
    "honeywell": "HON", "hon": "HON",
    "prologis": "PLD", "pld": "PLD",
}

def rule_based_fallback_parser(query: str) -> dict:
    """Deterministic fallback parser for common financial queries when LLM is unavailable or rate-limited."""
    q_lower = query.strip().lower()
    filters = []
    
    # 1. Company name / ticker matching
    for name, ticker in COMPANY_TICKERS.items():
        pattern = r"\b" + re.escape(name) + r"\b"
        if re.search(pattern, q_lower):
            filters.append({"field": "symbol", "operator": "=", "value": ticker})
            break

    # 2. Sector matching
    for key, sector_name in SECTOR_MAP.items():
        pattern = r"\b" + re.escape(key) + r"\b"
        if re.search(pattern, q_lower):
            filters.append({"field": "sector", "operator": "=", "value": sector_name})
            break
            
    # 2. PE ratio matching: e.g. "pe < 30", "pe_ratio <= 25", "p/e > 15"
    pe_match = re.search(r"(?:pe|pe_ratio|p/e)\s*(=|<=|>=|<|>)\s*(\d+(?:\.\d+)?)", q_lower)
    if pe_match:
        op = pe_match.group(1)
        val = float(pe_match.group(2))
        filters.append({"field": "pe_ratio", "operator": op, "value": val})
    elif "undervalued" in q_lower or "low pe" in q_lower:
        filters.append({"field": "pe_ratio", "operator": "<", "value": 25.0})
        
    # 3. EPS matching: e.g. "eps > 5", "profitable"
    eps_match = re.search(r"\beps\s*(=|<=|>=|<|>)\s*(\d+(?:\.\d+)?)", q_lower)
    if eps_match:
        op = eps_match.group(1)
        val = float(eps_match.group(2))
        filters.append({"field": "eps", "operator": op, "value": val})
    elif "profitable" in q_lower or "positive earnings" in q_lower:
        filters.append({"field": "eps", "operator": ">", "value": 0.0})
        
    # 4. Market Cap matching: e.g. "market cap > 50B", "market_cap < 100B", "mega cap", "large cap"
    cap_match = re.search(r"(?:market\s*cap|market_cap)\s*(=|<=|>=|<|>)\s*(\d+(?:\.\d+)?)\s*([tbmk])?", q_lower)
    if cap_match:
        op = cap_match.group(1)
        val = float(cap_match.group(2))
        unit = (cap_match.group(3) or "").lower()
        if unit == "t":
            val *= 1e12
        elif unit == "b":
            val *= 1e9
        elif unit == "m":
            val *= 1e6
        elif unit == "k":
            val *= 1e3
        filters.append({"field": "market_cap", "operator": op, "value": val})
    elif "mega cap" in q_lower or "mega-cap" in q_lower:
        filters.append({"field": "market_cap", "operator": ">", "value": 200e9})
    elif "large cap" in q_lower or "large-cap" in q_lower:
        filters.append({"field": "market_cap", "operator": ">", "value": 10e9})
    elif "small cap" in q_lower or "small-cap" in q_lower:
        filters.append({"field": "market_cap", "operator": "<", "value": 2e9})

    # 5. Revenue growth matching: e.g. "growth > 10", "revenue growth > 15", "high growth"
    growth_match = re.search(r"(?:revenue\s*growth|growth)\s*(=|<=|>=|<|>)\s*(\d+(?:\.\d+)?)", q_lower)
    if growth_match:
        op = growth_match.group(1)
        val = float(growth_match.group(2))
        filters.append({"field": "revenue_growth", "operator": op, "value": val})
    elif "high growth" in q_lower:
        filters.append({"field": "revenue_growth", "operator": ">", "value": 15.0})

    if filters:
        return {"filters": filters, "logic": "AND"}
    # Safe universal fallback: returns empty filter to display all market stocks
    return {"filters": [], "logic": "AND"}

def normalize_dsl_dict(d: dict) -> dict:
    """Normalize common variations in LLM JSON output to standard DSL schema."""
    if not isinstance(d, dict):
        return d
    if "conditions" in d and "filters" not in d:
        d["filters"] = d.pop("conditions")
    if "filter" in d and "filters" not in d:
        val = d.pop("filter")
        d["filters"] = [val] if isinstance(val, dict) else val
    if "logic" not in d:
        d["logic"] = "AND"
    return d

def parse_query_to_dsl(query: str) -> dict:
    prompt = f"""
    You are a financial query parser. Convert the following natural language query into a structured DSL JSON format.
    
    ### Guidelines:
    1. Return ONLY valid JSON.
    2. Do not include markdown code blocks (e.g., ```json).
    3. Do not include any explanations or extra text.
    4. Allowed fields: {', '.join(ALLOWED_FIELDS)}
    5. Allowed operators: =, <, >, <=, >=
    6. Logic must be "AND" or "OR".
    7. For time-based queries, use "time_filter".
    
    ### DSL Schema:
    {{
      "filters": [
        {{
          "field": "string",
          "operator": "string",
          "value": number or string
        }}
      ],
      "logic": "AND" | "OR",
      "time_filter": {{
        "type": "quarter",
        "value": "YYYY-QX"
      }} // Optional.
    }}

    ### Examples:
    - "Tech stocks with PE < 20": 
      {{"filters": [{{"field": "sector", "operator": "=", "value": "Technology"}}, {{"field": "pe_ratio", "operator": "<", "value": 20}}], "logic": "AND"}}
    
    - "Companies with net income > 5B in 2024-Q1":
      {{"filters": [{{"field": "net_income", "operator": ">", "value": 5000000000}}], "logic": "AND", "time_filter": {{"type": "quarter", "value": "2024-Q1"}}}}

    Query: {query}
    """
    
    llm_error = None
    current_key = os.getenv("GEMINI_API_KEY") or api_key
    if is_valid_gemini_key(current_key):
        try:
            genai.configure(api_key=current_key)
        except Exception as e:
            print(f"Error configuring Gemini with current key: {e}")

        # Primary model: gemini-3.8-flash; Fallback: gemini-latest (gemini-flash-latest)
        models_to_try = ["gemini-3.8-flash", "gemini-flash-latest", "gemini-flash-lite-latest"]
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                # 12-second explicit timeout prevents socket hang on 429 quota backoff
                response = model.generate_content(prompt, request_options={"timeout": 12.0})
                text = response.text.strip()
                if text.startswith("```json"):
                    text = text[7:-3].strip()
                elif text.startswith("```"):
                    text = text[3:-3].strip()
                parsed = json.loads(text)
                return normalize_dsl_dict(parsed)
            except Exception as e:
                llm_error = e
                print(f"Gemini model '{model_name}' failed/rate-limited: {e}. Trying fallback...")
    else:
        llm_error = RuntimeError("GEMINI_API_KEY is not configured.")

    # Execute fallback parser
    fallback_result = rule_based_fallback_parser(query)
    if fallback_result:
        return fallback_result

    # If fallback cannot parse and LLM threw error, raise error
    if llm_error:
        raise RuntimeError(f"Error communicating with Gemini API: {llm_error}")
    raise ValueError("Unable to parse query with either Gemini or fallback parser.")
