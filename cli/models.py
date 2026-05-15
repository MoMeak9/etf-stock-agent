from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel


class AssetType(str, Enum):
    STOCK = "stock"
    ETF = "etf"


class AnalystType(str, Enum):
    MARKET = "market"
    SOCIAL = "social"
    NEWS = "news"
    FUNDAMENTALS = "fundamentals"
